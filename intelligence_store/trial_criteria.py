"""Reported age/sex field comparison, never actual participant representation."""

from collections import Counter
import hashlib
import json
import math
import re

import click
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .drug_aliases import load_alias_catalog, reconcile_drug_aliases
from .extensions import db
from .models import TrialSnapshot
from .normalization import _mapping, _text
from .summaries import CohortSummaryError, summarize_cohort

METHOD_VERSION = "reported-age-sex-fields-v1.0"
COMPARISON_LABELS = {
    "within": "Within both reported fields",
    "outside": "Outside at least one reported field",
    "unresolved": "Unresolved comparison",
}
DIMENSION_LABELS = {
    "age": {"within": "Within reported age bounds", "outside": "Outside a reported age bound", "unresolved": "Age comparison unresolved"},
    "sex": {"within": "Within reported sex field", "outside": "Outside reported sex field", "unresolved": "Sex comparison unresolved"},
}
DEFINITION_URL = "https://clinicaltrials.gov/policy/protocol-definitions"
LIMITATION = (
    "Compares reported minimum/maximum age and sex fields only. These are protocol criteria, "
    "not actual participant demographics, full eligibility, enrollment opportunity or a "
    "population-representation measure. Other eligibility text, gender-based criteria, "
    "clinical factors, treatment arms and intervention roles are not assessed."
)


