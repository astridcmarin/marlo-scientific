"""Verify a hypothetical coupling numerically; no biological validation claim."""
import copy
import math
import unittest
from unittest.mock import patch
from intelligence_store.binding_turnover import calculate_binding_turnover
from intelligence_store.target_binding_kinetics import _hash


def integrating_factor_reference(kout,gain,kon,koff,concentration,duration):
    """Independent integrating factor + composite Simpson quadrature, not RK4."""
    rate=kon*concentration+koff;eq=kon*concentration/rate
    def segment(initial,b0,beq,r,length):
        def cumulative(time):
            return kout*((1+gain*beq)*time+gain*(b0-beq)*(-math.expm1(-r*time))/r)
        total=cumulative(length);n=16384;h=length/n
        values=[math.exp(cumulative(i*h)-total) for i in range(n+1)]
        integral=h/3*(values[0]+values[-1]+4*sum(values[1:-1:2])+2*sum(values[2:-1:2]))
        return initial*math.exp(-total)+kout*integral
    at_switch=segment(1,0,eq,rate,duration)
    bound_switch=eq*(-math.expm1(-rate*duration))
    final=segment(at_switch,bound_switch,0,koff,24-duration)
    return at_switch,final


class BindingTurnoverTests(unittest.TestCase):
    def report(self,**kwargs):
        return calculate_binding_turnover(times_h=[0,1,4,8,24],**kwargs)

    def test_independent_integrating_factor_reference(self):
        for overrides in [{},{'pulse_duration_h':3.37,'hypothetical_gain':7,'loss_rate_h_inv':.5}]:
            report=self.report(**overrides);inputs=report['inputs']
            for name,kon,koff in [('slower_binding',.01,.1),('faster_binding',.1,1)]:
                boundary,final=integrating_factor_reference(inputs['loss_rate_h_inv'],inputs['hypothetical_gain'],
                    kon,koff,inputs['free_concentration_nm'],inputs['pulse_duration_h'])
                example=report['examples'][name]
                self.assertAlmostEqual(example['pulse_boundary']['relative_amount'],boundary,delta=2e-8)
                self.assertAlmostEqual(example['points'][-1]['relative_amount'],final,delta=2e-8)

    def test_step_refinement_reduces_numerical_error(self):
        _,reference=integrating_factor_reference(.5,7,.1,1,10,3.37)
        errors=[]
        for step in [.05,.025,.0125]:
            report=self.report(loss_rate_h_inv=.5,hypothetical_gain=7,pulse_duration_h=3.37,max_step_h=step)
            errors.append(abs(report['examples']['faster_binding']['points'][-1]['relative_amount']-reference))
        self.assertGreater(errors[0],errors[1]);self.assertGreater(errors[1],errors[2])
        self.assertLess(errors[-1],2e-8)

    def test_no_coupling_or_no_concentration_preserves_baseline(self):
        for overrides in [{'hypothetical_gain':0},{'free_concentration_nm':0}]:
            report=self.report(**overrides)
            for example in report['examples'].values():
                self.assertTrue(all(p['relative_amount']==1 for p in example['points']))
        report=self.report(hypothetical_gain=0)
        self.assertGreater(report['examples']['faster_binding']['points'][1]['fraction_bound'],0)

    def test_exact_switch_binding_source_and_valid_extremes(self):
        report=calculate_binding_turnover(times_h=[0,3.37,5,24],pulse_duration_h=3.37,
            free_concentration_nm=100,loss_rate_h_inv=1,hypothetical_gain=10)
        for example in report['examples'].values():
            switch=example['points'][1];boundary=example['pulse_boundary']
            self.assertEqual(switch['free_concentration_nm'],0)
            self.assertEqual(switch['relative_amount'],boundary['relative_amount'])
            self.assertEqual(switch['fraction_bound'],boundary['fraction_bound'])
            for point,binding in zip(example['points'],example['binding_report']['points']):
                self.assertEqual(point['fraction_bound'],binding['fraction_bound'])
                self.assertTrue(math.isfinite(point['relative_amount']))
                self.assertTrue(0<=point['relative_amount']<=1+1e-12)
                self.assertAlmostEqual(point['loss_multiplier'],1+10*point['fraction_bound'])
            self.assertLessEqual(example['solver']['actual_max_step_h'],.01+1e-15)

    def test_deterministic_hashes_scope_and_no_input_mutation(self):
        times=[0,1,4,8,24];original=list(times)
        report=calculate_binding_turnover(times_h=times)
        self.assertEqual(report,calculate_binding_turnover(times_h=times));self.assertEqual(times,original)
        payloads=[report,*report['examples'].values()]+[e['binding_report'] for e in report['examples'].values()]
        for payload in payloads:
            saved=copy.deepcopy(payload);sha=saved.pop('report_sha256');self.assertEqual(sha,_hash(saved))
        self.assertIsNone(report['coupling_evidence']);self.assertEqual(report['coupling_status'],'explicit_unvalidated_hypothesis')
        self.assertEqual(report['pk_connection'],'not_connected')
        self.assertFalse(report['clinical_prediction_validated']);self.assertFalse(report['ready_for_patient_simulation'])

    def test_invalid_bounds_types_grids_and_unsupported_arguments(self):
        for overrides in [{'hypothetical_gain':-1},{'hypothetical_gain':True},
            {'free_concentration_nm':float('nan')},{'free_concentration_nm':101},
            {'loss_rate_h_inv':2},{'pulse_duration_h':24},{'max_step_h':0},
            {'times_h':[0,12]},{'times_h':[0,0,24]},{'times_h':list(range(1002))}]:
            with self.subTest(overrides=overrides),self.assertRaises(ValueError):calculate_binding_turnover(**overrides)
        with self.assertRaises(TypeError):calculate_binding_turnover(patient_id=1)

    def test_web_inspection_export_and_existing_routes_no_patient_calls(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        client=app.test_client();path='/landscape/patient-lab/binding-turnover-experiment'
        controls={'pulse_duration_h':3.37,'time_h':5.2,'hypothetical_gain':3}
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No patient PK')), \
             patch('requests.get',side_effect=AssertionError('No network')):
            page=client.get(path,query_string=controls)
            data=client.get(path,query_string={**controls,'format':'json'})
        self.assertEqual(page.status_code,200);self.assertEqual(data.status_code,200)
        text=page.get_data(as_text=True)
        self.assertIn('The connection is an assumption',text);self.assertEqual(text.count('<polyline'),4)
        self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(data.headers['Cache-Control'],'no-store')
        for example in data.json['examples'].values():self.assertTrue(any(p['time_h']==5.2 for p in example['points']))
        for query in ['patient_id=1','pk_run_id=1','time_h=25','time_h=nan','hypothetical_gain=11',
            'time_h=1&time_h=2','max_step_h=0.05','format=csv']:
            self.assertEqual(client.get(path+'?'+query).status_code,400)
        self.assertEqual(client.post(path).status_code,405)
        self.assertIn('binding-turnover-experiment',client.get('/landscape/patient-lab/turnover-experiment').get_data(as_text=True))


if __name__=='__main__':unittest.main()
