"""Offline tests for the regimen approval gate. Synthetic evidence is test-only."""
import copy
import hashlib
import json
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from datetime import datetime, timedelta, timezone

from regimen_approval_gate import run_gate
from fetch_regimen_evidence_v2 import collect

NOW = datetime.now(timezone.utc)
RETRIEVED = (NOW - timedelta(hours=2)).isoformat()
REVIEWED = (NOW - timedelta(hours=1)).isoformat()


def example(multi=False):
    raw = "Drug A and Placebo"
    record = {"regimen_rank": 10, "raw_group": raw, "audit_flags": ["placebo_or_control_not_in_proposed_components", "source_level_review_pending"]}
    if multi:
        record["decomposition_type"] = "multi_arm_comparison"
        record["comparison_arms"] = [{"arm_id": "A"}, {"arm_id": "B"}]
    study = {"protocolSection": {
        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Synthetic study"},
        "armsInterventionsModule": {
            "interventions": [{"name": raw, "type": "DRUG", "armGroupLabels": ["Arm A", "Arm B"]}],
            "armGroups": [
                {"label": "Arm A", "type": "EXPERIMENTAL", "interventionNames": [raw]},
                {"label": "Arm B", "type": "ACTIVE_COMPARATOR", "interventionNames": [raw]},
            ],
        },
    }}
    evidence = collect(record, "NCT00000001", study, "clinicaltrials_gov_api_v2")
    evidence["retrieved_at_utc"] = RETRIEVED
    decision = {
        "regimen_rank": 10, "raw_group": raw, "source_nct_id": "NCT00000001",
        "source_record_sha256": evidence["source_record_sha256"],
        "arm_label": "Arm A", "arm_id": "A" if multi else None,
        "reviewer_decision": "approved", "reviewer_name": "Test Reviewer", "reviewed_at": REVIEWED,
        "reviewer_notes": "All source intervention and component details verified against synthetic study.",
        "review_checks": {
            "original_intervention_text_checked": True, "source_arm_mapping_checked": True,
            "component_completeness_checked": True, "product_and_formulation_distinctions_checked": True,
            "non_drug_interventions_checked": True, "schedule_and_stage_checked": True,
        },
        "audit_flag_resolutions": {
            flag: {"status": "resolved", "rationale": "Independently reviewed and reconciled in synthetic test"}
            for flag in record["audit_flags"]
        },
        "components": [
            {"name": "Drug A", "component_type": "drug", "canonical": "Drug A", "product_identity_verified": True},
            {"name": "placebo", "component_type": "placebo_comparator", "canonical": None},
        ],
    }
    return record, evidence, decision


def run(records, evidence, decisions):
    return run_gate({"records": records}, {"records": evidence}, {"records": decisions})


class GateTests(unittest.TestCase):
    def test_no_decisions_empty(self):
        r, e, d = example()
        catalog, report = run([r], [e], [])
        self.assertEqual(catalog["entries"], [])
        self.assertEqual(report["production_approved_regimens"], 0)

    def test_approved_synthetic_primary_shaped_evidence(self):
        r, e, d = example()
        catalog, report = run([r], [e], [d])
        self.assertEqual(report["production_approved_regimens"], 1)
        self.assertEqual(catalog["entries"][0]["components"][1]["component_type"], "placebo_comparator")

    def test_fixture_never_approved(self):
        r, e, d = example()
        e["source_kind"] = "offline_fixture"
        _, report = run([r], [e], [d])
        self.assertIn("official_api_evidence_required", report["error_counts"])

    def test_missing_review_blocks(self):
        r, e, d = example()
        d["reviewer_decision"] = "unassessed"
        _, report = run([r], [e], [d])
        self.assertIn("explicit_reviewer_approval_missing", report["error_counts"])

    def test_unresolved_audit_flag_blocks(self):
        r, e, d = example()
        d["audit_flag_resolutions"].pop("source_level_review_pending")
        _, report = run([r], [e], [d])
        self.assertIn("audit_flag_not_resolved:source_level_review_pending", report["error_counts"])

    def test_hash_binding_blocks(self):
        r, e, d = example()
        d["source_record_sha256"] = "0" * 64
        _, report = run([r], [e], [d])
        self.assertIn("review_not_bound_to_source_hash", report["error_counts"])

    def test_missing_arm_association_blocks(self):
        r, e, d = example()
        e["arm_groups"][0]["interventionNames"] = ["Something else"]
        _, report = run([r], [e], [d])
        self.assertIn("source_intervention_not_associated_with_arm", report["error_counts"])

    def test_ambiguous_drug_identity_blocks(self):
        r, e, d = example()
        d["components"][0]["product_identity_verified"] = False
        _, report = run([r], [e], [d])
        self.assertIn("component_0:identity_not_verified", report["error_counts"])

    def test_review_before_evidence_blocks(self):
        r, e, d = example()
        d["reviewed_at"] = (NOW - timedelta(hours=3)).isoformat()
        _, report = run([r], [e], [d])
        self.assertIn("review_predates_source_evidence", report["error_counts"])

    def test_multiarm_requires_both_arms(self):
        r, e, d = example(multi=True)
        _, report = run([r], [e], [d])
        self.assertEqual(report["exported_entries"], 0)
        self.assertIn("multi_arm_comparison_requires_all_arms", report["error_counts"])
        d2 = copy.deepcopy(d)
        d2["arm_id"] = "B"
        d2["arm_label"] = "Arm B"
        catalog, report = run([r], [e], [d, d2])
        self.assertEqual(report["exported_entries"], 2)
        self.assertEqual(report["production_approved_regimens"], 1)

    def test_duplicate_decision_blocks_all(self):
        r, e, d = example()
        _, report = run([r], [e], [d, copy.deepcopy(d)])
        self.assertEqual(report["exported_entries"], 0)
        self.assertIn("duplicate_decision_key", report["error_counts"])

    def test_second_arm_on_single_arm_blocks(self):
        r, e, d = example()
        d2 = copy.deepcopy(d)
        d2["arm_label"] = "Arm B"
        _, report = run([r], [e], [d, d2])
        self.assertEqual(report["exported_entries"], 0)
        self.assertIn("single_arm_multiple_decisions", report["error_counts"])

    def test_qualifier_notes_required(self):
        r, e, d = example()
        r["raw_group"] = "Drug A gel and Placebo"
        e["raw_group"] = r["raw_group"]
        e["matching_interventions"][0]["name"] = r["raw_group"]
        e["arm_groups"][0]["interventionNames"] = [r["raw_group"]]
        d["raw_group"] = r["raw_group"]
        _, report = run([r], [e], [d])
        self.assertIn("formulation_notes_required", report["error_counts"])

if __name__ == "__main__":
    unittest.main()
