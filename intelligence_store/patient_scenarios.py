"""Transient synthetic scenario inputs attached to existing evidence references."""

import hashlib
import json
import math
from pathlib import Path
import re

import click
from sqlalchemy.exc import SQLAlchemyError

from .drug_aliases import AliasCatalogError, load_alias_catalog, reconcile_drug_aliases
from .interactions import InteractionCatalogError, summarize_interactions
from .intervention_names import name_key
from .safety import SafetyCatalogError, summarize_safety
from .summaries import CohortSummaryError, summarize_cohort
from .trial_criteria import summarize_criteria
from .pharmacokinetics import pk_availability

METHOD_VERSION = "synthetic-scenario-references-v1.2"
SCHEMA_VERSION = "synthetic-patient-scenario-v1"
PRESETS_PATH = Path(__file__).parent / "data" / "patient_scenarios_v1.json"
SEX_VALUES = ("FEMALE", "MALE", "UNSPECIFIED")
DOSE_UNITS = ("mg", "mg/m2", "mg/kg")
FIELDS = {
    "schema_version", "purpose", "age_years", "biological_sex", "weight_kg",
    "egfr_ml_min_1_73m2", "selected_drug", "dose_value", "dose_unit",
    "indication", "medications",
}
LIMITATION = (
    "Synthetic Educational Patient Scenario. Outputs are product-label references and "
    "reported fields in frozen studies, not an individual clinical assessment. Age and sex "
    "are compared only with reported protocol fields, not actual participant demographics "
    "or full eligibility. Weight, eGFR, dose and indication remain descriptive. No renal-dose, "
    "individualized exposure or risk result is calculated. An optional historical PK "
    "teaching model runs separately with fixed parameters and an invented mg dose."
)


class ScenarioValidationError(ValueError):
    pass


def _number(value, label, *, positive=False, maximum=None):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ScenarioValidationError(f"{label} must be a finite number or left blank.")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ScenarioValidationError(f"{label} must be a finite number or left blank.") from exc
    if (not math.isfinite(result) or result < 0 or (positive and result == 0)
        or (maximum is not None and result > maximum)):
        raise ScenarioValidationError(f"{label} is outside the supported synthetic input range.")
    return result


def validate_scenario(profile, alias_catalog=None):
    if not isinstance(profile, dict) or set(profile) != FIELDS:
        raise ScenarioValidationError("The scenario has missing or unsupported fields.")
    if profile["schema_version"] != SCHEMA_VERSION or profile["purpose"] != "synthetic_educational":
        raise ScenarioValidationError("Only the synthetic educational scenario schema is supported.")
    aliases = alias_catalog if alias_catalog is not None else load_alias_catalog()
    if not isinstance(profile["selected_drug"], str) or profile["selected_drug"] not in {e["id"] for e in aliases["entries"]}:
        raise ScenarioValidationError("Select a drug from the curated name catalog.")
    if profile["biological_sex"] not in SEX_VALUES:
        raise ScenarioValidationError("Biological sex must be FEMALE, MALE or UNSPECIFIED.")
    age = _number(profile["age_years"], "Age", maximum=130)
    weight = _number(profile["weight_kg"], "Weight", positive=True)
    egfr = _number(profile["egfr_ml_min_1_73m2"], "eGFR")
    dose = _number(profile["dose_value"], "Dose", positive=True)
    unit = profile["dose_unit"]
    if dose is not None and unit not in DOSE_UNITS:
        raise ScenarioValidationError("A supplied dose requires mg, mg/m2 or mg/kg units.")
    if dose is None and unit is not None:
        raise ScenarioValidationError("A dose unit requires a dose value.")
    indication = profile["indication"]
    if not isinstance(indication, str) or len(indication) > 160:
        raise ScenarioValidationError("Indication must be text of at most 160 characters.")
    medications = profile["medications"]
    if not isinstance(medications, list) or len(medications) > 20:
        raise ScenarioValidationError("Enter up to 20 medication names, one per line.")
    names, seen = [], set()
    for value in medications:
        if not isinstance(value, str) or not value.strip() or len(value) > 120 or "\n" in value or "\r" in value:
            raise ScenarioValidationError("Each medication must be one nonblank name of at most 120 characters.")
        key = name_key(value)
        if key not in seen:
            names.append(value.strip())
            seen.add(key)
    return {
        "schema_version": SCHEMA_VERSION, "purpose": "synthetic_educational",
        "age_years": age, "biological_sex": profile["biological_sex"],
        "weight_kg": weight, "egfr_ml_min_1_73m2": egfr,
        "selected_drug": profile["selected_drug"], "dose_value": dose,
        "dose_unit": unit, "indication": indication.strip(), "medications": names,
    }


