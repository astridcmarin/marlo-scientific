"""State contracts preserve units, unknowns and legacy provenance without models."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.patient_state import (SCHEMA_VERSION, PatientStateError, UNITS,
    digest, example_state, preview_patient_state, register_patient_state_commands,
    state_from_scenario, validate_patient_state)
from intelligence_store.patient_scenarios import load_scenario_presets


class PatientStateTests(unittest.TestCase):
    def test_omitted_fields_are_unknown_and_zero_is_preserved(self):
        state={'schema_version':SCHEMA_VERSION,'purpose':'synthetic_educational','fields':{}}
        canonical=validate_patient_state(state)
        self.assertEqual(set(canonical['fields']),set(UNITS))
        self.assertTrue(all(f['value'] is None and f['origin']=='unknown' for f in canonical['fields'].values()))
        field=canonical['fields']['egfr_indexed'];field.update(value=0,origin='synthetic_input')
        report=preview_patient_state(canonical)
        self.assertEqual(report['known_fields'],['egfr_indexed'])
        self.assertEqual(report['state']['fields']['egfr_indexed']['value'],0)
        self.assertNotEqual(report['state_sha256'],preview_patient_state(state)['state_sha256'])

    def test_canonical_copy_is_idempotent_and_does_not_mutate_inputs(self):
        raw=example_state();raw['fields']['weight']['value']='70.0';before=copy.deepcopy(raw)
        first=validate_patient_state(raw);second=validate_patient_state(first)
        self.assertEqual(first,second);self.assertEqual(raw,before)
        self.assertEqual(preview_patient_state(raw),preview_patient_state(first))
        first['fields']['weight']['value']=99
        self.assertEqual(raw['fields']['weight']['value'],'70.0')

    def test_units_cannot_substitute_indexed_egfr_for_clearance_or_convert_weight(self):
        for name,unit in [('egfr_indexed','mL/min'),('creatinine_clearance','mL/min/1.73m2'),
                          ('weight','lb'),('albumin','g/dL')]:
            state=example_state();state['fields'][name]['unit']=unit
            with self.subTest(name=name),self.assertRaisesRegex(PatientStateError,'expected unit'):
                validate_patient_state(state)

    def test_invalid_numbers_and_schema_are_rejected(self):
        for value in [True,[],float('nan'),float('inf'),-1,'','not a number',0]:
            state=example_state();state['fields']['weight']['value']=value
            with self.subTest(value=repr(value)),self.assertRaises(PatientStateError):validate_patient_state(state)
        for change in ['purpose','schema_version','unsupported_field','missing_metadata','derived_origin']:
            state=example_state()
            if change in ('purpose','schema_version'):state[change]='unsupported'
            elif change=='unsupported_field':state['fields']['child_pugh_score']={}
            elif change=='missing_metadata':del state['fields']['weight']['origin']
            else:state['fields']['weight']['origin']='derived'
            with self.subTest(change=change),self.assertRaises(PatientStateError):validate_patient_state(state)

    def test_origins_sources_and_timezone_are_explicit(self):
        state=example_state();f=state['fields']['weight'];f['origin']='assumption'
        with self.assertRaisesRegex(PatientStateError,'requires'):validate_patient_state(state)
        f['source_ref']='Invented assumption for demonstration'
        f['observed_at']='2026-10-07T08:00:00-04:00'
        first=validate_patient_state(state)
        self.assertEqual(first['fields']['weight']['observed_at'],'2026-10-07T12:00:00Z')
        f['observed_at']='2026-10-07T12:00:00Z'
        self.assertEqual(digest(first),digest(validate_patient_state(state)))
        for timestamp in ['2026-10-07','2026-10-07T12:00:00','invalid']:
            f['observed_at']=timestamp
            with self.subTest(timestamp=timestamp),self.assertRaises(PatientStateError):validate_patient_state(state)
        f['observed_at']=None;f['value']=None
        with self.assertRaisesRegex(PatientStateError,'null'):validate_patient_state(state)

    def test_legacy_adapter_is_catalog_independent_and_does_not_invent_new_values(self):
        profile=copy.deepcopy(load_scenario_presets()['index']['interaction-reference']['profile'])
        profile['selected_drug']='historical-uninstalled-drug';profile['biological_sex']='UNSPECIFIED'
        before=copy.deepcopy(profile)
        with patch('intelligence_store.patient_scenarios.load_alias_catalog',side_effect=AssertionError('no catalog dependency')):
            state=state_from_scenario(profile)
        self.assertEqual(profile,before)
        self.assertIsNone(state['fields']['biological_sex']['value'])
        for name in ['height','creatinine_clearance','serum_creatinine','alt','ast','albumin','total_bilirubin']:
            self.assertIsNone(state['fields'][name]['value'])
        field=state['fields']['egfr_indexed']
        self.assertEqual(field['value'],profile['egfr_ml_min_1_73m2'])
        self.assertEqual(field['origin'],'legacy_scenario')
        self.assertEqual(field['source_ref'],'legacy-profile-sha256:'+digest(profile))
        self.assertIsNone(field['observed_at'])
        self.assertNotIn('selected_drug',state['fields'])

    def runner(self):
        app=Flask(__name__);register_patient_state_commands(app)
        return app.test_cli_runner()

    def test_cli_example_needs_no_database_and_roundtrips_verified_preview(self):
        runner=self.runner();result=runner.invoke(args=['patient-state','--example'])
        self.assertEqual(result.exit_code,0,result.output);report=json.loads(result.output)
        self.assertEqual(report['simulation_status'],'not_run')
        self.assertEqual(report['state_sha256'],digest(report['state']))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'preview.json';p.write_text(result.output)
            second=runner.invoke(args=['patient-state','--state-file',str(p)])
            self.assertEqual(second.exit_code,0,second.output);self.assertEqual(json.loads(second.output),report)
            report['state']['fields']['weight']['value']=99;p.write_text(json.dumps(report))
            tampered=runner.invoke(args=['patient-state','--state-file',str(p)])
            self.assertNotEqual(tampered.exit_code,0);self.assertIn('digest mismatch',tampered.output)

    def test_cli_legacy_report_import_and_output_never_overwrite(self):
        runner=self.runner()
        profile=load_scenario_presets()['index']['interaction-reference']['profile']
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'legacy.json';source.write_text(json.dumps({'profile':profile}))
            output=Path(tmp)/'state.json'
            args=['patient-state','--scenario-file',str(source),'--output',str(output)]
            first=runner.invoke(args=args);self.assertEqual(first.exit_code,0,first.output)
            saved=output.read_bytes();self.assertEqual(json.loads(saved)['state'],state_from_scenario(profile))
            second=runner.invoke(args=args);self.assertNotEqual(second.exit_code,0)
            self.assertEqual(saved,output.read_bytes())

    def test_cli_rejects_invalid_modes_json_and_oversized_files(self):
        runner=self.runner()
        for args in [['patient-state'],['patient-state','--example','--state-file',__file__]]:
            self.assertNotEqual(runner.invoke(args=args).exit_code,0)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'invalid.json'
            for text in ['{','{"fields":NaN}',' '*131073]:
                p.write_text(text)
                self.assertNotEqual(runner.invoke(args=['patient-state','--state-file',str(p)]).exit_code,0)


if __name__=='__main__':unittest.main()


class SchemaV2Tests(unittest.TestCase):
    def v1(self):
        from intelligence_store.patient_state import example_state
        return example_state()

    def test_v1_states_validate_to_exactly_themselves(self):
        from intelligence_store.patient_state import SCHEMA_VERSION, UNITS_V1, validate_patient_state, digest
        state = self.v1()
        canonical = validate_patient_state(state)
        self.assertEqual(canonical['schema_version'], SCHEMA_VERSION)
        self.assertEqual(set(canonical['fields']), set(UNITS_V1))
        self.assertEqual(validate_patient_state(canonical), canonical)
        self.assertEqual(digest(validate_patient_state(canonical)), digest(canonical))

    def test_v2_adds_platelet_count_and_v1_refuses_it(self):
        import copy
        from intelligence_store.patient_state import (SCHEMA_V2, PatientStateError, UNITS_V2, validate_patient_state)
        field = {'value': 165, 'unit': '10^9/L', 'origin': 'synthetic_input', 'observed_at': None, 'source_ref': None}
        v2 = copy.deepcopy(self.v1()); v2['schema_version'] = SCHEMA_V2; v2['fields']['platelet_count'] = field
        canonical = validate_patient_state(v2)
        self.assertEqual(set(canonical['fields']), set(UNITS_V2))
        self.assertEqual(canonical['fields']['platelet_count']['value'], 165.0)
        v1 = copy.deepcopy(self.v1()); v1['fields']['platelet_count'] = field
        with self.assertRaises(PatientStateError):
            validate_patient_state(v1)
        for bad in ({'value': 0}, {'unit': '/uL'}):
            broken = copy.deepcopy(v2); broken['fields']['platelet_count'].update(bad)
            with self.assertRaises(PatientStateError):
                validate_patient_state(broken)
        unknown = copy.deepcopy(v2); unknown['schema_version'] = 'synthetic-patient-state-v3'
        with self.assertRaises(PatientStateError):
            validate_patient_state(unknown)
