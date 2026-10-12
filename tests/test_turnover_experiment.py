"""Mathematical identities and web boundaries for hypothetical mechanisms."""
import copy
from decimal import Decimal, localcontext
import importlib.util
import math
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_turnover_experiment_test',ROOT/'intelligence_store/protein_turnover_experiments.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)


class TurnoverExperimentTests(unittest.TestCase):
    def process(self,**overrides):
        inputs=dict(loss_rate_h_inv=.2,initial_relative_amount=1,
            phases=[{'start_time_h':0,'production_multiplier':.25,'loss_multiplier':1}],times_h=[0,4,24])
        inputs.update(overrides)
        return model.calculate_turnover_process(**inputs)

    def test_independent_high_precision_production_loss_solution(self):
        for k,s,m,t,r in [(.2,.25,1,4,1),(.2,1,4,4,1),(1e-6,1000,1e-6,1e-8,0),(1000,0,1000,72,1e6)]:
            result=self.process(loss_rate_h_inv=k,initial_relative_amount=r,
                phases=[{'start_time_h':0,'production_multiplier':s,'loss_multiplier':m}],times_h=[0,t])
            with localcontext() as context:
                context.prec=70
                dk,ds,dm,dt,dr=[Decimal(str(v)) for v in [k,s,m,t,r]]
                decay=(-dk*dm*dt).exp()
                expected=dr*decay+(ds/dm)*(1-decay)
            self.assertAlmostEqual(result['points'][-1]['relative_amount'],float(expected),delta=1e-12*max(1,float(expected)))

    def test_same_equilibrium_different_pulse_speed_and_same_recovery_rate(self):
        report=model.compare_turnover_mechanisms(times_h=[0,1,4,8,24])
        production=report['examples']['reduced_production'];loss=report['examples']['increased_loss']
        self.assertEqual(production['segments'][0]['equilibrium_relative_amount'],.25)
        self.assertEqual(loss['segments'][0]['equilibrium_relative_amount'],.25)
        self.assertGreater(production['points'][2]['relative_amount'],loss['points'][2]['relative_amount'])
        for example in [production,loss]:
            switch=example['points'][2]['relative_amount'];later=example['points'][3]['relative_amount']
            self.assertAlmostEqual((1-later)/(1-switch),math.exp(-.2*4),places=14)

    def test_zero_production_zero_loss_and_baseline_control(self):
        decay=self.process(phases=[{'start_time_h':0,'production_multiplier':0,'loss_multiplier':1}])
        self.assertAlmostEqual(decay['points'][-1]['relative_amount'],math.exp(-.2*24),places=14)
        growth=self.process(phases=[{'start_time_h':0,'production_multiplier':2,'loss_multiplier':0}])
        self.assertAlmostEqual(growth['points'][-1]['relative_amount'],1+.4*24)
        static=self.process(phases=[{'start_time_h':0,'production_multiplier':0,'loss_multiplier':0}])
        self.assertTrue(all(p['relative_amount']==1 for p in static['points']))
        control=model.compare_turnover_mechanisms(strength=1)
        for example in control['examples'].values():
            self.assertTrue(all(abs(p['relative_amount']-1)<1e-14 for p in example['points']))

    def test_off_grid_boundary_split_invariance_and_input_preservation(self):
        phases=[{'start_time_h':0,'production_multiplier':.25,'loss_multiplier':1},
            {'start_time_h':3.37,'production_multiplier':1,'loss_multiplier':1}]
        original=copy.deepcopy(phases)
        report=self.process(phases=phases,times_h=[0,3.37,4,24])
        self.assertEqual(phases,original)
        switch=report['boundaries'][1]
        self.assertEqual(switch['relative_amount'],report['points'][1]['relative_amount'])
        self.assertEqual(report['points'][1]['production_multiplier'],1)
        self.assertEqual(switch['relative_amount'],report['segments'][0]['final_relative_amount'])
        whole=self.process();split=self.process(phases=[phases[0],{**phases[0],'start_time_h':3.37}])
        for a,b in zip(whole['points'],split['points']):self.assertAlmostEqual(a['relative_amount'],b['relative_amount'],places=14)

    def test_deterministic_nested_hashes_versions_and_scope(self):
        report=model.compare_turnover_mechanisms()
        self.assertEqual(report,model.compare_turnover_mechanisms())
        for payload in [report,*report['examples'].values()]:
            copied=copy.deepcopy(payload);sha=copied.pop('report_sha256')
            self.assertEqual(sha,model._digest(copied))
            self.assertFalse(payload['clinical_prediction_validated']);self.assertFalse(payload['ready_for_patient_simulation'])
            for key in ['drug','protein','patient_revision_id','pk_run_id']:self.assertIsNone(payload[key])

    def test_invalid_parameters_phase_fields_and_budgets(self):
        for overrides in [{'strength':0},{'strength':float('nan')},{'pulse_duration_h':24},
                          {'loss_rate_h_inv':True},{'loss_rate_h_inv':10**1000},{'times_h':[0,12]}]:
            with self.subTest(overrides=overrides),self.assertRaises(ValueError):model.compare_turnover_mechanisms(**overrides)
        for phases in [[{'start_time_h':0,'production_multiplier':-1,'loss_multiplier':1}],
                       [{'start_time_h':0,'production_multiplier':1,'loss_multiplier':1e-320}],
                       [{'start_time_h':0,'production_multiplier':1,'loss_multiplier':1,'patient_id':1}],
                       [{'start_time_h':0,'production_multiplier':True,'loss_multiplier':1}]]:
            with self.subTest(phases=phases),self.assertRaises(ValueError):self.process(phases=phases)
        for times in [[0,0],[1,2],[0,float('inf')],list(range(1002))]:
            with self.assertRaises(ValueError):self.process(times_h=times)

    def test_web_controls_export_exact_values_no_storage_and_no_patient_solver(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        client=app.test_client();path='/landscape/patient-lab/turnover-experiment'
        controls={'loss_rate_h_inv':.35,'strength':5,'pulse_duration_h':3.37,'time_h':5.2}
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No patient solver')), \
             patch('requests.get',side_effect=AssertionError('No network')):
            page=client.get(path,query_string=controls)
            exported=client.get(path,query_string={**controls,'format':'json'})
        self.assertEqual(page.status_code,200);self.assertEqual(exported.status_code,200)
        text=page.get_data(as_text=True)
        self.assertIn('<polyline',text);self.assertIn('Reduced Production',text)
        self.assertIn('No drug, protein identity or patient',text)
        self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(exported.json['inputs']['pulse_duration_h'],3.37)
        for example in exported.json['examples'].values():
            self.assertTrue(any(p['time_h']==5.2 for p in example['points']))
            self.assertEqual(example['boundaries'][1]['time_h'],3.37)
        self.assertEqual(exported.headers['Cache-Control'],'no-store')
        for query in ['time_h=-1','time_h=nan','strength=21','strength=1&strength=2',
                      'pulse_duration_h=24','loss_rate_h_inv=0','patient_id=1','pk_run_id=1','format=csv']:
            self.assertEqual(client.get(path+'?'+query).status_code,400)
        self.assertEqual(client.post(path).status_code,405)
        self.assertIn('turnover-experiment',client.get('/landscape/patient-lab/protein-turnover-demo').get_data(as_text=True))


if __name__=='__main__':unittest.main()
