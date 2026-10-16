"""Draft governance must not imply clinical or reviewer approval."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.patient_lab_intended_use import (
 intended_use_report, load_intended_use_contract, register_patient_lab_intended_use_commands)
from intelligence_store.patient_state import digest

class PatientLabIntendedUseTests(unittest.TestCase):
    def test_deterministic_hash_and_no_execution_or_storage_access(self):
        with patch('socket.socket.connect', side_effect=AssertionError('No network')), patch('sqlalchemy.engine.base.Connection.execute',side_effect=AssertionError('No DB')), patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            report=intended_use_report()
        self.assertEqual(report,intended_use_report())
        self.assertEqual(report['status'],'draft_pending_review')
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])
        for name in ('clinical_prediction_validated','ready_for_patient_simulation','control_verification_performed','residual_risk_accepted','database_writes_performed','ode_solver_rerun','network_refresh_performed'):
            self.assertFalse(report[name])
        self.assertIsNone(report['governance_approval'])

    def test_every_risk_has_controls_and_explicit_remaining_gap(self):
        report=intended_use_report();risks=report['failure_modes']
        self.assertEqual(len(risks),8);self.assertEqual(len({r['code'] for r in risks}),8)
        for risk in risks:
            self.assertTrue(risk['failure']);self.assertTrue(risk['consequence'])
            self.assertTrue(risk['recorded_controls']);self.assertTrue(risk['remaining_gap'])
        self.assertTrue(report['permitted_uses']);self.assertTrue(report['prohibited_uses'])
        self.assertEqual(report['change_control']['status'],'proposed_not_approved')
        self.assertTrue(all(role['assignment'] is None for role in report['change_control']['review_roles']))
        self.assertIsNone(report['change_control']['acceptance_decision'])

    def test_independent_contract_and_source_review_remain_pending(self):
        report=intended_use_report()
        self.assertEqual(len(report['model_contract_binding']),4)
        self.assertEqual(report['independent_transcription_review'],'pending')
        with patch('intelligence_store.patient_lab_intended_use.transcription_review_packet',side_effect=ValueError('Changed source contract')):
            with self.assertRaises(ValueError):intended_use_report()
        report['failure_modes'][0]['remaining_gap']='changed'
        self.assertNotEqual(report,intended_use_report())

    def test_corrupt_or_missing_intended_use_contract_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'policy.json';p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'missing or changed'):load_intended_use_contract(p)
            with self.assertRaises(ValueError):load_intended_use_contract(Path(directory)/'missing')

    def test_cli_json_and_protected_export(self):
        app=Flask(__name__);register_patient_lab_intended_use_commands(app);runner=app.test_cli_runner()
        result=runner.invoke(args=['patient-lab-intended-use','--json']);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(json.loads(result.stdout),intended_use_report())
        summary=runner.invoke(args=['patient-lab-intended-use']);self.assertEqual(summary.exit_code,0)
        self.assertIn('Governance approval: none',summary.output)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'use.json';args=['patient-lab-intended-use','--output',str(p)]
            self.assertEqual(runner.invoke(args=args).exit_code,0);before=p.read_bytes()
            self.assertNotEqual(runner.invoke(args=args).exit_code,0);self.assertEqual(p.read_bytes(),before)
            p2=Path(directory)/'bad.json'
            with patch('intelligence_store.patient_lab_intended_use.transcription_review_packet',side_effect=ValueError('Changed source')):
                self.assertNotEqual(runner.invoke(args=['patient-lab-intended-use','--output',str(p2)]).exit_code,0)
            self.assertFalse(p2.exists())
if __name__=='__main__':unittest.main()