def parse_age_bound(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return {"raw_value": value, "status": "missing", "years": None, "note": "Age bound not reported; not assumed unlimited."}
    if not isinstance(value, str):
        return {"raw_value": value, "status": "invalid", "years": None, "note": "Age bound is not a string."}
    text = " ".join(value.split())
    if text.casefold() in ("n/a", "n/a (no limit)"):
        return {"raw_value": value, "status": "no_limit_reported", "years": None, "note": "Explicit N/A: no numerical limit reported. This describes the source field only."}
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s+Years?", text, re.IGNORECASE)
    if match:
        number = float(match[1])
        if math.isfinite(number):
            return {"raw_value": value, "status": "years", "years": number, "note": "Reported years; compared without unit conversion."}
    if re.fullmatch(r"\d+(?:\.\d+)?\s+(?:Months?|Weeks?|Days?|Hours?|Minutes?)", text, re.IGNORECASE):
        return {"raw_value": value, "status": "unsupported_unit", "years": None, "note": "Non-year unit retained; no approximate conversion applied."}
    return {"raw_value": value, "status": "invalid", "years": None, "note": "Age bound format is unsupported or invalid."}


def compare_age(age_years, minimum, maximum):
    if minimum["status"] == maximum["status"] == "years" and minimum["years"] > maximum["years"]:
        return "unresolved", "Reported minimum age exceeds maximum age; no range comparison applied."
    if age_years is None:
        return "unresolved", "Synthetic age not supplied."
    if minimum["status"] == "years" and age_years < minimum["years"]:
        return "outside", "Synthetic age is below the reported minimum in years."
    if maximum["status"] == "years" and age_years > maximum["years"]:
        return "outside", "Synthetic age is above the reported maximum in years."
    if minimum["status"] in ("years", "no_limit_reported") and maximum["status"] in ("years", "no_limit_reported"):
        return "within", "Synthetic age falls within both reported bounds; numerical boundaries are inclusive."
    return "unresolved", "A bound is missing, invalid or uses a non-year unit; the known bound does not establish an outside result."


def compare_sex(profile_sex, raw_sex):
    source = raw_sex.strip().upper() if isinstance(raw_sex, str) else None
    if profile_sex == "UNSPECIFIED":
        return "unresolved", "Synthetic biological sex not supplied."
    if source not in ("ALL", "FEMALE", "MALE"):
        return "unresolved", "Reported sex field is missing, invalid or unsupported."
    if source == "ALL" or source == profile_sex:
        return "within", "Synthetic sex is included by the reported sex field; gender criteria are not assessed."
    return "outside", "Synthetic sex differs from the reported sex-only field."


def criteria_record(nct_id, raw_study, evidence, profile):
    protocol = _mapping(_mapping(raw_study).get("protocolSection"))
    identification = _mapping(protocol.get("identificationModule"))
    if identification.get("nctId") != nct_id:
        raise CohortSummaryError("Criteria evidence does not match its retained NCT ID.")
    eligibility = _mapping(protocol.get("eligibilityModule"))
    minimum = parse_age_bound(eligibility.get("minimumAge"))
    maximum = parse_age_bound(eligibility.get("maximumAge"))
    age_status, age_note = compare_age(profile["age_years"], minimum, maximum)
    sex_status, sex_note = compare_sex(profile["biological_sex"], eligibility.get("sex"))
    combined = "outside" if "outside" in (age_status, sex_status) else "within" if age_status == sex_status == "within" else "unresolved"
    source_sex = eligibility.get("sex")
    return {
        "nct_id": nct_id, "title": _text(identification.get("briefTitle")) or "Title not reported",
        "study_type": _text(_mapping(protocol.get("designModule")).get("studyType")),
        "status": _text(_mapping(protocol.get("statusModule")).get("overallStatus")),
        "minimum_age": minimum, "maximum_age": maximum, "reported_sex": source_sex,
        "reported_sex_display": source_sex if isinstance(source_sex, str) else json.dumps(source_sex, ensure_ascii=False),
        "gender_based": eligibility.get("genderBased"),
        "gender_description": _text(eligibility.get("genderDescription")),
        "age_result": age_status, "age_note": age_note,
        "sex_result": sex_status, "sex_note": sex_note,
        "combined_result": combined, "combined_label": COMPARISON_LABELS[combined], "evidence": evidence,
    }


def summarize_criteria(summary, profile, aliases=None):
    # Lazy import keeps Patient Lab integration free of an import cycle.
    from .patient_scenarios import validate_scenario
    if aliases is None:
        catalog = load_alias_catalog()
        profile = validate_scenario(profile, catalog)
        aliases = reconcile_drug_aliases(summary, catalog)
    else:
        profile = validate_scenario(profile)
    entity = profile["selected_drug"]
    entry = next(e for e in aliases["catalog_entries"] if e["id"] == entity)
    group = next((g for g in aliases["groups"] if g.get("catalog_entry") and g["catalog_entry"]["id"] == entity), None)
    ids = group["nct_ids"] if group else []
    refs = summary["evidence"]
    snapshots = {s.id: s for s in db.session.scalars(select(TrialSnapshot).where(
        TrialSnapshot.id.in_([refs[nct]["snapshot_id"] for nct in ids])
    ))} if ids else {}
    records = []
    for nct in sorted(ids):
        snapshot = snapshots.get(refs[nct]["snapshot_id"])
        if snapshot is None or snapshot.nct_id != nct:
            raise CohortSummaryError("Missing or mismatched retained criteria snapshot.")
        records.append(criteria_record(nct, snapshot.raw_study, refs[nct], profile))
    groups = {}
    for dimension in ("combined", "age", "sex"):
        labels = COMPARISON_LABELS if dimension == "combined" else DIMENSION_LABELS[dimension]
        rows = []
        for key in ("within", "outside", "unresolved"):
            selected = [r for r in records if r[dimension + "_result"] == key]
            rows.append({"key": key, "label": labels[key], "count": len(selected),
                         "nct_ids": [r["nct_id"] for r in selected],
                         "recruiting_count": sum(r["status"] == "RECRUITING" for r in selected)})
        groups[dimension] = rows
    raw_sex_counts = Counter(
        r["reported_sex"].strip().upper() if isinstance(r["reported_sex"], str) and r["reported_sex"].strip().upper() in ("ALL", "FEMALE", "MALE") else "UNKNOWN"
        for r in records
    )
    result = {
        "method_version": METHOD_VERSION, "cohort": summary["cohort"],
        "selected_drug": {"entity_id": entity, "label": entry["canonical_name"]},
        "profile_fields": {"age_years": profile["age_years"], "biological_sex": profile["biological_sex"]},
        "denominator": len(records), "records": records, "groups": groups,
        "coverage": {
            "minimum_age_status": dict(Counter(r["minimum_age"]["status"] for r in records)),
            "maximum_age_status": dict(Counter(r["maximum_age"]["status"] for r in records)),
            "reported_sex": {key: raw_sex_counts[key] for key in ("ALL", "FEMALE", "MALE", "UNKNOWN")},
            "gender_based_true": sum(r["gender_based"] is True for r in records),
        },
        "alias_catalog_version": aliases["catalog_version"], "alias_catalog_sha256": aliases["catalog_sha256"],
        "source_fields": ["protocolSection.eligibilityModule." + key for key in ("minimumAge", "maximumAge", "sex", "genderBased", "genderDescription")],
        "definition_url": DEFINITION_URL, "limitation": LIMITATION,
    }
    result["report_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return result


def register_criteria_commands(app):
    @app.cli.command("cohort-criteria")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--drug", required=True, help="Curated entity ID, e.g. lenalidomide.")
    @click.option("--age", type=click.FloatRange(0, 130))
    @click.option("--sex", type=click.Choice(["FEMALE", "MALE", "UNSPECIFIED"]), default="UNSPECIFIED")
    @click.option("--json", "json_output", is_flag=True)
    def cohort_criteria(cohort_id, drug, age, sex, json_output):
        """Compare reported age/sex fields for a synthetic profile only."""
        from .patient_scenarios import load_scenario_presets
        try:
            profile = dict(load_scenario_presets()["index"]["interaction-reference"]["profile"])
            profile.update(selected_drug=drug, age_years=age, biological_sex=sex)
            result = summarize_criteria(summarize_cohort(cohort_id), profile)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException("Database unavailable. Check configuration and migrations.") from exc
        if json_output:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
            return
        click.echo("Synthetic Educational Patient Scenario · Reported age/sex criteria")
        click.echo(f"Cohort {cohort_id}: {result['cohort']['condition']} | {result['cohort']['scope']} | COMPLETE")
        click.echo(f"Method: {METHOD_VERSION} | Reference name: {result['selected_drug']['label']}")
        click.echo(f"Studies reporting the selected drug name: {result['denominator']}")
        for dimension, rows in result["groups"].items():
            click.echo(f"\n{dimension.title()} fields:")
            for row in rows:
                click.echo(f"  {row['label']}: {row['count']} | Recruiting records: {row['recruiting_count']}")
        click.echo("\n" + LIMITATION)
