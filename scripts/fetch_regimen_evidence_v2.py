#!/usr/bin/env python3
"""Collect primary ClinicalTrials.gov v2 evidence without approving any regimens.

Example:
  python scripts/fetch_regimen_evidence_v2.py \
    --queue intelligence_store/data/curation/regimen_decomposition_review_queue_v4.json \
    --links intelligence_store/data/curation/regimen_trial_links_v5.json \
    --output intelligence_store/data/curation/regimen_api_evidence_v2.json

Use --fixtures PATH for OFFLINE TESTING ONLY. Fixture evidence is never production eligible.
"""
import argparse
import copy
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def normalized(text):
    return re.sub(r"\s+", " ", str(text or "").strip()).casefold()


def fetch_study(nct_id, fixtures=None):
    if not re.fullmatch(r"NCT\d{8}", nct_id):
        raise ValueError("Invalid NCT ID")
    if fixtures:
        payload = json.loads((Path(fixtures) / f"{nct_id}.json").read_text(encoding="utf-8"))
        return payload, "offline_fixture"
    url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "CTI-Regimen-Source-Verification/2.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    return payload, "clinicaltrials_gov_api_v2"


def study_sha256(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def collect(record, nct_id, study, source_kind):
    study = copy.deepcopy(study)
    section = study.get("protocolSection", {})
    found_id = section.get("identificationModule", {}).get("nctId")
    if found_id != nct_id:
        raise ValueError(f"Study identifier mismatch: expected {nct_id}, got {found_id}")
    arms = section.get("armsInterventionsModule", {})
    interventions = arms.get("interventions", [])
    arm_groups = arms.get("armGroups", [])
    exact = [x for x in interventions if normalized(x.get("name")) == normalized(record["raw_group"])]
    return {
        "regimen_rank": record["regimen_rank"],
        "raw_group": record["raw_group"],
        "nct_id": nct_id,
        "source_kind": source_kind,
        "source_url": f"https://clinicaltrials.gov/api/v2/studies/{nct_id}",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_record_sha256": study_sha256(study),
        "source_study": study,
        "source_integrity_version": "retained-study-sha256-v1",
        "study_title": section.get("identificationModule", {}).get("briefTitle"),
        "exact_intervention_name_match": bool(exact),
        "matching_interventions": copy.deepcopy(exact),
        "all_interventions": copy.deepcopy(interventions),
        "arm_groups": copy.deepcopy(arm_groups),
        "evidence_status": "exact_intervention_name_matched" if exact else "requires_manual_source_name_reconciliation",
        "reviewer_decision": "unassessed",
    }


def run(queue, links, fixtures=None):
    index = {r["regimen_rank"]: r for r in queue["records"]}
    evidence, errors = [], []
    cache = {}
    seen = set()
    for link in links["links"]:
        rank, nct_id = link["regimen_rank"], link["nct_id"]
        if (rank, nct_id) in seen:
            continue
        seen.add((rank, nct_id))
        try:
            if rank not in index:
                raise ValueError("Unknown regimen rank")
            if nct_id not in cache:
                cache[nct_id] = fetch_study(nct_id, fixtures)
            payload, kind = cache[nct_id]
            evidence.append(collect(index[rank], nct_id, payload, kind))
        except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
            errors.append({"regimen_rank": rank, "nct_id": nct_id, "error": str(exc)})
    return {
        "schema_version": "regimen-primary-source-evidence-v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "methodology": "Explicit rank/NCT links only. No name-only inference. Offline fixtures cannot qualify for production.",
        "records": evidence,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new output path.")
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    links = json.loads(args.links.read_text(encoding="utf-8"))
    output = run(queue, links, args.fixtures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Evidence records: {len(output['records'])}; errors: {len(output['errors'])}; fixture mode: {bool(args.fixtures)}")

if __name__ == "__main__":
    main()
