"""Independent binding reference, pulse reproduction and numerical controls."""
import copy
import math
import unittest
from unittest.mock import patch
from intelligence_store.site_exposure_response import calculate_site_response
from intelligence_store.binding_turnover import calculate_binding_turnover
from intelligence_store.target_binding_kinetics import _hash


def independent_declining_binding(kon,koff,c0,half_life,time):
    """Integrating-factor quadrature for time-varying binding; not RK4."""
    rate=math.log(2)/half_life
    def cumulative(t):return kon*c0*(-math.expm1(-rate*t))/rate+koff*t
    total=cumulative(time);n=32768;h=time/n
    values=[kon*c0*math.exp(-rate*i*h)*math.exp(cumulative(i*h)-total) for i in range(n+1)]
    return h/3*(values[0]+values[-1]+4*sum(values[1:-1:2])+2*sum(values[2:-1:2]))


class SiteExposureResponseTests(unittest.TestCase):
    def calculate(self,**overrides):
        options=dict(times_h=[0,1,2,4,8,24]);options.update(overrides)
        return calculate_site_response(**options)

    def test_declining_concentration_and_independent_binding_reference(self):
        report=self.calculate()
        for name,kon,koff in [('slower_binding',.01,.1),('faster_binding',.1,1)]:
            points=report['examples'][name]['points']
            self.assertEqual(points[2]['free_concentration_nm'],5)
            self.assertTrue(all(a['free_concentration_nm']>=b['free_concentration_nm'] for a,b in zip(points,points[1:])))
            for t in [4,24]:
                actual=next(p['fraction_bound'] for p in points if p['time_h']==t)
                reference=independent_declining_binding(kon,koff,10,2,t)
                self.assertAlmostEqual(actual,reference,delta=2e-8)

    def test_pulse_reproduces_existing_analytic_binding_and_downstream_math(self):
        times=[0,1,3.37,8,24]
        new=calculate_site_response(profile='pulse',profile_time_h=3.37,times_h=times)
        old=calculate_binding_turnover(pulse_duration_h=3.37,times_h=times)
        for name in old['examples']:
            for a,b in zip(new['examples'][name]['points'],old['examples'][name]['points']):
                self.assertEqual(a['free_concentration_nm'],b['free_concentration_nm'])
                self.assertAlmostEqual(a['fraction_bound'],b['fraction_bound'],delta=2e-8)
                self.assertAlmostEqual(a['relative_amount'],b['relative_amount'],delta=2e-8)
            boundary=new['examples'][name]['pulse_boundary']
            self.assertEqual(boundary['relative_amount'],new['examples'][name]['points'][2]['relative_amount'])
            self.assertEqual(new['examples'][name]['points'][2]['free_concentration_nm'],0)

    def test_step_refinement_and_finite_extreme_case(self):
        reference=independent_declining_binding(.1,1,10,2,4)
        errors=[]
        for step in [.05,.025,.0125]:
            data=self.calculate(max_step_h=step)
            point=next(p for p in data['examples']['faster_binding']['points'] if p['time_h']==4)
            errors.append(abs(point['fraction_bound']-reference))
        self.assertGreater(errors[0],errors[1]);self.assertGreater(errors[1],errors[2])
        extreme=self.calculate(initial_concentration_nm=100,profile_time_h=.1,loss_rate_h_inv=1,hypothetical_gain=10)
        for example in extreme['examples'].values():
            for p in example['points']:
                self.assertTrue(math.isfinite(p['relative_amount']));self.assertTrue(0<=p['fraction_bound']<=1)
                self.assertTrue(0<=p['relative_amount']<=1+1e-12)

    def test_no_effect_controls_for_both_profiles(self):
        for profile in ['decay','pulse']:
            for overrides in [{'hypothetical_gain':0},{'initial_concentration_nm':0}]:
                data=self.calculate(profile=profile,**overrides)
                for example in data['examples'].values():
                    self.assertTrue(all(p['relative_amount']==1 for p in example['points']))

    def test_identity_scope_hashes_input_preservation_and_missing_pulse_boundary(self):
        times=[0,1,2,4,8,24];old=list(times)
        report=calculate_site_response(times_h=times)
        self.assertEqual(times,old);self.assertEqual(report,calculate_site_response(times_h=times))
        for payload in [report,*report['examples'].values()]:
            saved=copy.deepcopy(payload);sha=saved.pop('report_sha256');self.assertEqual(sha,_hash(saved))
        self.assertEqual(report['inputs']['profile_time_meaning'],'prescribed concentration half-life')
        self.assertIsNone(report['coupling_evidence']);self.assertEqual(report['pk_connection'],'not_connected')
        self.assertFalse(report['clinical_prediction_validated']);self.assertFalse(report['ready_for_patient_simulation'])
        for example in report['examples'].values():self.assertIsNone(example['pulse_boundary'])
        pulse=self.calculate(profile='pulse',profile_time_h=3.37)
        for example in pulse['examples'].values():self.assertEqual(example['pulse_boundary']['time_h'],3.37)

    def test_invalid_values_grids_and_unsupported_patient_arguments(self):
        for overrides in [{'profile':'unknown'},{'profile_time_h':0},{'profile_time_h':float('nan')},
            {'initial_concentration_nm':True},{'initial_concentration_nm':101},
            {'hypothetical_gain':-1},{'loss_rate_h_inv':2},{'max_step_h':0},
            {'times_h':[0,12]},{'times_h':[0,0,24]},{'times_h':list(range(1002))}]:
            with self.subTest(overrides=overrides),self.assertRaises(ValueError):calculate_site_response(**overrides)
        with self.assertRaises(TypeError):calculate_site_response(pk_run_id=1)

    def test_web_controls_exact_inspection_export_and_old_routes_without_storage(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        client=app.test_client();path='/landscape/patient-lab/site-exposure-experiment'
        controls={'profile':'decay','profile_time_h':1.7,'time_h':3.37,'hypothetical_gain':3}
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No patient PK')), \
             patch('requests.get',side_effect=AssertionError('No network')):
            page=client.get(path,query_string=controls);exported=client.get(path,query_string={**controls,'format':'json'})
        self.assertEqual(page.status_code,200);self.assertEqual(exported.status_code,200)
        text=page.get_data(as_text=True)
        self.assertEqual(text.count('<polyline'),5);self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertIn('not a measured drug elimination process',text)
        data=exported.json;self.assertEqual(data['inspection']['time_h'],3.37)
        self.assertEqual(data['inputs']['profile_time_h'],1.7)
        sha=data.pop('report_sha256');self.assertEqual(sha,_hash(data))
        self.assertEqual(exported.headers['Cache-Control'],'no-store')
        pulse=client.get(path,query_string={'profile':'pulse','profile_time_h':3.37,'time_h':3.37,'format':'json'}).json
        for point in pulse['inspection']['points'].values():self.assertEqual(point['free_concentration_nm'],0)
        for query in ['patient_id=1','pk_run_id=1','time_h=nan','time_h=25','profile=organ',
            'profile_time_h=0','time_h=1&time_h=2','max_step_h=0.05','format=csv']:
            self.assertEqual(client.get(path+'?'+query).status_code,400)
        self.assertEqual(client.post(path).status_code,405)
        self.assertIn('site-exposure-experiment',client.get('/landscape/patient-lab/binding-turnover-experiment').get_data(as_text=True))


if __name__=='__main__':unittest.main()
