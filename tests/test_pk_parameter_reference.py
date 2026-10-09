"""Reference normalization and algebra do not imply patient simulation readiness."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.pk_parameter_reference import (_parameter_math,load_parameter_extract,
    parameter_reference_report,register_pk_parameter_reference_commands)
from intelligence_store.patient_state import digest


class PKParameterReferenceTests(unittest.TestCase):
    def test_published_reference_values_and_units(self):
        report=parameter_reference_report();r=report['fixed_cases'][0]['parameters']
        self.assertEqual(r['apparent_clearance_l_h'],12)
        self.assertEqual(r['apparent_volume_l'],68.8)
        self.assertEqual(r['transit_rate_h'],13.5)
        self.assertAlmostEqual(r['elimination_rate_h'],12/68.8)
        self.assertTrue(all(c['passed'] for c in report['checks']))
        self.assertEqual(report['parameter_basis']['apparent_clearance']['unit'],'L/h')

    def test_renal_scaling_changes_clearance_without_changing_volume(self):
        p=load_parameter_extract()['parameters']
        first=_parameter_math(55,90,p);half=_parameter_math(55,45,p)
        self.assertAlmostEqual(half['apparent_clearance_l_h']/first['apparent_clearance_l_h'],math.exp(-0.224*math.log(2)))
        self.assertEqual(half['apparent_volume_l'],first['apparent_volume_l'])
        self.assertEqual(half['transit_rate_h'],first['transit_rate_h'])

    def test_ffm_scaling_differs_for_clearance_and_volume(self):
        p=load_parameter_extract()['parameters'];baseline=_parameter_math(55,90,p)
        doubled=_parameter_math(110,90,p)
        self.assertAlmostEqual(doubled['apparent_clearance_l_h']/baseline['apparent_clearance_l_h'],math.sqrt(math.sqrt(8)))
        self.assertEqual(doubled['apparent_volume_l']/baseline['apparent_volume_l'],2)
        # This is an algebra test outside a reviewed clinical domain, not a patient example.

    def test_invalid_math_inputs_are_not_guessed_or_converted(self):
        p=load_parameter_extract()['parameters']
        for value in (None,True,0,-1,'55',float('nan'),float('inf')):
            with self.assertRaises(ValueError):_parameter_math(value,90,p)
            with self.assertRaises(ValueError):_parameter_math(55,value,p)

    def test_source_digest_and_deterministic_output(self):
        report=parameter_reference_report();body=copy.deepcopy(report);sha=body.pop('report_sha256')
        self.assertEqual(digest(body),sha)
        self.assertEqual(report,parameter_reference_report())
        self.assertEqual(report['source']['doi'],'10.1111/bcp.13873')
        report['parameter_basis']['apparent_clearance']['value']=99
        self.assertEqual(parameter_reference_report()['parameter_basis']['apparent_clearance']['value'],12)

    def test_missing_or_modified_extract_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'extract.json'
            with self.assertRaises(ValueError):load_parameter_extract(p)
            p.write_text('{}')
            with self.assertRaises(ValueError):load_parameter_extract(p)

    def test_no_patient_db_network_or_simulation_and_readiness_stays_false(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            with patch('intelligence_store.patient_state_revisions.read_revision',side_effect=AssertionError('No state')):
                with patch('intelligence_store.pharmacokinetics.simulate_pk',side_effect=AssertionError('No curves')):
                    report=parameter_reference_report()
        self.assertFalse(report['ready_for_patient_simulation'])
        self.assertEqual(report['concentration_simulation_status'],'not_implemented')
        self.assertNotIn('points',report);self.assertNotIn('cmax',report)

    def test_cli_runs_without_db_and_exports_never_overwrite(self):
        app=Flask(__name__);register_pk_parameter_reference_commands(app);runner=app.test_cli_runner()
        result=runner.invoke(args=['pk-parameter-check']);self.assertEqual(result.exit_code,0,result.output)
        self.assertIn('parameter_math_passed',result.output)
        result=runner.invoke(args=['pk-parameter-check','--json']);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(json.loads(result.output),parameter_reference_report())
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'check.json';args=['pk-parameter-check','--output',str(p)]
            self.assertEqual(runner.invoke(args=args).exit_code,0);before=p.read_bytes()
            self.assertNotEqual(runner.invoke(args=args).exit_code,0);self.assertEqual(before,p.read_bytes())

if __name__=='__main__':unittest.main()
