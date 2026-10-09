"""Reported stopping reasons from complete cohorts; no inferred causes."""

from collections import Counter, defaultdict
import hashlib
import json

import click
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import TrialSnapshot
from .normalization import _mapping, _text
from .summaries import CohortSummaryError, summarize_cohort

METHOD_VERSION = "stopping-reasons-v1.0"
STOPPING_STATUSES = ("TERMINATED", "WITHDRAWN", "SUSPENDED")
SOURCE_PATHS = [
    "protocolSection.statusModule.overallStatus",
    "protocolSection.statusModule.whyStopped",
]
DEFINITION_URL = "https://clinicaltrials.gov/policy/protocol-definitions"
TEMPLATE_URL = "https://cdn.clinicaltrials.gov/documents/Interventional_Study_Protocol_Registration_Template_Jan_2018.pdf"
GROUPING_RULE = "Complete reason text, grouped by capitalization and whitespace only. Punctuation, wording and combined explanations remain distinct."
LIMITATION = (
    "Reported status and stopping text describe the retained registry record. "
    "They do not establish clinical failure, safety causality, lack of efficacy or a prediction for another study. "
    "Reasons are not assigned inferred clinical categories. Missing or invalid text stays unknown."
)


def reason_key(text):
    return (
        "text:" + hashlib.sha256(" ".join(text.split()).casefold().encode()).hexdigest()
    )


def variant_key(text):
    return "raw:" + hashlib.sha256(text.encode()).hexdigest()


def stopping_record(nct_id, raw_study, evidence):
    protocol = _mapping(_mapping(raw_study).get("protocolSection"))
    identification = _mapping(protocol.get("identificationModule"))
    if identification.get("nctId") != nct_id:
        raise CohortSummaryError(
            "Stopping evidence does not match its retained NCT ID."
        )
    status = _mapping(protocol.get("statusModule"))
    reason = status.get("whyStopped")
    if _text(reason) is not None:
        coverage = "reported"
    elif reason is None or isinstance(reason, str):
        coverage = "missing"
    else:
        coverage = "invalid"
    return {
        "nct_id": nct_id,
        "title": _text(identification.get("briefTitle")) or "Title not reported",
        "status": _text(status.get("overallStatus")),
        "study_type": _text(_mapping(protocol.get("designModule")).get("studyType")),
        "lead_sponsor": _text(
            _mapping(
                _mapping(protocol.get("sponsorCollaboratorsModule")).get("leadSponsor")
            ).get("name")
        ),
        "reason": reason if coverage == "reported" else None,
        "reason_coverage": coverage,
        "reason_key": reason_key(reason) if coverage == "reported" else None,
        "variant_key": variant_key(reason) if coverage == "reported" else None,
        "evidence": dict(evidence),
    }


def summarize_stopping(cohort_id, status="TERMINATED"):
    if status not in (*STOPPING_STATUSES, "ALL"):
        raise ValueError("Choose TERMINATED, WITHDRAWN, SUSPENDED or ALL.")
    summary = summarize_cohort(cohort_id)
    snapshots = db.session.scalars(
        select(TrialSnapshot).where(
            TrialSnapshot.id.in_(
                [ref["snapshot_id"] for ref in summary["evidence"].values()]
            )
        )
    )
    by_id = {s.id: s for s in snapshots}
    all_records = []
    for nct_id, reference in sorted(summary["evidence"].items()):
        snapshot = by_id.get(reference["snapshot_id"])
        if snapshot is None or snapshot.nct_id != nct_id:
            raise CohortSummaryError(
                "A stopping record has missing or mismatched retained evidence."
            )
        all_records.append(stopping_record(nct_id, snapshot.raw_study, reference))
    selected_statuses = STOPPING_STATUSES if status == "ALL" else (status,)
    records = [r for r in all_records if r["status"] in selected_statuses]
    coverage = Counter(r["reason_coverage"] for r in records)
    groups = defaultdict(list)
    for record in records:
        if record["reason_key"] is not None:
            groups[record["reason_key"]].append(record)
    reasons = []
    for key, members in groups.items():
        variants = defaultdict(set)
        for record in members:
            variants[record["reason"]].add(record["nct_id"])
        variants = [
            {
                "text": text,
                "key": variant_key(text),
                "count": len(ids),
                "nct_ids": sorted(ids),
            }
            for text, ids in sorted(variants.items(), key=lambda p: (-len(p[1]), p[0]))
        ]
        reasons.append(
            {
                "key": key,
                "label": " ".join(variants[0]["text"].split()),
                "count": len(members),
                "nct_ids": sorted(r["nct_id"] for r in members),
                "variants": variants,
            }
        )
    reasons.sort(key=lambda r: (-r["count"], r["label"], r["key"]))
    outside = [
        r
        for r in all_records
        if r["status"] not in STOPPING_STATUSES and r["reason_coverage"] == "reported"
    ]
    return {
        "cohort": summary["cohort"],
        "method_version": METHOD_VERSION,
        "status_scope": status,
        "selected_statuses": list(selected_statuses),
        "total_trials": len(all_records),
        "selected_trials": len(records),
        "reported_reasons": coverage["reported"],
        "unknown_reasons": coverage["missing"] + coverage["invalid"],
        "missing_reasons": coverage["missing"],
        "invalid_reasons": coverage["invalid"],
        "status_counts": [
            {
                "status": name,
                "count": sum(r["status"] == name for r in all_records),
                "nct_ids": [r["nct_id"] for r in all_records if r["status"] == name],
            }
            for name in STOPPING_STATUSES
        ],
        "outside_status_with_reason": {"count": len(outside), "records": outside},
        "reason_group_count": len(reasons),
        "reasons": reasons,
        "records": records,
        "source_paths": list(SOURCE_PATHS),
        "grouping_rule": GROUPING_RULE,
        "limitation": LIMITATION,
        "definition_url": DEFINITION_URL,
        "template_url": TEMPLATE_URL,
    }


def register_stopping_commands(app):
    @app.cli.command("cohort-stopping")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option(
        "--status",
        type=click.Choice([*STOPPING_STATUSES, "ALL"]),
        default="TERMINATED",
        show_default=True,
    )
    @click.option("--top", type=click.IntRange(1, 100), default=10, show_default=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_stopping(cohort_id, status, top, json_output):
        """Summarize reported stopping text without inferred cause labels."""
        try:
            report = summarize_stopping(cohort_id, status)
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
        click.echo(f"Method: {METHOD_VERSION} | Selected stopping status: {status}")
        for key, label in (
            ("total_trials", "Saved trials"),
            ("selected_trials", "Trials in selected stopping status"),
            ("reported_reasons", "Nonblank reported reasons"),
            ("unknown_reasons", "Missing or invalid reasons"),
            ("invalid_reasons", "Invalid reason values"),
            ("reason_group_count", "Formatting-only reason groups"),
        ):
            click.echo(f"{label}: {report[key]}")
        click.echo("\nStopping statuses (whole cohort):")
        for row in report["status_counts"]:
            click.echo(f"  {row['status']}: {row['count']}")
        click.echo("\nReported reason groups:")
        for row in report["reasons"][:top]:
            click.echo(f"  {row['count']}: {row['label']}")
        if not report["reasons"]:
            click.echo("  No reported reason text in the selected records.")
        if len(report["reasons"]) > top:
            click.echo(f"  Showing top {top} of {report['reason_group_count']} groups")
        click.echo(
            f"\nRecords with reason text outside the three stopping statuses: {report['outside_status_with_reason']['count']} (excluded)"
        )
        click.echo(GROUPING_RULE)
        click.echo(LIMITATION)
