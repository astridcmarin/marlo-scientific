"""Synthetic offline integrity checks. No production decisions or API calls."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
from test_regimen_approval_gate import example, run
from fetch_regimen_evidence_v2 import collect, study_sha256

class SourceIntegrityTests(unittest.TestCase):
    def blocked(self, r, evidence, d, error):
        catalog, report = run([r], evidence, [d])
        self.assertEqual(catalog['entries'], [])
        self.assertIn(error, report['error_counts'])

    def test_snapshot_is_independent_of_input_and_projections(self):
        r, e, d = example()
        original = copy.deepcopy(e['source_study'])
        again = collect(r, e['nct_id'], original, 'offline_fixture')
        original['protocolSection']['identificationModule']['briefTitle'] = 'changed'
        again['arm_groups'][0]['label'] = 'edited projection'
        self.assertEqual(study_sha256(again['source_study']), again['source_record_sha256'])
        self.assertEqual(again['source_study']['protocolSection']['armsInterventionsModule']['armGroups'][0]['label'], 'Arm A')

    def test_missing_snapshot_blocks_legacy_evidence(self):
        r, e, d = example(); e.pop('source_study')
        self.blocked(r, [e], d, 'retained_source_study_missing')

    def test_modified_source_blocks(self):
        r, e, d = example(); e['source_study']['protocolSection']['identificationModule']['briefTitle'] = 'changed'
        self.blocked(r, [e], d, 'retained_source_hash_mismatch')

    def test_all_derived_fields_checked(self):
        for field in ('study_title', 'matching_interventions', 'all_interventions', 'arm_groups', 'exact_intervention_name_match', 'evidence_status', 'source_url'):
            with self.subTest(field=field):
                r, e, d = example()
                e[field] = [] if isinstance(e[field], list) else ('changed' if isinstance(e[field], str) else False)
                self.blocked(r, [e], d, 'source_projection_mismatch:' + field)

    def test_duplicate_identical_evidence_blocks(self):
        r, e, d = example()
        self.blocked(r, [e, copy.deepcopy(e)], d, 'duplicate_evidence_key')

    def test_conflicting_duplicates_block_in_both_orders(self):
        r, e, d = example(); conflict = copy.deepcopy(e); conflict['source_record_sha256'] = '0' * 64
        for records in ([e, conflict], [conflict, e]):
            self.blocked(r, records, d, 'duplicate_evidence_key')

    def test_duplicate_queue_rank_blocks(self):
        r, e, d = example(); catalog, report = run([r, copy.deepcopy(r)], [e], [d])
        self.assertEqual(catalog['entries'], [])
        self.assertIn('duplicate_queue_rank', report['error_counts'])

    def test_rehashed_source_still_requires_new_review_hash(self):
        r, e, d = example(); e['source_study']['protocolSection']['identificationModule']['briefTitle'] = 'changed'
        e['study_title'] = 'changed'; e['source_record_sha256'] = study_sha256(e['source_study'])
        self.blocked(r, [e], d, 'review_not_bound_to_source_hash')

    def test_wrong_study_id_blocks_even_when_rehashed(self):
        r, e, d = example(); e['source_study']['protocolSection']['identificationModule']['nctId'] = 'NCT00000002'
        e['source_record_sha256'] = study_sha256(e['source_study']); d['source_record_sha256'] = e['source_record_sha256']
        self.blocked(r, [e], d, 'retained_source_structure_invalid')

    def test_gate_cli_preserves_existing_outputs(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs=[]
            for name in ('queue', 'evidence', 'decisions'):
                path=root/name; path.write_text(json.dumps({'records':[]}));inputs += ['--'+name,str(path)]
            catalog=root/'catalog';catalog.write_text('KEEP');report=root/'report'
            result=subprocess.run([sys.executable,str(scripts/'regimen_approval_gate.py'),*inputs,'--catalog',str(catalog),'--report',str(report)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(catalog.read_text(),'KEEP');self.assertFalse(report.exists())

    def test_collector_cli_preserves_existing_output_without_fetch(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'evidence';output.write_text('KEEP')
            result=subprocess.run([sys.executable,str(scripts/'fetch_regimen_evidence_v2.py'),'--queue','missing','--links','missing','--output',str(output)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(output.read_text(),'KEEP');self.assertIn('Output already exists',result.stderr)

if __name__ == '__main__': unittest.main()
