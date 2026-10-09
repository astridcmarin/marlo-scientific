#!/usr/bin/env python3
"""Fail-closed regimen approval gate; does not grant approval or alter source files.

Reviewer decisions are separate, explicit, dated records. A matching intervention
label or an existing 'approved' normalization status is NEVER reviewer approval.

Example:
  python scripts/regimen_approval_gate.py \
    --queue intelligence_store/data/curation/regimen_decomposition_review_queue_v4.json \
    --evidence intelligence_store/data/curation/regimen_api_evidence_v2.json \
    --decisions intelligence_store/data/curation/regimen_reviewer_decisions_v1.json \
    --catalog intelligence_store/data/regimen_components_v1.json \
    --report intelligence_store/data/curation/regimen_approval_gate_report_v1.json
"""
import argparse
from fetch_regimen_evidence_v2 import collect, study_sha256
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_TYPES = {"drug", "cell_therapy", "placebo_comparator", "radiation_procedure", "transplant_procedure", "other_procedure", "supportive_intervention"}
SPECIFIC_TYPES = {"drug", "cell_therapy"}
REVIEW_CHECKS = (
    "original_intervention_text_checked", "source_arm_mapping_checked",
    "component_completeness_checked", "product_and_formulation_distinctions_checked",
    "non_drug_interventions_checked", "schedule_and_stage_checked",
)
FORMULATION_HINTS = ("liposom", "pegylat", "gel", "biosimil", "radiolabel", "injection", "doXIL".casefold())


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def date_valid(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed <= datetime.now(timezone.utc)
    except ValueError:
        return False


def source_integrity_errors(record, evidence):
    """Verify retained canonical JSON and every source-derived projection.

    Hashes detect inconsistency; they do not authenticate the origin of a file.
    """
    if not isinstance(evidence, dict):
        return []  # Existing validation reports missing primary evidence.
    study = evidence.get("source_study")
    if not isinstance(study, dict):
        return ["retained_source_study_missing"]
    errors = []
    try:
        if study_sha256(study) != evidence.get("source_record_sha256"):
            errors.append("retained_source_hash_mismatch")
        expected = collect(record, evidence.get("nct_id"), study, evidence.get("source_kind"))
        for field in ("study_title", "matching_interventions", "all_interventions",
                      "arm_groups", "exact_intervention_name_match", "evidence_status", "source_url"):
            if evidence.get(field) != expected[field]:
                errors.append("source_projection_mismatch:" + field)
    except (ValueError, TypeError, AttributeError, KeyError):
        errors.append("retained_source_structure_invalid")
    return errors


def validate_record(record, decision, evidence):
    errors = source_integrity_errors(record, evidence)
    def need(test, code):
        if not test:
            errors.append(code)

    need(decision.get("reviewer_decision") == "approved", "explicit_reviewer_approval_missing")
    need(isinstance(decision.get("reviewer_name"), str) and bool(decision.get("reviewer_name", "").strip()), "reviewer_name_missing")
    need(date_valid(decision.get("reviewed_at")), "valid_dated_review_missing")
    need(decision.get("regimen_rank") == record.get("regimen_rank"), "regimen_rank_mismatch")
    need(norm(decision.get("raw_group")) == norm(record.get("raw_group")), "raw_group_mismatch")
    need(re.fullmatch(r"NCT\d{8}", str(decision.get("source_nct_id", ""))) is not None, "nct_id_invalid")
    need(isinstance(decision.get("reviewer_notes"), str) and bool(decision.get("reviewer_notes", "").strip()), "reviewer_rationale_missing")

    checks = decision.get("review_checks") or {}
    if not isinstance(checks, dict):
        errors.append("review_checks_invalid")
        checks = {}
    for check in REVIEW_CHECKS:
        need(checks.get(check) is True, f"review_check_missing:{check}")

    components = decision.get("components")
    need(isinstance(components, list) and len(components) > 0, "components_missing")
    if isinstance(components, list):
        for i, component in enumerate(components):
            if not isinstance(component, dict):
                errors.append(f"component_{i}:invalid_record")
                continue
            kind = component.get("component_type")
            need(kind in ALLOWED_TYPES, f"component_{i}:invalid_type")
            need(isinstance(component.get("name"), str) and bool(component["name"].strip()), f"component_{i}:name_missing")
            if kind in SPECIFIC_TYPES:
                need(component.get("product_identity_verified") is True, f"component_{i}:identity_not_verified")
                need(isinstance(component.get("canonical"), str) and bool(component["canonical"].strip()), f"component_{i}:canonical_missing")
            if kind not in SPECIFIC_TYPES:
                need(component.get("canonical") in (None, ""), f"component_{i}:non_drug_must_not_be_drug_canonical")
            if kind == "placebo_comparator":
                need(norm(component.get("name")) == "placebo", f"component_{i}:placebo_label_invalid")

    flags = set(record.get("audit_flags", []))
    resolutions = decision.get("audit_flag_resolutions") or {}
    need(isinstance(resolutions, dict), "audit_resolutions_invalid")
    if isinstance(resolutions, dict):
        for flag in sorted(flags):
            resolution = resolutions.get(flag, {})
            need(isinstance(resolution, dict) and resolution.get("status") == "resolved" and bool(str(resolution.get("rationale", "")).strip()), f"audit_flag_not_resolved:{flag}")
        need(set(resolutions) == flags, "audit_flag_set_mismatch")

    arm_label = decision.get("arm_label")
    need(isinstance(arm_label, str) and bool(arm_label.strip()), "arm_label_missing")
    if record.get("decomposition_type") == "multi_arm_comparison":
        permitted = {a.get("arm_id") for a in record.get("comparison_arms", [])}
        need(decision.get("arm_id") in permitted, "multi_arm_id_missing_or_invalid")
    else:
        need(decision.get("arm_id") in (None, ""), "single_arm_record_cannot_have_comparison_arm_id")

    need(isinstance(evidence, dict), "primary_evidence_missing")
    if isinstance(evidence, dict):
        need(evidence.get("source_kind") == "clinicaltrials_gov_api_v2", "official_api_evidence_required")
        need(evidence.get("nct_id") == decision.get("source_nct_id"), "source_nct_id_mismatch")
        need(evidence.get("regimen_rank") == record.get("regimen_rank"), "source_rank_mismatch")
        need(norm(evidence.get("raw_group")) == norm(record.get("raw_group")), "source_raw_group_mismatch")
        need(bool(re.fullmatch(r"[a-f0-9]{64}", str(evidence.get("source_record_sha256", "")))), "source_sha256_missing")
        need(evidence.get("source_record_sha256") == decision.get("source_record_sha256"), "review_not_bound_to_source_hash")
        need(date_valid(evidence.get("retrieved_at_utc")), "source_retrieval_date_missing")
        if date_valid(evidence.get("retrieved_at_utc")) and date_valid(decision.get("reviewed_at")):
            reviewed_time = datetime.fromisoformat(decision["reviewed_at"].replace("Z", "+00:00"))
            source_time = datetime.fromisoformat(evidence["retrieved_at_utc"].replace("Z", "+00:00"))
            need(reviewed_time >= source_time, "review_predates_source_evidence")
        matches = evidence.get("matching_interventions") or []
        exact = [i for i in matches if norm(i.get("name")) == norm(record.get("raw_group"))]
        need(bool(exact) and evidence.get("exact_intervention_name_match") is True, "exact_source_intervention_match_required")
        arm_matches = [a for a in (evidence.get("arm_groups") or []) if norm(a.get("label")) == norm(arm_label)]
        need(bool(arm_matches), "source_arm_not_found")
        if arm_matches:
            source_intervention_names = [norm(n) for a in arm_matches for n in a.get("interventionNames", [])]
            need(norm(record.get("raw_group")) in source_intervention_names, "source_intervention_not_associated_with_arm")

    if any(x in norm(record.get("raw_group")) for x in FORMULATION_HINTS):
        need(bool(str(decision.get("formulation_notes", "")).strip()), "formulation_notes_required")

    if not errors:
        return [], {
            "regimen_rank": record["regimen_rank"],
            "raw_group": record["raw_group"],
            "arm_id": decision.get("arm_id"),
            "arm_label": arm_label,
            "components": components,
            "source_trial_ids": [decision["source_nct_id"]],
            "evidence_references": [{
                "source_url": evidence["source_url"],
                "source_record_sha256": evidence["source_record_sha256"],
                "retrieved_at_utc": evidence["retrieved_at_utc"],
                "source_kind": evidence["source_kind"],
            }],
            "reviewer_decision": "approved",
            "reviewer_name": decision["reviewer_name"],
            "reviewed_at": decision["reviewed_at"],
            "reviewer_notes": decision["reviewer_notes"],
            "formulation_notes": decision.get("formulation_notes"),
            "audit_flag_resolutions": resolutions,
        }
    return sorted(set(errors)), None


def run_gate(queue, evidence_doc, decisions_doc):
    records = queue.get("records", [])
    index = {r["regimen_rank"]: r for r in records}
    evidence_records = evidence_doc.get("records", [])
    evidence_counts = Counter((r.get("regimen_rank"), r.get("nct_id")) for r in evidence_records)
    queue_counts = Counter(r["regimen_rank"] for r in records)
    evidence_index = {(r.get("regimen_rank"), r.get("nct_id")): r for r in evidence_records}
    entries, rejected, seen, duplicated = [], [], set(), set()
    for decision in decisions_doc.get("records", []):
        rank = decision.get("regimen_rank")
        key = (rank, decision.get("arm_id") or "", norm(decision.get("arm_label")))
        if key in seen:
            duplicated.add(key)
            rejected.append({"regimen_rank": rank, "arm_id": key[1], "errors": ["duplicate_decision_key"]})
            continue
        seen.add(key)
        if rank not in index:
            rejected.append({"regimen_rank": rank, "errors": ["unknown_regimen_rank"]})
            continue
        if queue_counts[rank] > 1:
            rejected.append({"regimen_rank": rank, "errors": ["duplicate_queue_rank"]})
            continue
        if evidence_counts[(rank, decision.get("source_nct_id"))] > 1:
            rejected.append({"regimen_rank": rank, "errors": ["duplicate_evidence_key"]})
            continue
        record = index[rank]
        evidence = evidence_index.get((rank, decision.get("source_nct_id")))
        errors, entry = validate_record(record, decision, evidence)
        if errors:
            rejected.append({"regimen_rank": rank, "arm_id": decision.get("arm_id"), "errors": errors})
        else:
            entries.append(entry)

    # Duplicate decisions fail closed, including a previously valid decision.
    if duplicated:
        entries = [e for e in entries if (e["regimen_rank"], e.get("arm_id") or "", norm(e["arm_label"])) not in duplicated]

    # Multiple submitted arm labels for a single-arm regimen also fail closed.
    submitted_counts = Counter(d.get("regimen_rank") for d in decisions_doc.get("records", []) if d.get("regimen_rank") in index and index[d["regimen_rank"]].get("decomposition_type") != "multi_arm_comparison")
    for rank, count in submitted_counts.items():
        if count > 1:
            entries = [e for e in entries if e["regimen_rank"] != rank]
            rejected.append({"regimen_rank": rank, "errors": ["single_arm_multiple_decisions"]})

    # A multi-arm comparison must not be partially exported. Require all defined arms.
    for record in records:
        if record.get("decomposition_type") != "multi_arm_comparison":
            continue
        rank = record["regimen_rank"]
        expected = {a.get("arm_id") for a in record.get("comparison_arms", [])}
        actual = {e["arm_id"] for e in entries if e["regimen_rank"] == rank}
        if actual and actual != expected:
            entries = [e for e in entries if e["regimen_rank"] != rank]
            rejected.append({"regimen_rank": rank, "errors": ["multi_arm_comparison_requires_all_arms"]})

    entries.sort(key=lambda e: (e["regimen_rank"], e.get("arm_id") or ""))
    approved_ranks = {e["regimen_rank"] for e in entries}
    report = {
        "schema_version": "regimen-approval-gate-report-v1",
        "source_integrity_version": "retained-study-sha256-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_regimens": len(records),
        "submitted_decisions": len(decisions_doc.get("records", [])),
        "exported_entries": len(entries),
        "production_approved_regimens": len(approved_ranks),
        "unassessed_or_not_approved_regimens": len(records) - len(approved_ranks),
        "blocked_decisions": rejected,
        "error_counts": dict(Counter(e for r in rejected for e in r["errors"])),
        "policy": "No automated approval; only explicitly approved and independently source-verified reviewer records export.",
    }
    catalog = {
        "schema_version": "regimen-components-v1",
        "catalog_version": "1.0.0",
        "catalog_status": "approved_only" if entries else "empty_no_approved_regimens",
        "source_review_queue": "regimen_decomposition_review_queue_v4.json",
        "entry_policy": report["policy"],
        "entries": entries,
    }
    return catalog, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("queue", "evidence", "decisions", "catalog", "report"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.catalog.resolve() == args.report.resolve():
        parser.error("Catalog and report must use different output paths.")
    if args.catalog.exists() or args.report.exists():
        parser.error("Output already exists; choose new staging catalog and report paths.")
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    catalog, report = run_gate(queue, evidence, decisions)
    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.catalog.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(catalog, indent=2, ensure_ascii=False))
    with args.report.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Approved regimen ranks: {report['production_approved_regimens']} | exported entries: {report['exported_entries']} | blocked decisions: {len(report['blocked_decisions'])}")

if __name__ == "__main__":
    main()
