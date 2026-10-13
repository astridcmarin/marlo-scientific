"""The combined checkpoint preserves explicit lineage and scientific blockers."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_pk_validation_gap as fixtures
from intelligence_store.patient_lab_milestone import phase_checkpoint,register_patient_lab_milestone_commands
from intelligence_store.patient_state import digest
from intelligence_store.pk_validation_artifacts import artifact_manifest_example

class PatientLabMilestoneTests(unittest.TestCase):
    setUp=fixtures.PKValidationGapTests.setUp
    tearDown=fixtures.PKValidationGapTests.tearDown
    save_scenario=fixtures.PKValidationGapTests.save_scenario
    baseline=fixtures.PKValidationGapTests.baseline
    source_run=fixtures.PKValidationGapTests.source_run
    hashes=fixtures.PKValidationGapTests.hashes

    def checkpoint(self,**kwargs):
        return phase_checkpoint(1,self.scenario.id,self.revision.id,self.run.id,**kwargs)

    def test_phase_separates_software_pass_from_science_and_is_read_only(self):
        self.source_run();before=self.hashes()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')),patch('socket.socket.connect',side_effect=AssertionError('No network')):
            report=self.checkpoint()
        self.assertEqual(report['status'],'software_checkpoint_passed_science_pending')
        self.assertEqual(report['software_checkpoint']['status'],'software_checkpoint_passed_with_warnings')
        self.assertEqual(report['artifact_inventory']['file_status_counts'],{'not_supplied':8})
        self.assertFalse(report['artifact_manifest_supplied'])
        self.assertEqual(report['validation_gap']['source_payload_sha256'],self.run.payload_sha256)
        self.assertEqual(report['software_checkpoint']['source_hashes']['run_payload_sha256'],self.run.payload_sha256)
        self.assertIn('equation_transcription',report['blockers']);self.assertIn('external_validation',report['blockers'])
        self.assertEqual(report['intended_use']['status'],'draft_pending_review')
        self.assertEqual(report['transcription_review']['status'],'independent_review_pending')
        self.assertEqual(len(report['environment']['selected_code_sha256']),15)
        self.assertEqual(self.hashes(),before)
        self.assertFalse(report['clinical_prediction_validated']);self.assertFalse(report['ready_for_patient_simulation'])
        self.assertIsNone(report['governance_approval'])
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])

    def test_wrong_lineage_stops_scientific_summaries(self):
        self.source_run()
        with patch('intelligence_store.patient_lab_milestone.validation_gap_report',side_effect=AssertionError('Must stop after lineage failure')):
            report=phase_checkpoint(999,self.scenario.id,self.revision.id,self.run.id)
        self.assertEqual(report['status'],'phase_checkpoint_failed');self.assertIsNone(report['validation_gap'])
        self.assertIsNone(report['environment'])

    def test_manifest_digest_failure_blocks_phase_without_changing_archive(self):
        self.source_run();before=self.hashes()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'artifact').write_bytes(b'Synthetic test artifact')
            manifest=artifact_manifest_example();manifest['artifacts'][0].update(file='artifact',expected_sha256='0'*64)
            path=root/'manifest.json';path.write_text(json.dumps(manifest))
            report=self.checkpoint(manifest_path=path)
            self.assertEqual(report['status'],'phase_checkpoint_failed')
            self.assertIn('declared_artifact_file_integrity_failed',report['blockers'])
        self.assertEqual(self.hashes(),before)

    def test_current_archive_contract_mismatch_cannot_pass(self):
        self.source_run()
        from intelligence_store.pk_validation_gap import validation_gap_report
        gap=validation_gap_report(self.run.id);gap['contract_matches']['execution_contract_matches_archive']=False
        gap['gates'][0]['status']='failed'
        with patch('intelligence_store.patient_lab_milestone.validation_gap_report',return_value=gap):
            report=self.checkpoint()
        self.assertEqual(report['status'],'phase_checkpoint_failed')
        self.assertIn('source_traceability',report['blockers'])

    def test_cli_explicit_ids_reports_and_protected_exports(self):
        self.source_run();register_patient_lab_milestone_commands(self.app);runner=self.app.test_cli_runner()
        args=['patient-lab-phase-checkpoint','--cohort-id','1','--scenario-id',str(self.scenario.id),'--revision-id',str(self.revision.id),'--run-id',str(self.run.id)]
        result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(json.loads(result.output),self.checkpoint())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'checkpoint.json'
            self.assertEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            before=path.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            self.assertEqual(path.read_bytes(),before)
        self.assertNotEqual(runner.invoke(args=['patient-lab-phase-checkpoint']).exit_code,0)
        failed=args.copy();failed[2]='999'
        result=runner.invoke(args=failed+['--json']);self.assertEqual(result.exit_code,1)
        self.assertEqual(json.loads(result.output)['status'],'phase_checkpoint_failed')

if __name__=='__main__':unittest.main()
