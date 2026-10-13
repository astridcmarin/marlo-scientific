import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.patient_state import digest
from intelligence_store.pk_model_inputs import (model_input_example,validate_model_inputs,
    preview_model_inputs,load_input_contract,register_pk_model_input_commands)


class PKModelInputTests(unittest.TestCase):
    def test_canonical_copy_preserves_provenance_and_integrity(self):
        inputs=model_input_example();before=copy.deepcopy(inputs)
        canonical=validate_model_inputs(inputs)
        self.assertEqual(canonical,inputs);self.assertIsNot(canonical,inputs)
        self.assertEqual(validate_model_inputs(canonical),canonical)
        report=preview_model_inputs(inputs);self.assertEqual(before,inputs)
        self.assertEqual(report['inputs_sha256'],digest(canonical))
        body=dict(report);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)
        self.assertEqual(report,preview_model_inputs(inputs))
        self.assertFalse(report['ready_for_patient_simulation']);self.assertIsNone(report['patient_revision_id'])
        self.assertEqual(report['simulation_status'],'not_run')

    def test_missing_values_remain_unknown_without_normalization_defaults(self):
        inputs=model_input_example();inputs['fields']={}
        report=preview_model_inputs(inputs)
        self.assertEqual(report['status'],'missing_inputs')
        self.assertEqual(set(report['missing_fields']),{'fat_free_mass','creatinine_clearance'})
        self.assertIsNone(report['parameter_preview'])
        for field in report['inputs']['fields'].values():
            self.assertIsNone(field['value']);self.assertEqual(field['origin'],'unknown')

    def test_parameter_algebra_and_observed_range_boundaries(self):
        example=model_input_example();report=preview_model_inputs(example)
        self.assertEqual(report['status'],'parameter_preview_available')
        p=report['parameter_preview'];self.assertEqual(p['apparent_clearance_l_h'],12)
        self.assertEqual(p['apparent_volume_l'],68.8)
        example['fields']['fat_free_mass']['value']=80
        example['fields']['creatinine_clearance']['value']=45
        p=preview_model_inputs(example)['parameter_preview']
        self.assertAlmostEqual(p['apparent_clearance_l_h'],12*(80/55)**.75*(45/90)**.224)
        self.assertAlmostEqual(p['apparent_volume_l'],68.8*80/55)
        for ffm,crcl,status in ((32,36,'parameter_preview_available'),(84,211,'parameter_preview_available'),
                              (31.9,90,'outside_reference_range'),(55,211.1,'outside_reference_range')):
            example['fields']['fat_free_mass']['value']=ffm
            example['fields']['creatinine_clearance']['value']=crcl
            r=preview_model_inputs(example);self.assertEqual(r['status'],status)
            if status=='outside_reference_range':self.assertIsNone(r['parameter_preview'])

    def test_weight_egfr_unit_and_method_substitutions_are_rejected(self):
        for name in ('weight','egfr_indexed','lean_body_mass'):
            inputs=model_input_example();inputs['fields'][name]=inputs['fields'].pop('fat_free_mass')
            with self.assertRaises(ValueError):validate_model_inputs(inputs)
        for name,unit,method in (('fat_free_mass','lb','direct_synthetic_covariate'),
                                 ('creatinine_clearance','mL/min/1.73m2','direct_synthetic_covariate'),
                                 ('fat_free_mass','kg','total_body_weight'),
                                 ('creatinine_clearance','mL/min','ckd_epi_recorded')):
            inputs=model_input_example();inputs['fields'][name]['unit']=unit;inputs['fields'][name]['method']=method
            with self.assertRaises(ValueError):validate_model_inputs(inputs)

    def test_invalid_numbers_schema_and_provenance_fail_explicitly(self):
        for value in (0,-1,True,'55',float('nan'),float('inf'),10**400):
            inputs=model_input_example();inputs['fields']['fat_free_mass']['value']=value
            with self.assertRaises(ValueError):validate_model_inputs(inputs)
        inputs=model_input_example();inputs['purpose']='clinical'
        with self.assertRaises(ValueError):validate_model_inputs(inputs)
        for origin,method in (('assumption','direct_synthetic_covariate'),('synthetic_input','janmahasatian_recorded')):
            inputs=model_input_example();field=inputs['fields']['fat_free_mass']
            field.update(origin=origin,method=method,source_ref=None)
            with self.assertRaises(ValueError):validate_model_inputs(inputs)
            field['source_ref']='Recorded test assumption or calculation claim'
            self.assertEqual(validate_model_inputs(inputs)['fields']['fat_free_mass']['method'],method)
        inputs=model_input_example();inputs['fields']['fat_free_mass'].update(value=None,origin='unknown',method='unknown')
        with self.assertRaises(ValueError):validate_model_inputs(inputs)

    def test_changed_or_missing_input_contract_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'contract.json'
            with self.assertRaises(ValueError):load_input_contract(p)
            p.write_text('{}')
            with self.assertRaises(ValueError):load_input_contract(p)
        with patch('intelligence_store.pk_model_inputs.load_input_contract',side_effect=ValueError('Missing')):
            with self.assertRaises(ValueError):preview_model_inputs(model_input_example())

    def test_preview_reads_no_patient_database_network_or_solver(self):
        with patch('sqlalchemy.engine.Engine.connect',side_effect=AssertionError('DB')), \
             patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('intelligence_store.patient_state_revisions.read_revision',side_effect=AssertionError('Patient')), \
             patch('intelligence_store.published_transit_reference.solve_transit',side_effect=AssertionError('Solver')):
            self.assertEqual(preview_model_inputs(model_input_example())['status'],'parameter_preview_available')

    def test_cli_modes_json_safety_and_non_overwriting_output(self):
        app=Flask(__name__);register_pk_model_input_commands(app);runner=app.test_cli_runner()
        r=runner.invoke(args=['pk-model-inputs','--example','--json']);self.assertEqual(r.exit_code,0,r.output)
        self.assertEqual(json.loads(r.output),preview_model_inputs(model_input_example()))
        self.assertNotEqual(runner.invoke(args=['pk-model-inputs']).exit_code,0)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'inputs.json';out=Path(tmp)/'out.json'
            source.write_text(json.dumps(model_input_example()))
            r=runner.invoke(args=['pk-model-inputs','--inputs-file',str(source),'--output',str(out)])
            self.assertEqual(r.exit_code,0,r.output);saved=out.read_bytes()
            self.assertNotEqual(runner.invoke(args=['pk-model-inputs','--inputs-file',str(source),'--output',str(out)]).exit_code,0)
            self.assertEqual(out.read_bytes(),saved)
            self.assertNotEqual(runner.invoke(args=['pk-model-inputs','--example','--inputs-file',str(source)]).exit_code,0)
            for content in ('{"schema_version":"a","schema_version":"b"}', '{oops', ' '*65537):
                source.write_text(content)
                self.assertNotEqual(runner.invoke(args=['pk-model-inputs','--inputs-file',str(source)]).exit_code,0)


if __name__=='__main__':unittest.main()
