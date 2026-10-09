"""Factual regulatory-field evidence from retained registry records."""
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re

import click
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import TrialSnapshot
from .normalization import _mapping, _text
from .summaries import CohortSummaryError, summarize_cohort

METHOD_VERSION = "frozen-regulatory-evidence-v1.0"
REFERENCE_PATH = Path(__file__).parent / "data" / "regulatory_reference_v1.json"
REFERENCE_SHA256 = "f907d3d4283d51e714d2b9f756e0c2611cba3bb8ab299c1fb6183fa1a4d978d2"
OVERSIGHT_FIELDS = {
    "isFdaRegulatedDrug": "FDA-regulated drug product",
    "isFdaRegulatedDevice": "FDA-regulated device product",
    "isUnapprovedDevice": "Device not approved / cleared flag",
    "oversightHasDmc": "Data monitoring committee",
    "isPpsd": "Pediatric postmarket device surveillance",
    "isUsExport": "Product manufactured in / exported from U.S.",
    "fdaaa801Violation": "Reported FDAAA 801 violation indicator",
}
RESULT_LABELS = {
    "posted": "Posted-results evidence",
    "waived": "Waiver flag reported; no posting signal",
    "submitted": "Submission / QC signal; no final posting signal",
    "no_posted": "Explicit no-results flag; no posting signal",
    "unknown": "Results availability unresolved",
}
REVIEW_LABELS = {
    "conflicting_results": "Conflicting results-availability signals",
    "timeline_order": "Reported timeline order needs review",
    "actual_completion_no_posting": "Actual primary completion; no posted-results signal",
    "invalid_fields": "Selected field formats need review",
    "reported_violation": "Registry reports FDAAA 801 violation indicator",
}
EVENTS = [
    ("start", "Study start", "protocolSection.statusModule.startDateStruct", True),
    ("primary_completion", "Primary completion", "protocolSection.statusModule.primaryCompletionDateStruct", True),
    ("completion", "Study completion", "protocolSection.statusModule.completionDateStruct", True),
    ("study_submitted", "Study first submitted", "protocolSection.statusModule.studyFirstSubmitDate", False),
    ("study_qc", "Study first submitted meeting QC criteria", "protocolSection.statusModule.studyFirstSubmitQcDate", False),
    ("study_posted", "Study first posted", "protocolSection.statusModule.studyFirstPostDateStruct", True),
    ("results_submitted", "Results first submitted", "protocolSection.statusModule.resultsFirstSubmitDate", False),
    ("results_qc", "Results first submitted meeting QC criteria", "protocolSection.statusModule.resultsFirstSubmitQcDate", False),
    ("results_posted", "Results first posted", "protocolSection.statusModule.resultsFirstPostDateStruct", True),
    ("pending_results_submitted", "Submission tracking: estimated first results submission", "derivedSection.miscInfoModule.submissionTracking.estimatedResultsFirstSubmitDate", False),
    ("qc_comments_posted", "First results posting with QC comments", "derivedSection.miscInfoModule.submissionTracking.firstMcpInfo.postDateStruct", True),
    ("cert_extension_submitted", "Certification / Extension first submitted", "protocolSection.statusModule.dispFirstSubmitDate", False),
    ("cert_extension_posted", "Certification / Extension first posted", "protocolSection.statusModule.dispFirstPostDateStruct", True),
    ("last_update_submitted", "Last update submitted", "protocolSection.statusModule.lastUpdateSubmitDate", False),
    ("last_update_posted", "Last update posted", "protocolSection.statusModule.lastUpdatePostDateStruct", True),
]
BOOL_STATES = ("yes", "no", "unreported", "invalid")
LIMITATION = (
    "Registry-field evidence, not a legal compliance, reporting-deadline, ACT, IND/IDE "
    "or product-approval determination. Missing values remain unknown. Review signals "
    "identify source evidence for human examination; they are not findings of lateness, "
    "violation, product safety or enrollment opportunity."
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def load_regulatory_reference(path=REFERENCE_PATH):
    try:
        content = Path(path).read_bytes()
        if hashlib.sha256(content).hexdigest() != REFERENCE_SHA256:
            raise ValueError("Changed field reference")
        return {**json.loads(content), "sha256": REFERENCE_SHA256}
    except (OSError, ValueError, TypeError) as exc:
        raise CohortSummaryError("Regulatory field reference is missing or changed; restore regulatory_reference_v1.json from Step 18.") from exc


def boolean_field(value):
    state = "yes" if value is True else "no" if value is False else "unreported" if value is None else "invalid"
    return {"raw_value": value, "value": value if isinstance(value, bool) else None,
        "state": state, "label": {"yes": "Yes", "no": "No", "unreported": "Not reported", "invalid": "Invalid / unrecognized"}[state]}


def _path(value, path):
    for component in path.split("."):
        value = _mapping(value).get(component)
    return value


def date_field(value, structured=False):
    original = value
    raw = _mapping(value).get("date") if structured else value
    raw_type = _mapping(value).get("type") if structured else None
    state, precision = "missing", None
    if raw is not None and raw != "":
        state = "invalid"
        if isinstance(raw, str):
            match = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", raw)
            if match:
                try:
                    year, month, day = (int(x) if x else None for x in match.groups())
                    date(year, month if month is not None else 1, day if day is not None else 1)  # Validation only; not exported or used as an imputed date.
                    state, precision = "valid", "day" if day is not None else "month" if month is not None else "year"
                except ValueError:
                    pass
    if structured and value is not None and not isinstance(value, dict):
        state = "invalid"
    type_state = "unreported" if raw_type is None else "valid" if raw_type in ("ACTUAL", "ESTIMATED") else "invalid"
    return {"raw_value": original, "raw_date": raw, "date_type": raw_type,
        "state": state, "precision": precision, "type_state": type_state,
        "exact_arithmetic_supported": state == "valid" and precision == "day" and raw_type != "ESTIMATED" and type_state != "invalid"}


def elapsed_days(start, end):
    if not start["exact_arithmetic_supported"] or not end["exact_arithmetic_supported"]:
        return {"days": None, "state": "unresolved", "note": "Requires valid full-day dates without estimated or invalid date types."}
    number = (date.fromisoformat(end["raw_date"]) - date.fromisoformat(start["raw_date"])).days
    if number < 0:
        return {"days": None, "state": "order_issue", "note": "Reported end precedes reported start; no negative duration presented as elapsed time."}
    return {"days": number, "state": "calculated", "note": "Calendar-day difference between reported full dates. An unreported date type is retained as unreported; no legal deadline or QC performance judgment is applied."}


def regulatory_record(nct, raw, evidence):
    protocol = _mapping(_mapping(raw).get("protocolSection"))
    ident = _mapping(protocol.get("identificationModule"))
    if _text(ident.get("nctId")) != nct or not re.fullmatch(r"NCT\d{8}", nct):
        raise CohortSummaryError("Retained regulatory source ID does not match cohort membership.")
    status, oversight = _mapping(protocol.get("statusModule")), _mapping(protocol.get("oversightModule"))
    flags = {key: {"field_label": label, "source_path": "protocolSection.oversightModule." + key,
        **boolean_field(oversight.get(key))} for key, label in OVERSIGHT_FIELDS.items()}
    events = {key: {"label": label, "source_path": path + (".date" if struct else ""),
        **date_field(_path(raw, path), struct)} for key, label, path, struct in EVENTS}
    results_flag, waiver = boolean_field(_mapping(raw).get("hasResults")), boolean_field(status.get("resultsWaived"))
    section = _mapping(raw).get("resultsSection")
    section_state = "missing" if section is None else "invalid" if not isinstance(section, dict) else "present" if section else "empty"
    posting_signals = []
    if results_flag["value"] is True:
        posting_signals.append("hasResults is explicitly true")
    if events["results_posted"]["state"] == "valid":
        posting_signals.append("A valid results first-posted date is reported")
    if section_state == "present":
        posting_signals.append("A nonempty resultsSection object is retained (content not validated)")
    submission_signals = [events[key]["label"] for key in ("results_submitted", "results_qc", "pending_results_submitted", "qc_comments_posted") if events[key]["state"] == "valid"]
    bucket = "posted" if posting_signals else "waived" if waiver["value"] is True else "submitted" if submission_signals else "no_posted" if results_flag["value"] is False else "unknown"
    intervals = {}
    for key, label, first, last in (
        ("study_submission_to_posting", "Study first submission → first posting", "study_submitted", "study_posted"),
        ("results_submission_to_posting", "Results first submission → first posting", "results_submitted", "results_posted"),
        ("last_update_to_posting", "Last update submission → posting", "last_update_submitted", "last_update_posted")):
        intervals[key] = {"label": label, **elapsed_days(events[first], events[last])}
    chronology = []
    for first, last in (("study_submitted", "study_qc"), ("study_qc", "study_posted"),
        ("results_submitted", "results_qc"), ("results_qc", "results_posted"),
        ("cert_extension_submitted", "cert_extension_posted")):
        if elapsed_days(events[first], events[last])["state"] == "order_issue":
            chronology.append({"from": first, "to": last})
    ea = _mapping(status.get("expandedAccessInfo"))
    linked_id = _text(ea.get("nctId"))
    study_type = _text(_mapping(protocol.get("designModule")).get("studyType"))
    expanded = {"has_expanded_access": boolean_field(ea.get("hasExpandedAccess")),
        "raw_linked_nct_id": ea.get("nctId"), "linked_nct_id": linked_id if linked_id and re.fullmatch(r"NCT\d{8}", linked_id) else None,
        "linked_status": ea.get("statusForNctId"), "study_is_expanded_access": study_type == "EXPANDED_ACCESS",
        "types": {key: boolean_field(_mapping(_mapping(protocol.get("designModule")).get("expandedAccessTypes")).get(key)) for key in ("individual", "intermediate", "treatment")}}
    doc_module = _mapping(_mapping(_mapping(raw).get("documentSection")).get("largeDocumentModule"))
    docs = doc_module.get("largeDocs")
    doc_list_state = "missing" if docs is None else "invalid" if not isinstance(docs, list) else "listed" if docs else "empty"
    documents, invalid_docs = [], 0
    for index, item in enumerate(docs if isinstance(docs, list) else []):
        if not isinstance(item, dict):
            invalid_docs += 1
            continue
        documents.append({"source_index": index, "type_abbreviation": item.get("typeAbbrev"),
            "label": item.get("label"), "filename": item.get("filename"), "date": date_field(item.get("date")),
            "upload_date": item.get("uploadDate"), "size_bytes": item.get("size"),
            "has_protocol": boolean_field(item.get("hasProtocol")), "has_sap": boolean_field(item.get("hasSap")),
            "has_icf": boolean_field(item.get("hasIcf"))})
    reviews = []
    if posting_signals and results_flag["value"] is False:
        reviews.append("conflicting_results")
    if chronology or any(value["state"] == "order_issue" for value in intervals.values()):
        reviews.append("timeline_order")
    if events["primary_completion"]["state"] == "valid" and events["primary_completion"]["date_type"] == "ACTUAL" and not posting_signals:
        reviews.append("actual_completion_no_posting")
    if any(f["state"] == "invalid" for f in [*flags.values(), results_flag, waiver]) or any(e["state"] == "invalid" or e["type_state"] == "invalid" for e in events.values()) or section_state == "invalid" or doc_list_state == "invalid" or invalid_docs:
        reviews.append("invalid_fields")
    if flags["fdaaa801Violation"]["value"] is True:
        reviews.append("reported_violation")
    return {"nct_id": nct, "title": _text(ident.get("briefTitle")), "status": _text(status.get("overallStatus")),
        "study_type": study_type, "flags": flags, "timeline": events, "intervals": intervals,
        "chronology_pairs": chronology, "results": {"bucket": bucket, "label": RESULT_LABELS[bucket],
            "has_results": results_flag, "waived": waiver, "section_state": section_state,
            "section_module_names": sorted(section) if isinstance(section, dict) else [],
            "posting_signals": posting_signals, "submission_signals": submission_signals},
        "certification_extension_signal": any(events[k]["state"] == "valid" for k in ("cert_extension_submitted", "cert_extension_posted")),
        "expanded_access": expanded, "documents": documents, "document_list_state": doc_list_state,
        "invalid_document_entries": invalid_docs, "no_sap_flag": boolean_field(doc_module.get("noSap")),
        "review_keys": reviews, "evidence": evidence}


def summarize_regulatory(summary):
    reference = load_regulatory_reference()
    refs = summary["evidence"]
    snapshots = {s.id: s for s in db.session.scalars(select(TrialSnapshot).where(
        TrialSnapshot.id.in_([r["snapshot_id"] for r in refs.values()]))) } if refs else {}
    records = []
    for nct, evidence in sorted(refs.items()):
        snapshot = snapshots.get(evidence["snapshot_id"])
        if snapshot is None or snapshot.nct_id != nct:
            raise CohortSummaryError("Missing or mismatched retained regulatory snapshot.")
        records.append(regulatory_record(nct, snapshot.raw_study, evidence))
    def group(items, predicate):
        selected = [r for r in items if predicate(r)]
        return {"count": len(selected), "nct_ids": [r["nct_id"] for r in selected]}
    ea_records = [r for r in records if r["study_type"] == "EXPANDED_ACCESS"]
    flag_groups = {key: {"label": label, "denominator": len(records),
        "groups": {state: group(records, lambda r, k=key, s=state: r["flags"][k]["state"] == s) for state in BOOL_STATES}}
        for key, label in OVERSIGHT_FIELDS.items()}
    results = {key: {"label": label, **group(records, lambda r, k=key: r["results"]["bucket"] == k)} for key, label in RESULT_LABELS.items()}
    review_groups = {key: {"label": label, **group(records, lambda r, k=key: k in r["review_keys"])} for key, label in REVIEW_LABELS.items()}
    metrics = {"posted_results_signal": results["posted"], "certification_extension_signal": group(records, lambda r: r["certification_extension_signal"]),
        "listed_documents": group(records, lambda r: bool(r["documents"])),
        "expanded_access_available_flag": group(records, lambda r: r["expanded_access"]["has_expanded_access"]["value"] is True),
        "any_review_signal": group(records, lambda r: bool(r["review_keys"]))}
    report = {"method_version": METHOD_VERSION, "cohort": summary["cohort"], "denominator": len(records),
        "records": records, "oversight": flag_groups, "results_groups": results, "review_groups": review_groups,
        "metrics": metrics, "timeline_coverage": {key: {"label": label,
            "states": dict(Counter(r["timeline"][key]["state"] for r in records)),
            "precision": dict(Counter(r["timeline"][key]["precision"] or "unknown" for r in records))} for key, label, _path, _struct in EVENTS},
        "expanded_access_groups": {state: group(records, lambda r, s=state: r["expanded_access"]["has_expanded_access"]["state"] == s) for state in BOOL_STATES},
        "expanded_access_type_denominator": len(ea_records),
        "expanded_access_types": {key: {state: group(ea_records, lambda r, k=key, s=state: r["expanded_access"]["types"][k]["state"] == s) for state in BOOL_STATES} for key in ("individual", "intermediate", "treatment")},
        "document_counts": {"metadata_objects": sum(len(r["documents"]) for r in records),
            "invalid_entries": sum(r["invalid_document_entries"] for r in records),
            "listed_protocol_flags": group(records, lambda r: any(d["has_protocol"]["value"] is True for d in r["documents"])),
            "listed_sap_flags": group(records, lambda r: any(d["has_sap"]["value"] is True for d in r["documents"])),
            "listed_icf_flags": group(records, lambda r: any(d["has_icf"]["value"] is True for d in r["documents"]))},
        "reference": reference, "limitation": LIMITATION}
    report["report_sha256"] = digest(report)
    return report


def register_regulatory_commands(app):
    @app.cli.command("cohort-regulatory")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_regulatory(cohort_id, json_output):
        """Inspect FDA fields and reporting evidence without judging legal compliance."""
        try:
            report = summarize_regulatory(summarize_cohort(cohort_id))
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException("Database unavailable. Check configuration and migrations.") from exc
        if json_output:
            click.echo(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
            return
        click.echo(f"Cohort {cohort_id}: {report['cohort']['condition']} | COMPLETE")
        click.echo(f"Method: {METHOD_VERSION} | Saved studies: {report['denominator']}")
        for key, row in report["results_groups"].items():
            click.echo(f"{row['label']}: {row['count']}")
        for key, row in report["oversight"].items():
            click.echo(f"{row['label']}: " + "; ".join(f"{state}={row['groups'][state]['count']}" for state in BOOL_STATES))
        click.echo(f"Studies with document metadata: {report['metrics']['listed_documents']['count']}")
        click.echo(f"Studies with any human-review signal: {report['metrics']['any_review_signal']['count']}")
        click.echo(LIMITATION)