def load_scenario_presets(path=PRESETS_PATH, alias_catalog=None):
    try:
        content = Path(path).read_bytes()
        data = json.loads(content)
        if not isinstance(data, dict) or data.get("schema_version") != "synthetic-scenario-presets-v1":
            raise ValueError("Unsupported preset schema")
        if not isinstance(data.get("catalog_version"), str) or not data["catalog_version"].strip():
            raise ValueError("Missing preset version")
        if not isinstance(data.get("presets"), list) or not data["presets"]:
            raise ValueError("Missing presets")
        aliases = alias_catalog if alias_catalog is not None else load_alias_catalog()
        index, presets = {}, []
        for item in data["presets"]:
            if not isinstance(item, dict):
                raise ValueError("Invalid preset")
            key = item.get("id")
            if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key) or key in index:
                raise ValueError("Invalid or duplicate preset")
            if any(not isinstance(item.get(k), str) or not item[k].strip() for k in ("label", "description")):
                raise ValueError("Missing preset description")
            preset = {**item, "profile": validate_scenario(item.get("profile"), aliases)}
            index[key] = preset
            presets.append(preset)
        return {"catalog_version": data["catalog_version"], "sha256": hashlib.sha256(content).hexdigest(),
                "presets": presets, "index": index}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ScenarioValidationError("Synthetic scenario examples are missing, invalid or incompatible; no example was loaded.") from exc


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def summarize_scenario(summary, profile):
    alias_catalog = load_alias_catalog()
    profile = validate_scenario(profile, alias_catalog)
    aliases = reconcile_drug_aliases(summary, alias_catalog)
    safety = summarize_safety(summary, aliases)
    interactions = summarize_interactions(summary, aliases)
    entity = profile["selected_drug"]
    alias_entry = next(e for e in alias_catalog["entries"] if e["id"] == entity)
    group = next((g for g in aliases["groups"] if g.get("catalog_entry") and g["catalog_entry"]["id"] == entity), None)
    ids = set(group["nct_ids"]) if group else set()
    selected_safety = next((e for e in safety["catalog_entries"] if e["entity_id"] == entity), None)
    selected_interactions = next((e for e in interactions["entries"] if e["entity_id"] == entity), None)
    if selected_safety is None or selected_interactions is None:
        raise ScenarioValidationError("The selected drug lacks a required starter reference; no partial scenario report was generated.")
    recruiting = ids & set(summary["metrics"]["recruiting_trials"]["nct_ids"])
    rules = selected_interactions["references"]
    partner_index = {name_key(r["partner_name"]): r for r in rules if r["kind"] == "drug_pair"}
    anchor_keys = {name_key(name) for name in alias_entry["aliases"]}
    medication_rows, pair_ids = [], set()
    for name in profile["medications"]:
        key = name_key(name)
        rule = partner_index.get(key)
        status = "selected_reference" if rule else "same_reference_name" if key in anchor_keys else "unassessed"
        medication_rows.append({"name": name, "status": status, "reference": rule})
        if rule:
            pair_ids.update(rule["pair_nct_ids"])
    criteria = summarize_criteria(summary, profile, aliases=aliases)
    profile_digest = _digest(profile)
    evidence = {nct: summary["evidence"][nct] for nct in sorted(ids)}
    provenance = {
        "method_version": METHOD_VERSION, "profile_sha256": profile_digest,
        "criteria_method_version": criteria["method_version"],
        "criteria_report_sha256": criteria["report_sha256"],
        "summary_method_version": summary["method_version"],
        "alias_catalog_version": aliases["catalog_version"], "alias_catalog_sha256": aliases["catalog_sha256"],
        "safety_catalog_version": safety["catalog_version"], "safety_catalog_sha256": safety["catalog_sha256"],
        "interaction_catalog_version": interactions["catalog_version"], "interaction_catalog_sha256": interactions["catalog_sha256"],
    }
    result = {
        "scenario_label": "Synthetic Educational Patient Scenario", "profile": profile,
        "selected_drug": {"entity_id": entity, "label": alias_entry["canonical_name"],
                          "variants": group["variants"] if group else []},
        "cohort": summary["cohort"], "total_trials": summary["metrics"]["total_trials"]["value"],
        "reference_trials": {"count": len(ids), "nct_ids": sorted(ids)},
        "recruiting_reference_trials": {"count": len(recruiting), "nct_ids": sorted(recruiting)},
        "medications": medication_rows,
        "medication_coverage": {"entered_unique": len(medication_rows),
            "selected_references": sum(r["status"] == "selected_reference" for r in medication_rows),
            "unassessed": sum(r["status"] == "unassessed" for r in medication_rows),
            "same_reference_name": sum(r["status"] == "same_reference_name" for r in medication_rows)},
        "selected_pair_trials": {"count": len(pair_ids), "nct_ids": sorted(pair_ids)},
        "criteria": criteria,
        "pk_demo_availability": pk_availability(profile),
        "safety_reference": selected_safety, "interaction_reference": selected_interactions,
        "non_pair_references": [r for r in rules if r["kind"] != "drug_pair"],
        "evidence": evidence, "provenance": provenance,
        "limitation": LIMITATION,
    }
    result["scenario_sha256"] = _digest(result)
    return result


