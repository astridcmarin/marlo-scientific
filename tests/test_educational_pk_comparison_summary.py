"""Comparative metrics must not imply clinical renal or response attribution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_educational_pk_comparison as fixtures
from intelligence_store.educational_pk_comparison_summary import (
 comparison_summary,register_educational_pk_comparison_summary_commands,_delta)
from intelligence_store.educational_pk_metrics import summarize_pk_run
from intelligence_store.educational_pk_runs import save_pk_run,export_pk_run
from intelligence_store.pk_model_inputs import model_input_example
from intelligence_store.treatment_requests import treatment_request_example
from intelligence_store.patient_state import digest

class EducationalPKComparisonSummaryTests(unittest.TestCase):
    setUp=fixtures.EducationalPKComparisonTests.setUp
    tearDown=fixtures.EducationalPKComparisonTests.tearDown
    save_scenario=fixtures.EducationalPKComparisonTests.save_scenario
    baseline=fixtures.EducationalPKComparisonTests.baseline
    save=fixtures.EducationalPKComparisonTests.save
    pair=fixtures.EducationalPKComparisonTests.pair

    def summary(self,a,b):return comparison_summary(a.id,b.id,revision_id=self.revision.id)

    def test_baseline_crcl_pair_is_audited_and_read_only(self):
        a,b=self.pair();before=(export_pk_run(a.id),export_pk_run(b.id))
        with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            report=self.summary(a,b)
        self.assertEqual(report['status'],'educational_comparison_summary_available')
        self.assertEqual(report['comparison_context']['status'],'single_declared_covariate_value_changed')
        self.assertEqual(report['comparison_context']['changed_covariate_values'],['creatinine_clearance'])
        self.assertFalse(report['comparison_context']['treatment_values_changed'])
        rows={r['code']:r for r in report['metrics']};self.assertEqual(len(rows),7)
        self.assertAlmostEqual(rows['apparent_clearance_l_h']['right_to_left_ratio'],0.5**0.224)
        self.assertEqual(rows['apparent_volume_l']['right_minus_left'],0)
        self.assertGreater(rows['auc_recorded_window']['right_minus_left'],0)
        self.assertEqual(rows['sampled_maximum']['right'],summarize_pk_run(b.id)['sampled_peak']['concentration_ng_ml'])
        self.assertIsNone(rows['first_sampled_maximum_time']['right_to_left_ratio'])
        self.assertEqual((export_pk_run(a.id),export_pk_run(b.id)),before)
        self.assertFalse(report['clinical_prediction_validated']);self.assertFalse(report['ready_for_patient_simulation'])
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])

    def test_identical_and_reversed_pairs_have_defined_arithmetic(self):
        a,b=self.pair();same=self.summary(a,a)
        self.assertTrue(all(r['right_minus_left']==0 for r in same['metrics']))
        self.assertEqual(same['comparison_context']['status'],'no_declared_numeric_input_change')
        forward=self.summary(a,b);reverse=self.summary(b,a)
        for x,y in zip(forward['metrics'],reverse['metrics']):self.assertEqual(x['right_minus_left'],-y['right_minus_left'])
        self.assertIsNone(_delta('x','test','unit',0,1)['right_to_left_ratio'])
        with self.assertRaises(ValueError):_delta('x','test','unit',float('nan'),1)

    def test_treatment_values_and_multiple_covariates_are_flagged(self):
        a,b=self.pair();request=treatment_request_example()
        for e in request['events']:e['amount']['value']=25
        dose=save_pk_run(self.revision.id,model_input_example(),request,'MM',title='Invented changed amount')
        report=self.summary(a,dose)
        self.assertEqual(report['comparison_context']['status'],'treatment_values_changed_do_not_isolate_covariate_effect')
        self.assertTrue(report['comparison_context']['treatment_values_changed'])
        inputs=model_input_example();inputs['fields']['fat_free_mass']['value']=60;inputs['fields']['creatinine_clearance']['value']=45
        both=save_pk_run(self.revision.id,inputs,treatment_request_example(),'MM',title='Invented multiple changes')
        self.assertEqual(self.summary(a,both)['comparison_context']['status'],'multiple_covariate_values_changed')

    def test_request_metadata_changes_do_not_become_numeric_changes(self):
        a,b=self.pair();request=treatment_request_example();request['source_ref']='Different invented note'
        inputs=model_input_example();inputs['fields']['fat_free_mass']['source_ref']='Different synthetic declaration'
        other=save_pk_run(self.revision.id,inputs,request,'MM',title='Metadata only')
        report=self.summary(a,other);context=report['comparison_context']
        self.assertEqual(context['status'],'no_declared_numeric_input_change')
        self.assertTrue(context['full_treatment_request_changed']);self.assertFalse(context['treatment_values_changed'])
        self.assertEqual(context['changed_covariate_metadata'],['fat_free_mass'])
        self.assertTrue(all(r['right_minus_left']==0 for r in report['metrics']))

    def test_incompatible_or_failed_audit_withholds_metrics(self):
        a,b=self.pair();request=treatment_request_example();request['horizon']['value']=48
        short=save_pk_run(self.revision.id,model_input_example(),request,'MM',title='Short window')
        with patch('intelligence_store.educational_pk_comparison_summary.summarize_pk_run',side_effect=AssertionError('No audit of incompatible pair')):
            report=self.summary(a,short)
        self.assertEqual(report['status'],'comparison_summary_withheld');self.assertIn('time_grid',report['withheld_reasons'])
        self.assertIsNone(report['metrics'])
        failed=summarize_pk_run(a.id);failed.update(status='metrics_withheld',sampled_peak=None,exposure=None)
        with patch('intelligence_store.educational_pk_comparison_summary.summarize_pk_run',return_value=failed):
            report=self.summary(a,b)
        self.assertIsNone(report['metrics']);self.assertEqual(report['status'],'comparison_summary_withheld')

    def test_cli_json_matches_and_exports_never_overwrite(self):
        a,b=self.pair();register_educational_pk_comparison_summary_commands(self.app);runner=self.app.test_cli_runner()
        args=['patient-pk-comparison-summary','--revision-id',str(self.revision.id),'--left',str(a.id),'--right',str(b.id)]
        result=runner.invoke(args=args+['--json']);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(json.loads(result.output),self.summary(a,b))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'summary.json';self.assertEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0)
            before=path.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(path)]).exit_code,0);self.assertEqual(path.read_bytes(),before)
        self.assertNotEqual(runner.invoke(args=['patient-pk-comparison-summary']).exit_code,0)

if __name__=='__main__':unittest.main()
