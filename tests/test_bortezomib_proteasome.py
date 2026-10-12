import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal, localcontext
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_tested_bortezomib',ROOT/'intelligence_store/bortezomib_proteasome.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)


class ProteasomeTests(unittest.TestCase):
    def test_baseline_half_maximum_monotonicity_and_asymptote(self):
        values=[0,0.001,0.179,1.79,17.9,179,1e6]
        points=model.calculate_proteasome_activity(plasma_concentrations_nm=values)['points']
        self.assertEqual(points[0]['activity_percent_of_baseline'],100)
        self.assertAlmostEqual(points[3]['activity_percent_of_baseline'],64.45,places=12)
        activity=[p['activity_percent_of_baseline'] for p in points]
        self.assertTrue(all(28.9<=v<=100 for v in activity))
        self.assertTrue(all(a>b for a,b in zip(activity,activity[1:])))
        self.assertAlmostEqual(activity[-1],28.9,places=5)

    def test_independent_decimal_equation_and_subnormal_inputs(self):
        values=[5e-324,1e-8,0.179,0.73,1.79,4.2,17.9,1e6]
        points=model.calculate_proteasome_activity(plasma_concentrations_nm=values)['points']
        with localcontext() as context:
            context.prec=60
            for c,p in zip(values,points):
                d=Decimal(str(c)); power=d**Decimal('1.47')
                expected=Decimal('100')-Decimal('71.1')*power/(Decimal('1.79')**Decimal('1.47')+power)
                self.assertAlmostEqual(float(expected),p['activity_percent_of_baseline'],places=11)

    def test_invalid_inputs_and_units_fail_without_coercion(self):
        invalid=[[],(),[True],['1.79'],[None],[float('nan')],[float('inf')],[-1],[1e6+1],
                 [1,1],[2,1],[10**1000],[0]*1002]
        for values in invalid:
            with self.subTest(values=str(values)[:50]),self.assertRaises(ValueError):
                model.calculate_proteasome_activity(plasma_concentrations_nm=values)
        with self.assertRaises(TypeError):model.calculate_proteasome_activity(free_concentrations_nm=[1])
        with self.assertRaises(TypeError):model.calculate_proteasome_activity(plasma_concentrations_nm=[1],patient_id=1)

    def test_provenance_hash_determinism_no_mutation_and_no_clinical_promotion(self):
        original=[0,1.79,10]; report=model.calculate_proteasome_activity(plasma_concentrations_nm=original)
        self.assertEqual(original,[0,1.79,10])
        self.assertEqual(report,model.calculate_proteasome_activity(plasma_concentrations_nm=original))
        digest=report.pop('report_sha256')
        self.assertEqual(digest,hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
        self.assertFalse(report['clinical_prediction_validated']);self.assertFalse(report['ready_for_patient_simulation'])
        self.assertIsNone(report['reference']['observed_concentration_domain_nm'])
        self.assertEqual(report['pk_coupling_status'],'not_connected')
        self.assertIsNone(report['efficacy_prediction']);self.assertIsNone(report['toxicity_prediction'])

    def test_altered_or_missing_reference_blocks_calculation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'reference.json'
            with patch.object(model,'REFERENCE_PATH',path):
                with self.assertRaises(ValueError):model.proteasome_example()
                path.write_text('{}')
                with self.assertRaises(ValueError):model.proteasome_example()

    def test_cli_json_roundtrip_no_overwrite_and_rejects_patient_argument(self):
        command=[sys.executable,str(ROOT/'scripts/bortezomib_proteasome_demo.py')]
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'result.json'
            p=subprocess.run(command+['--output',str(out)],capture_output=True,text=True,cwd=d)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(out.read_text()),model.proteasome_example())
            before=out.read_bytes()
            self.assertNotEqual(subprocess.run(command+['--output',str(out)],capture_output=True).returncode,0)
            self.assertEqual(before,out.read_bytes())
            self.assertNotEqual(subprocess.run(command+['--patient-id','1'],capture_output=True).returncode,0)


class ProteasomePageTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from landscape_ui import register_landscape
        self.app=Flask(__name__);self.app.config['TESTING']=True
        self.app.add_url_rule('/','home',lambda:'Home');register_landscape(self.app)
        self.client=self.app.test_client()
        self.path='/landscape/simulation-lab/bortezomib-proteasome'

    def test_page_export_navigation_without_database(self):
        response=self.client.get(self.path)
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertIn('64.4500%',text)
        self.assertIn('All Simulation Lab experiments',text)
        self.assertEqual(text.count('class="nav-item active"'),1)
        exported=self.client.get(self.path+'?concentration_nm=2&format=json')
        self.assertEqual(exported.status_code,200)
        self.assertEqual(exported.headers['Cache-Control'],'no-store')
        self.assertFalse(exported.json['ready_for_patient_simulation'])
        self.assertIn('bortezomib-proteasome',self.client.get('/landscape/simulation-lab').get_data(as_text=True))

    def test_bad_queries_and_corrupt_source_fail_closed(self):
        for query in ['patient_id=1','pk_run_id=1','concentration_nm=nan','concentration_nm=-1',
                      'concentration_nm=101','concentration_nm=1&concentration_nm=2','format=csv','concentration_nm=true']:
            with self.subTest(query=query):self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)
        with patch('landscape_ui.bortezomib_proteasome_pages.calculate_proteasome_activity',side_effect=ValueError('bad source')):
            self.assertEqual(self.client.get(self.path).status_code,503)
            self.assertEqual(self.client.get(self.path+'?format=json').status_code,503)


if __name__=='__main__':unittest.main()
