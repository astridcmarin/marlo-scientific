"""Preparation stays distinct from independent sign-off and clinical validation."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.pk_transcription_review import (
    transcription_review_packet, independent_review_worksheet, register_pk_transcription_review_commands)
from intelligence_store.patient_state import digest

class PKTranscriptionReviewTests(unittest.TestCase):
    def test_packet_is_contract_bound_without_patient_execution_or_network(self):
        with patch('intelligence_store.educational_pk.solve_transit', side_effect=AssertionError('No solver')), patch('socket.socket.connect',side_effect=AssertionError('No network')):
            report=transcription_review_packet()
        self.assertEqual(report['status'],'independent_review_pending')
        self.assertEqual(report['source_file_check']['status'],'not_supplied')
        self.assertEqual(len(report['review_items']),16)
        self.assertEqual(len({r['code'] for r in report['review_items']}),16)
        self.assertEqual(len(report['contract_binding']),4)
        for flag in ('independent_review_completed','clinical_prediction_validated','ready_for_patient_simulation','database_writes_performed','ode_solver_rerun','network_refresh_performed'):
            self.assertFalse(report[flag])
        self.assertIsNone(report['validation_approval'])
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])

    def test_source_hash_matches_or_fails_without_approval(self):
        from intelligence_store.published_transit_reference import load_structure_contract
        structure=load_structure_contract();data=b'Synthetic test file; not a scientific source'
        structure['source']['sha256']=hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.docx';path.write_bytes(data)
            with patch('intelligence_store.pk_transcription_review.load_structure_contract',return_value=structure):
                report=transcription_review_packet(path)
                self.assertEqual(report['source_file_check']['status'],'source_file_hash_matches')
                self.assertFalse(report['independent_review_completed'])
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'SHA256 differs'):transcription_review_packet(path)
        with self.assertRaises(OSError):transcription_review_packet('/does/not/exist')

    def test_missing_or_changed_contracts_stop_preparation(self):
        for loader in ('load_parameter_extract','load_structure_contract','load_coverage_contract','load_execution_contract'):
            with self.subTest(loader=loader),patch('intelligence_store.pk_transcription_review.'+loader,side_effect=ValueError('Changed contract')):
                with self.assertRaises(ValueError):transcription_review_packet()
        from intelligence_store.educational_pk import load_execution_contract
        execution=load_execution_contract();execution['structure_contract_sha256']='0'*64
        with patch('intelligence_store.pk_transcription_review.load_execution_contract',return_value=execution):
            with self.assertRaisesRegex(ValueError,'not bound'):transcription_review_packet()

    def test_worksheet_is_blank_separate_and_bound_to_packet(self):
        report=transcription_review_packet();before=copy.deepcopy(report)
        worksheet=independent_review_worksheet(report)
        self.assertEqual(worksheet['review_packet_sha256'],report['report_sha256'])
        self.assertEqual(worksheet['status'],'unassessed')
        self.assertTrue(all(v is None for v in worksheet['reviewer'].values()))
        self.assertIsNone(worksheet['review_decision'])
        for item in worksheet['items']:
            self.assertNotIn('project_transcription',item)
            self.assertIsNone(item['independent_transcription'])
            self.assertEqual(item['source_locations'],[])
            self.assertEqual(item['comparison_result'],'unassessed')
        self.assertEqual(digest({k:v for k,v in worksheet.items() if k!='template_sha256'}),worksheet['template_sha256'])
        worksheet['source_reference']['doi']='test';self.assertEqual(report,before)

    def test_source_and_project_policy_remain_distinct(self):
        r=transcription_review_packet();items={i['code']:i for i in r['review_items']}
        self.assertEqual(items['execution_policy']['category'],'project_policy')
        self.assertEqual(items['compartment_structure']['project_transcription']['precentral_stage_count'],8)
        self.assertEqual(items['parameter_apparent_clearance']['project_transcription']['unit'],'L/h')
        self.assertEqual(items['parameter_apparent_volume']['project_transcription']['value'],68.8)
        self.assertEqual(len(r['historical_notes_to_reconcile']),2)
        self.assertIn('supplementary control stream not retrieved',r['historical_notes_to_reconcile'][0]['recorded_text'])

    def test_cli_exports_never_overwrite_and_mismatch_creates_no_output(self):
        app=Flask(__name__);register_pk_transcription_review_commands(app);runner=app.test_cli_runner()
        result=runner.invoke(args=['pk-transcription-review','--json'])
        self.assertEqual(result.exit_code,0,result.output);self.assertEqual(json.loads(result.output),transcription_review_packet())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'packet.json'
            args=['pk-transcription-review','--worksheet','--output',str(path)]
            self.assertEqual(runner.invoke(args=args).exit_code,0)
            first=path.read_bytes();self.assertEqual(json.loads(first)['status'],'unassessed')
            self.assertNotEqual(runner.invoke(args=args).exit_code,0);self.assertEqual(path.read_bytes(),first)
            source=Path(directory)/'wrong.docx';source.write_bytes(b'wrong');bad=Path(directory)/'bad.json'
            result=runner.invoke(args=['pk-transcription-review','--source-file',str(source),'--output',str(bad)])
            self.assertNotEqual(result.exit_code,0);self.assertFalse(bad.exists())

if __name__=='__main__':unittest.main()
