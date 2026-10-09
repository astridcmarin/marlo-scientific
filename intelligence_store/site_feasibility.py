"""Frozen location evidence and explicitly assumed population scenarios."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlparse

import click
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import TrialSnapshot
from .normalization import _mapping, _text
from .summaries import CohortSummaryError, summarize_cohort

METHOD_VERSION = "frozen-location-evidence-v1.0"
POOL_METHOD = "assumed-patient-pool-v1.0"
CATALOG_PATH = Path(__file__).parent / "data" / "patient_pool_reference_v1.json"
CATALOG_SHA256 = "a1c34c2b6de9a7c6407abf065b3d88d6c7ace7f43d5241de4c898ce55986df7e"
UNKNOWN = "Not reported"
LOCATION_FIELDS = ("facility", "city", "state", "zip", "country", "status")
STATES = ("RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED",
    "TERMINATED", "WITHDRAWN", "SUSPENDED", "ENROLLING_BY_INVITATION")
MODES = ("us_reference", "synthetic_crude_prevalence", "user_reference_crude_prevalence")
POOL_FIELDS = {"mode", "country", "state", "population", "prevalence_per_100000",
    "eligible_pct", "eligible_low_pct", "eligible_high_pct", "access_pct", "rate_basis",
    "population_year", "prevalence_year", "population_source", "prevalence_source"}
LIMITATION = (
    "Registered locations describe listed research activity, not site capacity, "
    "performance, confirmed competition or patients available for enrollment. "
    "Location recruitment status and overall trial status are separate source fields. "
    "Patient-pool outputs are explicit assumption scenarios; no individual eligibility, "
    "catchment, referral, consent, enrollment rate or site ranking is inferred."
)


class FeasibilityError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def name_key(value):
    text = _text(value)
    return " ".join(text.split()).casefold() if text else ""


def load_pool_reference(path=CATALOG_PATH):
    try:
        content = Path(path).read_bytes()
        if hashlib.sha256(content).hexdigest() != CATALOG_SHA256:
            raise ValueError("Changed reference")
        return {**json.loads(content), "sha256": CATALOG_SHA256}
    except (OSError, ValueError, TypeError) as exc:
        raise FeasibilityError("Patient-pool reference is missing or changed. Restore patient_pool_reference_v1.json; location evidence remains available.") from exc


def summarize_locations(summary):
    refs = summary["evidence"]
    snapshots = {s.id: s for s in db.session.scalars(select(TrialSnapshot).where(
        TrialSnapshot.id.in_([r["snapshot_id"] for r in refs.values()]))) } if refs else {}
    rows, trials = [], []
    for nct, ref in sorted(refs.items()):
        snapshot = snapshots.get(ref["snapshot_id"])
        if snapshot is None or snapshot.nct_id != nct:
            raise CohortSummaryError("Missing or mismatched retained location snapshot.")
        protocol = _mapping(_mapping(snapshot.raw_study).get("protocolSection"))
        ident = _mapping(protocol.get("identificationModule"))
        if _text(ident.get("nctId")) != nct:
            raise CohortSummaryError("Retained location source ID does not match cohort membership.")
        locations = _mapping(protocol.get("contactsLocationsModule")).get("locations")
        list_status = "missing" if locations is None else "invalid" if not isinstance(locations, list) else "empty" if not locations else "listed"
        overall = _text(_mapping(protocol.get("statusModule")).get("overallStatus"))
        trial_rows, invalid = [], 0
        for index, item in enumerate(locations if isinstance(locations, list) else []):
            if not isinstance(item, dict):
                invalid += 1
                continue
            normalized = {k: _text(item.get(k)) for k in LOCATION_FIELDS}
            site_status = "_".join(normalized["status"].upper().split()) if normalized["status"] else None
            site_status = site_status if site_status in STATES else None
            row = {"id": f"{nct}:{index}", "nct_id": nct, "source_index": index,
                "title": _text(ident.get("briefTitle")), "overall_status": overall,
                "study_type": _text(_mapping(protocol.get("designModule")).get("studyType")),
                **normalized, "raw_fields": {k: item.get(k) for k in LOCATION_FIELDS},
                "location_status": site_status, "evidence": ref}
            row["country_key"], row["state_key"] = name_key(row["country"]), name_key(row["state"])
            row["facility_key"] = digest([name_key(row[k]) for k in ("country", "state", "city", "zip", "facility")]) if row["facility"] else None
            rows.append(row)
            trial_rows.append(row)
        trials.append({"nct_id": nct, "title": _text(ident.get("briefTitle")),
            "overall_status": overall, "list_status": list_status, "location_count": len(trial_rows),
            "invalid_location_entries": invalid, "has_country": any(r["country"] for r in trial_rows),
            "has_recruiting_location": any(r["location_status"] == "RECRUITING" for r in trial_rows),
            "evidence": ref})
    country_buckets = defaultdict(list)
    for row in rows:
        country_buckets[row["country_key"]].append(row)
    countries = []
    for key, items in country_buckets.items():
        variants = sorted({r["country"] for r in items if r["country"]})
        countries.append({"key": key, "label": variants[0] if variants else UNKNOWN, "variants": variants,
            **location_metrics(items)})
    countries.sort(key=lambda x: (-x["trial_count"], x["label"]))
    coverage = {"list_status": dict(Counter(t["list_status"] for t in trials)),
        "trials_without_location_objects": sum(t["location_count"] == 0 for t in trials),
        "trials_without_country": sum(not t["has_country"] for t in trials),
        "invalid_location_entries": sum(t["invalid_location_entries"] for t in trials),
        "location_fields_missing": {k: sum(not r[k] for r in rows) for k in LOCATION_FIELDS},
        "unresolved_location_status": sum(r["location_status"] is None for r in rows),
        "recruiting_location_overall_not_recruiting": sum(r["location_status"] == "RECRUITING" and r["overall_status"] != "RECRUITING" for r in rows)}
    report = {"method_version": METHOD_VERSION, "cohort": summary["cohort"],
        "total_trials": len(trials), "rows": rows, "trials": trials, "countries": countries,
        "metrics": location_metrics(rows), "coverage": coverage,
        "source_fields": ["protocolSection.contactsLocationsModule.locations[]." + k for k in LOCATION_FIELDS],
        "limitation": LIMITATION}
    report["report_sha256"] = digest(report)
    return report


def location_metrics(rows):
    return {"location_records": len(rows), "trial_count": len({r["nct_id"] for r in rows}),
        "overall_recruiting_trials": len({r["nct_id"] for r in rows if r["overall_status"] == "RECRUITING"}),
        "recruiting_location_records": sum(r["location_status"] == "RECRUITING" for r in rows),
        "trials_with_recruiting_locations": len({r["nct_id"] for r in rows if r["location_status"] == "RECRUITING"}),
        "facility_descriptor_groups": len({r["facility_key"] for r in rows if r["facility_key"]})}


def region_rows(report, country, state=""):
    return [r for r in report["rows"] if r["country_key"] == name_key(country)
        and (not state or r["state_key"] == name_key(state))]


def facility_groups(rows):
    buckets = defaultdict(list)
    for row in rows:
        if row["facility_key"]:
            buckets[row["facility_key"]].append(row)
    groups = [{"key": key, "facility": items[0]["facility"], "city": items[0]["city"],
        "state": items[0]["state"], "country": items[0]["country"], "zip": items[0]["zip"],
        "variants": sorted({r["facility"] for r in items}), **location_metrics(items)} for key, items in buckets.items()]
    return sorted(groups, key=lambda x: (-x["trial_count"], x["facility"]))


def _number(value, label, maximum):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise FeasibilityError(f"{label} must be a finite number or blank.")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise FeasibilityError(f"{label} must be a finite number or blank.") from exc
    if not math.isfinite(result) or not 0 <= result <= maximum:
        raise FeasibilityError(f"{label} is outside the supported input range.")
    return result


def validate_pool_inputs(inputs):
    if not isinstance(inputs, dict) or set(inputs) != POOL_FIELDS:
        raise FeasibilityError("Population scenario has missing or unsupported fields.")
    if inputs["mode"] not in MODES or inputs["rate_basis"] != "crude_prevalence":
        raise FeasibilityError("Use a supported mode and a crude prevalence basis. Incidence and age-adjusted rates are not accepted.")
    result = dict(inputs)
    for key in ("country", "state", "population_source", "prevalence_source"):
        if not isinstance(result[key], str) or len(result[key]) > (500 if "source" in key else 160):
            raise FeasibilityError("Geography and source fields must be bounded text.")
        result[key] = " ".join(result[key].split())
    if not result["country"]:
        raise FeasibilityError("Choose a named country; the unreported-country group cannot define a population.")
    for key, maximum in (("population", 1e10), ("prevalence_per_100000", 100000),
        ("eligible_pct", 100), ("eligible_low_pct", 100), ("eligible_high_pct", 100), ("access_pct", 100)):
        result[key] = _number(result[key], key.replace("_", " ").title(), maximum)
    for key in ("population_year", "prevalence_year"):
        value = _number(result[key], key.replace("_", " ").title(), 2100)
        if value is not None and (value < 1900 or int(value) != value):
            raise FeasibilityError("Reference years must be whole years from 1900–2100.")
        result[key] = int(value) if value is not None else None
    low, central, high = (result[k] for k in ("eligible_low_pct", "eligible_pct", "eligible_high_pct"))
    if (low is None) != (high is None):
        raise FeasibilityError("Supply both eligibility range endpoints or leave both blank.")
    if low is not None and (central is None or not low <= central <= high):
        raise FeasibilityError("Eligibility assumptions must satisfy low ≤ central ≤ high.")
    if result["mode"] == "us_reference" and any(result[k] not in (None, "") for k in (
        "population", "prevalence_per_100000", "population_year", "prevalence_year", "population_source", "prevalence_source")):
        raise FeasibilityError("The U.S. reference mode uses its pinned data; clear custom population and source inputs or choose a custom mode.")
    if result["mode"] == "user_reference_crude_prevalence":
        for key in ("population_source", "prevalence_source"):
            parsed = urlparse(result[key])
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise FeasibilityError("User-reported references require two HTTP(S) source URLs.")
        if result["population_year"] is None or result["prevalence_year"] is None or result["population_year"] != result["prevalence_year"]:
            raise FeasibilityError("User-reported references require matching population and prevalence years; source comparability remains your responsibility.")
    return result


def empty_pool_inputs(country="United States", state=""):
    return {"mode": "us_reference", "country": country, "state": state,
        "population": None, "prevalence_per_100000": None, "eligible_pct": None,
        "eligible_low_pct": None, "eligible_high_pct": None, "access_pct": None,
        "rate_basis": "crude_prevalence", "population_year": None, "prevalence_year": None,
        "population_source": "", "prevalence_source": ""}


def calculate_patient_pool(condition, inputs):
    inputs = validate_pool_inputs(inputs)
    reference = None
    if inputs["mode"] == "us_reference":
        reference = load_pool_reference()
        if name_key(condition) not in {name_key(v) for v in reference["compatible_cohort_condition_names"]} or name_key(inputs["country"]) != name_key(reference["country"]) or inputs["state"]:
            raise FeasibilityError("The bundled myeloma reference applies only to the United States as a whole. Other conditions, states and countries need their own custom crude-prevalence inputs.")
        population, pool = reference["population"], reference["condition_pool"]
        basis = "Pinned estimated disease prevalence count plus a dated population denominator. Derived ratios are illustrative, not a published SEER rate."
    else:
        population, rate = inputs["population"], inputs["prevalence_per_100000"]
        pool = population * rate / 100000 if population is not None and rate is not None else None
        basis = "Entirely synthetic population and crude-prevalence assumptions." if inputs["mode"] == "synthetic_crude_prevalence" else "User-reported references, not independently verified by the app; population/rate scope and comparability require review."
    eligible = pool * inputs["eligible_pct"] / 100 if pool is not None and inputs["eligible_pct"] is not None else None
    accessible = eligible * inputs["access_pct"] / 100 if eligible is not None and inputs["access_pct"] is not None else None
    bounds = None
    if pool is not None and inputs["eligible_low_pct"] is not None:
        low, high = (pool * inputs[k] / 100 for k in ("eligible_low_pct", "eligible_high_pct"))
        bounds = {"eligible_low": low, "eligible_high": high,
            "accessible_low": low * inputs["access_pct"] / 100 if inputs["access_pct"] is not None else None,
            "accessible_high": high * inputs["access_pct"] / 100 if inputs["access_pct"] is not None else None}
    result = {"method_version": POOL_METHOD, "purpose": "educational_population_scenario",
        "condition_context": condition, "inputs": inputs, "reference": reference, "basis": basis,
        "population": population, "condition_pool": pool, "assumed_eligible_pool": eligible,
        "assumed_accessible_pool": accessible, "sensitivity_range": bounds,
        "density_per_100000": {"condition_proxy": pool / population * 100000 if pool is not None and population else None,
            "assumed_eligible": eligible / population * 100000 if eligible is not None and population else None,
            "assumed_accessible": accessible / population * 100000 if accessible is not None and population else None},
        "status": "calculated" if accessible is not None else "incomplete",
        "equations": ["Condition pool = population × crude prevalence per 100000 / 100000 (custom modes); reference mode uses its published count directly.",
            "Assumed eligible pool = condition pool × eligibility share / 100.",
            "Assumed accessible pool = assumed eligible pool × accessibility share / 100.",
            "Derived density = modeled pool / population × 100000; undefined at zero population."],
        "limitation": LIMITATION + " Sensitivity endpoints vary only the eligibility assumption; they are not confidence intervals. No site allocation or current-year projection is performed."}
    result["report_sha256"] = digest(result)
    return result


def register_feasibility_commands(app):
    @app.cli.command("cohort-sites")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--country", default=None)
    @click.option("--state", default="")
    @click.option("--json", "json_output", is_flag=True)
    def cohort_sites(cohort_id, country, state, json_output):
        """Describe listed locations in retained cohort evidence."""
        if state and not country:
            raise click.UsageError("A state filter requires --country.")
        try:
            report = summarize_locations(summarize_cohort(cohort_id))
        except (ValueError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc) if isinstance(exc, ValueError) else "Database unavailable.") from exc
        if country is not None:
            rows = region_rows(report, country, state)
            report = {"method_version": METHOD_VERSION, "cohort": report["cohort"],
                "country": country, "state": state, "metrics": location_metrics(rows), "rows": rows,
                "limitation": LIMITATION}
            report["report_sha256"] = digest(report)
        if json_output:
            click.echo(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
            return
        click.echo(f"Cohort {cohort_id}: {report['cohort']['condition']} | COMPLETE")
        click.echo(f"Method: {METHOD_VERSION}")
        for key, value in report["metrics"].items():
            click.echo(f"{key.replace('_', ' ').title()}: {value}")
        if country is None:
            click.echo(f"Trials without listed country: {report['coverage']['trials_without_country']}")
        click.echo(LIMITATION)

    @app.cli.command("patient-pool-demo")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--eligible", type=float, required=True)
    @click.option("--accessible", type=float, required=True)
    @click.option("--low", type=float)
    @click.option("--high", type=float)
    @click.option("--json", "json_output", is_flag=True)
    def patient_pool_demo(cohort_id, eligible, accessible, low, high, json_output):
        """U.S. myeloma reference with explicitly chosen eligibility/access assumptions."""
        try:
            summary = summarize_cohort(cohort_id)
            inputs = {**empty_pool_inputs(), "eligible_pct": eligible, "access_pct": accessible,
                "eligible_low_pct": low, "eligible_high_pct": high}
            result = calculate_patient_pool(summary["cohort"]["condition"], inputs)
        except (ValueError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc) if isinstance(exc, ValueError) else "Database unavailable.") from exc
        if json_output:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
            return
        click.echo(f"U.S. myeloma population scenario | Reference year: 2023 | Method: {POOL_METHOD}")
        click.echo(f"Referenced disease pool: {result['condition_pool']:,}")
        click.echo(f"Assumed eligible pool: {result['assumed_eligible_pool']:,.1f}")
        click.echo(f"Assumed accessible pool: {result['assumed_accessible_pool']:,.1f}")
        click.echo("Assumed shares are not measured eligibility or enrollment findings. No site-level forecast is generated.")
