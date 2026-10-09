#!/usr/bin/env python3
"""Offline triage of explicit ClinicalTrials.gov links and fetched API evidence.

Never changes a reviewer decision or marks a regimen production-approved.
Run after the source collector, or before it to see outstanding work.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def analyze(queue, links, evidence):
    records = queue.get("records", [])
    indexed = {r.get("regimen_rank"): r for r in records}
    fetched = {}
    for item in evidence.get("records", []):
        key = (item.get("regimen_rank"), item.get("nct_id"))
        fetched.setdefault(key, []).append(item)
    errors = {}
    for item in evidence.get("errors", []):
        key = (item.get("regimen_rank"), item.get("nct_id"))
        errors.setdefault(key, []).append(str(item.get("error", "unspecified_error")))

    rows, seen = [], set()
    for link in links.get("links", []):
        rank, nct = link.get("regimen_rank"), link.get("nct_id")
        key = (rank, nct)
        if key in seen:
            continue
        seen.add(key)
        record = indexed.get(rank)
        candidates = fetched.get(key, [])
        issue_codes = []
        if not record:
            status = "invalid_regimen_rank"
            issue_codes.append("regimen_not_in_review_queue")
        elif not isinstance(nct, str) or re.fullmatch(r"NCT\d{8}", nct) is None:
            status = "invalid_nct_id"
            issue_codes.append("invalid_nct_id")
        elif len(candidates) > 1:
            status = "duplicate_evidence_records"
            issue_codes.append("duplicate_evidence_records")
        elif not candidates:
            status = "fetch_error" if key in errors else "not_fetched"
            if key in errors:
                issue_codes.append("api_fetch_failed")
        else:
            ev = candidates[0]
            if ev.get("source_kind") != "clinicaltrials_gov_api_v2":
                status = "non_primary_evidence"
                issue_codes.append("official_api_evidence_missing")
            elif not ev.get("exact_intervention_name_match"):
                status = "source_name_reconciliation_required"
                issue_codes.append("exact_intervention_label_not_found")
            else:
                # An exact intervention name does NOT establish correct arm assignment.
                matching_arms = [a.get("label") for a in ev.get("arm_groups", [])
                                 if norm(record["raw_group"]) in [norm(n) for n in a.get("interventionNames", [])]]
                if matching_arms:
                    status = "exact_name_and_arm_candidate_for_human_review"
                else:
                    status = "source_arm_reconciliation_required"
                    issue_codes.append("intervention_not_associated_with_arm")
        rows.append({
            "regimen_rank": rank,
            "raw_group": record.get("raw_group") if record else None,
            "nct_id": nct,
            "status": status,
            "linked_study_evidence_basis": link.get("link_basis"),
            "primary_api_verified_at_link_creation": link.get("primary_api_verified", False),
            "audit_flags": record.get("audit_flags", []) if record else [],
            "fetch_errors": errors.get(key, []),
            "issue_codes": issue_codes,
            "reviewer_approval_implied": False,
        })

    linked_ranks = {r["regimen_rank"] for r in rows if r["regimen_rank"] in indexed}
    status_counts = dict(sorted(Counter(r["status"] for r in rows).items()))
    return {
        "schema_version": "regimen-evidence-triage-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_queue_schema_version": queue.get("schema_version"),
        "summary": {
            "total_regimens": len(records),
            "linked_regimen_ranks": len(linked_ranks),
            "study_links": len(rows),
            "regimens_without_study_link": len(records) - len(linked_ranks),
            "statuses": status_counts,
            "api_evidence_records_in_input": len(evidence.get("records", [])),
            "api_fetch_errors_in_input": len(evidence.get("errors", [])),
            "human_approved_regimens": None,
        },
        "policy": "Diagnostic only. Exact intervention/arm association is a candidate for manual review, not regimen approval.",
        "links": rows,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("queue", "links", "evidence", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    args = p.parse_args()
    docs = [json.loads(getattr(args, x).read_text(encoding="utf-8")) for x in ("queue", "links", "evidence")]
    report = analyze(*docs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Study links:", report["summary"]["study_links"])
    print("Statuses:", json.dumps(report["summary"]["statuses"], sort_keys=True))
    print("Output:", args.output)


if __name__ == "__main__":
    main()
