"""Independent exact-solution and web-boundary checks; invented fixtures only."""
import copy
from decimal import Decimal, localcontext
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_test_turnover',ROOT/'intelligence_store/protein_turnover.py')
turnover=importlib.util.module_from_spec(spec);spec.loader.exec_module(turnover)


class ProteinTurnoverTests(unittest.TestCase):
    def calculate(self,**overrides):
        inputs=dict(loss_rate_h_inv=.2,phases=[{'start_time_h':0,'loss_multiplier':4},
            {'start_time_h':4,'loss_multiplier':1}],times_h=[0,1,4,8,24])
        inputs.update(overrides)
        return turnover.calculate_turnover(**inputs)

    def test_independent_decimal_solution_and_extreme_rates(self):
        for k,m,t,r in [(.2,4,4,1),(1e-6,.01,1e-8,1),(1000,1000,72,1e6),(.05,1,24,.2)]:
            result=self.calculate(loss_rate_h_inv=k,initial_relative_amount=r,
                phases=[{'start_time_h':0,'loss_multiplier':m}],times_h=[0,t])
            with localcontext() as ctx:
                ctx.prec=70
                dk,dm,dt,dr=map(lambda x:Decimal(str(x)),[k,m,t,r])
                e=(-dk*dm*dt).exp()
                expected=dr*e+(1-e)/dm
            self.assertAlmostEqual(result['points'][-1]['relative_amount'],float(expected),delta=1e-12*max(1,float(expected)))
            self.assertTrue(math.isfinite(result['points'][-1]['relative_amount']))

    def test_baseline_zero_loss_and_nonequilibrium_initial_state(self):
        baseline=self.calculate(phases=[{'start_time_h':0,'loss_multiplier':1}])
        self.assertTrue(all(p['relative_amount']==1 for p in baseline['points']))
        growth=self.calculate(phases=[{'start_time_h':0,'loss_multiplier':0}],initial_relative_amount=0)
        for p in growth['points']:self.assertAlmostEqual(p['relative_amount'],.2*p['time_h'])
        self.assertIsNone(growth['segments'][0]['equilibrium_relative_amount'])
        recovery=self.calculate(phases=[{'start_time_h':0,'loss_multiplier':1}],initial_relative_amount=.2)
        self.assertGreater(recovery['points'][-1]['relative_amount'],.2)
        self.assertLess(recovery['points'][-1]['relative_amount'],1)

    def test_off_grid_switch_continuity_and_recovery(self):
        report=self.calculate(phases=[{'start_time_h':0,'loss_multiplier':4},
            {'start_time_h':3.37,'loss_multiplier':1}],times_h=[0,3.37,4,24])
        boundary=report['boundaries'][1]
        self.assertEqual(boundary['relative_amount'],report['segments'][0]['final_relative_amount'])
        self.assertEqual(boundary['relative_amount'],report['segments'][1]['initial_relative_amount'])
        self.assertEqual(report['points'][1]['relative_amount'],boundary['relative_amount'])
        self.assertEqual(report['points'][1]['loss_multiplier'],1)
        self.assertGreater(report['points'][-1]['relative_amount'],report['points'][1]['relative_amount'])
        whole=self.calculate(phases=[{'start_time_h':0,'loss_multiplier':4}])
        split=self.calculate(phases=[{'start_time_h':0,'loss_multiplier':4},{'start_time_h':3.37,'loss_multiplier':4}])
        for a,b in zip(whole['points'],split['points']):self.assertAlmostEqual(a['relative_amount'],b['relative_amount'],places=14)

    def test_determinism_integrity_no_mutation_and_scope(self):
        phases=[{'start_time_h':0,'loss_multiplier':4}];old=copy.deepcopy(phases)
        a=self.calculate(phases=phases);b=self.calculate(phases=phases)
        self.assertEqual(a,b);self.assertEqual(phases,old)
        sha=a.pop('report_sha256');self.assertEqual(sha,turnover._digest(a))
        for key in ['drug','protein','patient_revision_id','pk_run_id']:self.assertIsNone(a[key])
        self.assertFalse(a['clinical_prediction_validated']);self.assertFalse(a['ready_for_patient_simulation'])

    def test_invalid_types_ranges_order_phases_and_budget(self):
        bad=[{'loss_rate_h_inv':True},{'loss_rate_h_inv':float('nan')},{'loss_rate_h_inv':0},
            {'initial_relative_amount':-1},{'phases':[{'start_time_h':0,'loss_multiplier':1e-320}]},{'times_h':[0,0]},{'times_h':[1,2]},
            {'times_h':[0,float('inf')]},{'times_h':list(range(1002))},
            {'phases':[{'start_time_h':0,'loss_multiplier':4,'drug':'x'}]},
            {'phases':[{'start_time_h':24,'loss_multiplier':1}]},
            {'phases':[{'start_time_h':0,'loss_multiplier':-1}]},
            {'phases':[{'start_time_h':0,'loss_multiplier':1}]*9}]
        for data in bad:
            with self.subTest(data=data),self.assertRaises(ValueError):self.calculate(**data)

    def test_cli_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'report.json'
            cmd=[sys.executable,str(ROOT/'scripts/protein_turnover_demo.py'),'--output',str(output)]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(output.read_text()),turnover.turnover_example())
            original=output.read_bytes()
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            self.assertEqual(original,output.read_bytes())

    def test_web_inspection_export_and_rejected_patient_links_without_storage(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        client=app.test_client();path='/landscape/patient-lab/protein-turnover-demo'
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No patient solver')), \
             patch('requests.get',side_effect=AssertionError('No network')):
            page=client.get(path+'?time_h=3.37')
            exported=client.get(path+'?time_h=3.37&format=json')
        self.assertEqual(page.status_code,200)
        self.assertEqual(exported.status_code,200)
        self.assertEqual(page.get_data(as_text=True).count('class="nav-item active"'),1)
        self.assertIn('3.37',page.get_data(as_text=True));self.assertIn('<polyline',page.get_data(as_text=True))
        self.assertIn('No identified protein, drug or patient',page.get_data(as_text=True))
        self.assertEqual(page.headers['Cache-Control'],'no-store')
        for data in exported.json.values():
            self.assertTrue(any(p['time_h']==3.37 for p in data['points']))
        for query in ['time_h=-1','time_h=nan','time_h=25','time_h=1&time_h=2','patient_id=1','pk_run_id=1','format=csv']:
            self.assertEqual(client.get(path+'?'+query).status_code,400)
        self.assertEqual(client.post(path).status_code,405)


if __name__=='__main__':unittest.main()
