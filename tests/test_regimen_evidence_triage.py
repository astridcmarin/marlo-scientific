"""Synthetic-only tests; no external study verification is performed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from regimen_evidence_triage import analyze


class TriageTests(unittest.TestCase):
    def setUp(self):
        self.queue = {"records": [{"regimen_rank": 1, "raw_group": "Drug A + Drug B", "audit_flags": []}, {"regimen_rank": 2, "raw_group": "C", "audit_flags": []}]}
        self.links = {"links": [{"regimen_rank": 1, "nct_id": "NCT00000001", "link_basis": "test"}]}

    def test_no_evidence_is_not_fetched(self):
        report = analyze(self.queue, self.links, {"records": [], "errors": []})
        self.assertEqual(report["summary"]["regimens_without_study_link"], 1)
        self.assertEqual(report["links"][0]["status"], "not_fetched")

    def test_fetch_error(self):
        ev = {"records": [], "errors": [{"regimen_rank": 1, "nct_id": "NCT00000001", "error": "timeout"}]}
        self.assertEqual(analyze(self.queue, self.links, ev)["links"][0]["status"], "fetch_error")

    def test_offline_fixture_not_primary(self):
        ev = {"records": [{"regimen_rank": 1, "nct_id": "NCT00000001", "source_kind": "offline_fixture", "exact_intervention_name_match": True}], "errors": []}
        self.assertEqual(analyze(self.queue, self.links, ev)["links"][0]["status"], "non_primary_evidence")

    def test_primary_exact_name_requires_arm(self):
        ev = {"records": [{"regimen_rank": 1, "nct_id": "NCT00000001", "source_kind": "clinicaltrials_gov_api_v2", "exact_intervention_name_match": True, "arm_groups": [{"label": "A", "interventionNames": ["Drug X"]}]}], "errors": []}
        self.assertEqual(analyze(self.queue, self.links, ev)["links"][0]["status"], "source_arm_reconciliation_required")

    def test_primary_name_and_arm_still_not_approved(self):
        ev = {"records": [{"regimen_rank": 1, "nct_id": "NCT00000001", "source_kind": "clinicaltrials_gov_api_v2", "exact_intervention_name_match": True, "arm_groups": [{"label": "A", "interventionNames": ["Drug A + Drug B"]}]}], "errors": []}
        row = analyze(self.queue, self.links, ev)["links"][0]
        self.assertEqual(row["status"], "exact_name_and_arm_candidate_for_human_review")
        self.assertFalse(row["reviewer_approval_implied"])

    def test_duplicate_links_not_double_counted(self):
        self.links["links"].append(self.links["links"][0])
        self.assertEqual(analyze(self.queue, self.links, {"records": [], "errors": []})["summary"]["study_links"], 1)

    def test_invalid_link(self):
        self.links["links"][0]["nct_id"] = "BAD"
        self.assertEqual(analyze(self.queue, self.links, {"records": [], "errors": []})["links"][0]["status"], "invalid_nct_id")


if __name__ == "__main__":
    unittest.main()
