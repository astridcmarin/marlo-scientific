import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from intelligence_store import bortezomib_timecourse as model

class TimecourseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=model.build_timecourse()
    def test_mass_balance_nonnegative_and_exact_boluses(self):
        r=self.report;rows=r['points'];self.assertLess(r['maximum_mass_balance_error_mg'],1e-10)
        events=[i for i,x in enumerate(rows) if x['phase']=='post_dose']
        self.assertEqual([rows[i]['time_h'] for i in events],[0,72,168,240])
        for i in events:
            before,after=rows[i-1],rows[i]
            self.assertEqual(before['time_h'],after['time_h'])
            self.assertAlmostEqual(after['central_mg']-before['central_mg'],2.327)
            for key in ['peripheral_2_mg','peripheral_3_mg','eliminated_mg','elimination_rate_per_h']:self.assertEqual(before[key],after[key])
        for row in rows:
            for key in ['central_mg','peripheral_2_mg','peripheral_3_mg','eliminated_mg']:self.assertGreaterEqual(row[key],0)
            self.assertGreaterEqual(row['activity_percent'],28.9-1e-12);self.assertLessEqual(row['activity_percent'],100)
        self.assertAlmostEqual(rows[-1]['administered_mg'],9.308)
    def test_baseline_unit_conversion_and_continuous_clock(self):
        rows=self.report['points'];self.assertEqual(rows[0]['activity_percent'],100)
        self.assertAlmostEqual(rows[1]['concentration_nm'],2.327/19.1*1e6/384.24)
        ref=self.report['reference']
        self.assertEqual(model.elimination_rate(0,ref),3.72)
        self.assertAlmostEqual(model.elimination_rate(1,ref),1.08+(3.72-1.08)/__import__('math').e)
        self.assertAlmostEqual(model.elimination_rate(72,ref),1.08)
        self.assertEqual(ref['assumed_relaxation_rate_per_h'],1)
    def test_finer_step_convergence(self):
        finer=model.build_timecourse(max_step_h=0.01)
        for a,b in zip(self.report['points'],finer['points']):
            self.assertEqual((a['time_h'],a['phase']),(b['time_h'],b['phase']))
            self.assertLess(abs(a['concentration_nm']-b['concentration_nm']),0.001)
            self.assertLess(abs(a['activity_percent']-b['activity_percent']),0.001)
    def test_provenance_and_no_readiness_promotion(self):
        r=dict(self.report);digest=r.pop('report_sha256')
        self.assertEqual(digest,hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
        for key in ['source_reproduction_established','clinical_prediction_validated','ready_for_patient_simulation','empirical_validation']:self.assertFalse(r[key])
        self.assertTrue(r['equation_4_review_required']);self.assertIsNone(r['patient_id'])
        self.assertIsNone(r['efficacy_prediction']);self.assertIsNone(r['toxicity_prediction'])
    def test_missing_or_corrupt_source_and_bad_steps(self):
        for step in [0,-1,1,True,float('nan'),float('inf'),'0.01']:
            with self.assertRaises(ValueError):model.build_timecourse(max_step_h=step)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json'
            with patch.object(model,'REFERENCE_PATH',p):
                with self.assertRaises(ValueError):model.build_timecourse()
                p.write_text('{}')
                with self.assertRaises(ValueError):model.build_timecourse()

class PageTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True;app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.client=app.test_client();self.path='/landscape/simulation-lab/bortezomib-timecourse'
    def test_html_export_and_navigation(self):
        r=self.client.get(self.path);self.assertEqual(r.status_code,200)
        text=r.get_data(as_text=True);self.assertEqual(text.count('<svg '),2)
        self.assertIn('time scale',text);self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        report=self.client.get(self.path+'?format=json').json
        self.assertFalse(report['ready_for_patient_simulation'])
        self.assertIn(self.path,self.client.get('/landscape/simulation-lab/bortezomib-figure-review').get_data(as_text=True))
    def test_reject_inputs_and_withhold_on_source_failure(self):
        for q in ['dose=2','patient_id=1','format=json&format=html','format=csv']:
            self.assertEqual(self.client.get(self.path+'?'+q).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)
        with patch('landscape_ui.bortezomib_timecourse_pages.build_timecourse',side_effect=ValueError()):self.assertEqual(self.client.get(self.path).status_code,503)
if __name__=='__main__':unittest.main()