def register_scenario_commands(app):
    @app.cli.command("cohort-scenario")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--preset", type=str)
    @click.option("--profile", type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path))
    @click.option("--json", "json_output", is_flag=True)
    def cohort_scenario(cohort_id, preset, profile, json_output):
        """Inspect a synthetic educational scenario without saving patient records."""
        if preset and profile:
            raise click.UsageError("Use either --preset or --profile, not both.")
        try:
            if profile:
                if profile.stat().st_size > 4194304:
                    raise ScenarioValidationError("Scenario JSON must be at most 4 MiB.")
                scenario = json.loads(profile.read_text())
                if isinstance(scenario, dict) and scenario.get("scenario_label") == "Synthetic Educational Patient Scenario":
                    scenario = scenario.get("profile")
            else:
                presets = load_scenario_presets()
                key = preset or "interaction-reference"
                if key not in presets["index"]:
                    raise ScenarioValidationError("Unknown synthetic example. Use interaction-reference, laboratory-reference or coverage-gap.")
                scenario = presets["index"][key]["profile"]
            result = summarize_scenario(summarize_cohort(cohort_id), scenario)
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException("Database unavailable. Check configuration and migrations.") from exc
        if json_output:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
            return
        click.echo(result["scenario_label"])
        click.echo(f"Cohort {cohort_id}: {result['cohort']['condition']} | {result['cohort']['scope']} | COMPLETE")
        click.echo(f"Method: {METHOD_VERSION} | Selected reference drug: {result['selected_drug']['label']}")
        click.echo(f"Saved trials: {result['total_trials']}")
        click.echo(f"Trials containing the reference name: {result['reference_trials']['count']}")
        click.echo(f"Recruiting records containing that name: {result['recruiting_reference_trials']['count']}")
        coverage = result["medication_coverage"]
        click.echo(f"Unique entered medications: {coverage['entered_unique']} | Selected pair references: {coverage['selected_references']} | Unassessed: {coverage['unassessed']} | Same reference name: {coverage['same_reference_name']}")
        for row in result["medications"]:
            rule = row["reference"]
            click.echo(f"\n{row['name']}: {rule['finding_label'] if rule else 'Not assessed as a separate selected pair'}")
            if rule:
                click.echo(rule["basis"])
                click.echo(f"Sections {', '.join(rule['sections'])} | Studies listing both names: {rule['pair_count']}")
        click.echo("\nReported age/sex criteria:")
        for row in result["criteria"]["groups"]["combined"]:
            click.echo(f"  {row['label']}: {row['count']}")
        click.echo(f"\nScenario SHA256: {result['scenario_sha256']}")
        click.echo(LIMITATION)
