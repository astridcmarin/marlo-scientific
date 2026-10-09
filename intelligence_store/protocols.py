"""Descriptive protocol profiles and an explicitly unvalidated structural heuristic."""

from collections import Counter
import hashlib
import json

import click
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import TrialSnapshot
from .normalization import _mapping, _text
from .summaries import CohortSummaryError, summarize_cohort

METHOD_VERSION = "protocol-structure-v1.0"
DEFINITION_URL = "https://clinicaltrials.gov/policy/protocol-definitions"
RULES = (
    {
        "key": "arms",
        "label": "Reported arms",
        "threshold": 3,
        "unit": "entries",
        "source_paths": ["protocolSection.armsInterventionsModule.armGroups"],
        "note": "Counts listed arm entries, not distinct intervention combinations.",
    },
    {
        "key": "outcomes",
        "label": "Primary + secondary outcomes",
        "threshold": 10,
        "unit": "entries",
        "source_paths": [
            "protocolSection.outcomesModule.primaryOutcomes",
            "protocolSection.outcomesModule.secondaryOutcomes",
        ],
        "note": "Counts reported entries, not unique endpoints, procedures or visits. Both lists must be present and valid.",
    },
    {
        "key": "eligibility",
        "label": "Eligibility text length",
        "threshold": 3000,
        "unit": "characters",
        "source_paths": ["protocolSection.eligibilityModule.eligibilityCriteria"],
        "note": "Counts Unicode characters after trimming outer whitespace. Formatting and language affect length; this does not measure eligibility restrictiveness.",
    },
    {
        "key": "locations",
        "label": "Listed locations",
        "threshold": 20,
        "unit": "entries",
        "source_paths": ["protocolSection.contactsLocationsModule.locations"],
        "note": "Counts listed records without deduplication, not confirmed active sites or site workload.",
    },
    {
        "key": "enrollment",
        "label": "Recorded enrollment",
        "threshold": 200,
        "unit": "participants",
        "source_paths": ["protocolSection.designModule.enrollmentInfo.count"],
        "note": "Uses the recorded count. Actual and estimated enrollment remain labeled separately; this is not a recruitment forecast.",
    },
)
RULES_SHA256 = hashlib.sha256(
    json.dumps(RULES, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
LIMITATION = (
    "Unvalidated structural heuristic: five author-selected thresholds with equal weights. "
    "This is not a measure of protocol quality, clinical risk, patient burden, feasibility or regulatory compliance. "
    "Missing values are unknown, not zero; only interventional records are assessed."
)


def _list_count(module, key, fields):
    if key not in module or module[key] is None:
        return None, "Not reported"
    records = module[key]
    if not isinstance(records, list) or any(
        not isinstance(record, dict)
        or not any(_text(record.get(field)) for field in fields)
        for record in records
    ):
        return None, "Invalid reported list or entry"
    return len(records), None


def protocol_profile(nct_id, raw_study, evidence):
    protocol = _mapping(_mapping(raw_study).get("protocolSection"))
    identification = _mapping(protocol.get("identificationModule"))
    if identification.get("nctId") != nct_id:
        raise CohortSummaryError(
            "Protocol evidence does not match its retained NCT ID."
        )
    design = _mapping(protocol.get("designModule"))
    outcomes = _mapping(protocol.get("outcomesModule"))
    arms, arms_reason = _list_count(
        _mapping(protocol.get("armsInterventionsModule")), "armGroups", ("label",)
    )
    primary, primary_reason = _list_count(outcomes, "primaryOutcomes", ("measure",))
    secondary, secondary_reason = _list_count(
        outcomes, "secondaryOutcomes", ("measure",)
    )
    outcome_count = (
        primary + secondary if primary is not None and secondary is not None else None
    )
    outcome_reason = (
        "; ".join(
            f"{name}: {reason}"
            for name, reason in (
                ("Primary", primary_reason),
                ("Secondary", secondary_reason),
            )
            if reason
        )
        or None
    )
    criteria = _text(
        _mapping(protocol.get("eligibilityModule")).get("eligibilityCriteria")
    )
    eligibility_count = len(criteria) if criteria else None
    locations, location_reason = _list_count(
        _mapping(protocol.get("contactsLocationsModule")),
        "locations",
        ("facility", "city", "country"),
    )
    enrollment_info = _mapping(design.get("enrollmentInfo"))
    enrollment = enrollment_info.get("count")
    enrollment_reason = None
    if enrollment is None:
        enrollment_reason = "Not reported"
    elif type(enrollment) is not int or enrollment < 0:
        enrollment, enrollment_reason = None, "Invalid recorded enrollment"
    values = {
        "arms": (arms, arms_reason),
        "outcomes": (outcome_count, outcome_reason),
        "eligibility": (
            eligibility_count,
            None if criteria else "Not reported or empty",
        ),
        "locations": (locations, location_reason),
        "enrollment": (enrollment, enrollment_reason),
    }
    study_type = _text(design.get("studyType"))
    assessed = study_type == "INTERVENTIONAL"
    indicators = []
    for rule in RULES:
        value, reason = values[rule["key"]]
        met = value >= rule["threshold"] if assessed and value is not None else None
        state = (
            "not_assessed"
            if not assessed
            else "unknown" if value is None else "met" if met else "not_met"
        )
        indicators.append(
            {
                **rule,
                "value": value,
                "missing_reason": reason,
                "state": state,
                "contribution": int(met) if met is not None else None,
            }
        )
    known = sum(indicator["contribution"] is not None for indicator in indicators)
    met_count = sum(indicator["contribution"] or 0 for indicator in indicators)
    complete = assessed and known == len(RULES)
    design_info = _mapping(design.get("designInfo"))
    eligibility = _mapping(protocol.get("eligibilityModule"))
    return {
        "nct_id": nct_id,
        "title": _text(identification.get("briefTitle")) or "Title not reported",
        "study_type": study_type,
        "status": _text(_mapping(protocol.get("statusModule")).get("overallStatus")),
        "assessment_status": (
            "complete" if complete else "partial" if assessed else "not_assessed"
        ),
        "scope_reason": (
            None
            if assessed
            else (
                "Study type not reported"
                if not study_type
                else "Heuristic applies to interventional records only"
            )
        ),
        "thresholds_met": met_count if assessed else None,
        "known_indicators": known if assessed else 0,
        "total_indicators": len(RULES),
        "score": met_count if complete else None,
        "possible_range": (
            [met_count, met_count + len(RULES) - known] if assessed else None
        ),
        "indicators": indicators,
        "primary_outcomes": primary,
        "secondary_outcomes": secondary,
        "enrollment_type": _text(enrollment_info.get("type")),
        "design": {
            "allocation": _text(design_info.get("allocation")),
            "intervention_model": _text(design_info.get("interventionModel")),
            "masking": _text(_mapping(design_info.get("maskingInfo")).get("masking")),
            "primary_purpose": _text(design_info.get("primaryPurpose")),
            "sex": _text(eligibility.get("sex")),
            "minimum_age": _text(eligibility.get("minimumAge")),
            "maximum_age": _text(eligibility.get("maximumAge")),
        },
        "evidence": dict(evidence),
    }


def summarize_protocols(cohort_id):
    # Existing summary validation enforces complete, consistent frozen membership.
    summary = summarize_cohort(cohort_id)
    snapshots = db.session.scalars(
        select(TrialSnapshot).where(
            TrialSnapshot.id.in_(
                [ref["snapshot_id"] for ref in summary["evidence"].values()]
            )
        )
    )
    by_id = {snapshot.id: snapshot for snapshot in snapshots}
    profiles = []
    for nct_id, reference in sorted(summary["evidence"].items()):
        snapshot = by_id.get(reference["snapshot_id"])
        if snapshot is None or snapshot.nct_id != nct_id:
            raise CohortSummaryError(
                "A protocol profile has missing or mismatched retained evidence."
            )
        profiles.append(protocol_profile(nct_id, snapshot.raw_study, reference))
    counts = Counter(profile["assessment_status"] for profile in profiles)
    coverage = []
    for rule in RULES:
        states = {state: [] for state in ("met", "not_met", "unknown", "not_assessed")}
        for profile in profiles:
            indicator = next(
                i for i in profile["indicators"] if i["key"] == rule["key"]
            )
            states[indicator["state"]].append(profile["nct_id"])
        coverage.append(
            {
                **rule,
                **{
                    state: {"count": len(ids), "nct_ids": ids}
                    for state, ids in states.items()
                },
            }
        )
    return {
        "cohort": summary["cohort"],
        "method_version": METHOD_VERSION,
        "rules_sha256": RULES_SHA256,
        "rules": list(RULES),
        "limitation": LIMITATION,
        "definition_url": DEFINITION_URL,
        "total_trials": len(profiles),
        "interventional_trials": counts["complete"] + counts["partial"],
        "complete_profiles": counts["complete"],
        "partial_profiles": counts["partial"],
        "not_assessed": counts["not_assessed"],
        "coverage": coverage,
        "score_distribution": [
            {"score": score, "count": len(ids), "nct_ids": ids}
            for score in range(len(RULES) + 1)
            for ids in [[p["nct_id"] for p in profiles if p["score"] == score]]
        ],
        "profiles": profiles,
    }


def register_protocol_commands(app):
    @app.cli.command("cohort-protocols")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_protocols(cohort_id, json_output):
        """Describe saved protocol structure with missing data kept unknown."""
        try:
            report = summarize_protocols(cohort_id)
        except CohortSummaryError as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException(
                "Database unavailable. Check configuration and migrations."
            ) from exc
        if json_output:
            click.echo(json.dumps(report, indent=2, ensure_ascii=False))
            return
        click.echo(
            f"Cohort {cohort_id}: {report['cohort']['condition']} | {report['cohort']['scope']} | COMPLETE"
        )
        click.echo(f"Method: {METHOD_VERSION} | Rules SHA256: {RULES_SHA256}")
        for key, label in (
            ("total_trials", "Saved trials"),
            ("interventional_trials", "Interventional trials"),
            ("complete_profiles", "All five indicators known"),
            ("partial_profiles", "Interventional profiles with missing indicators"),
            ("not_assessed", "Outside assessment scope"),
        ):
            click.echo(f"{label}: {report[key]}")
        click.echo("\nThresholds (interventional denominator):")
        for row in report["coverage"]:
            click.echo(
                f"  {row['label']} >= {row['threshold']} {row['unit']}: met {row['met']['count']}; below {row['not_met']['count']}; unknown {row['unknown']['count']}"
            )
        click.echo("\nThreshold counts for complete profiles only:")
        for row in report["score_distribution"]:
            click.echo(f"  {row['score']}/5: {row['count']}")
        click.echo("\n" + LIMITATION)
