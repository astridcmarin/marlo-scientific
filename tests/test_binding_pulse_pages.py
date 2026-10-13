import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask

ROOT=Path(__file__).resolve().parents[1]


class BindingPulsePageTests(unittest.TestCase):
    def setUp(self):
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.client=app.test_client();self.path='/landscape/patient-lab/binding-pulse-demo'

    def test_page_export_and_scope_without_database_network_or_pk(self):
        from intelligence_store.extensions import db
        with patch.object(db.session,'get',side_effect=AssertionError('No database read')), \
             patch.object(db.session,'execute',side_effect=AssertionError('No database query')), \
             patch('requests.get',side_effect=AssertionError('No network')), \
             patch('intelligence_store.educational_pk_runs.calculate_educational_pk',side_effect=AssertionError('No PK calculation')):
            page=self.client.get(self.path);self.assertEqual(page.status_code,200)
            html=page.get_data(as_text=True)
            self.assertEqual(html.count('<svg '),2)
            self.assertEqual(html.count('class="nav-item active"'),1)
            self.assertIn('0.275336',html);self.assertIn('0.499832',html)
            url=re.search(r'href="([^"]+)">Download this comparison JSON',html).group(1).replace('&amp;','&')
            export=self.client.get(url);report=export.get_json()
            self.assertEqual(export.status_code,200)
            self.assertIn('attachment',export.headers['Content-Disposition'])
            self.assertEqual(export.headers['Cache-Control'],'no-store')
            self.assertEqual(export.headers['X-Content-Type-Options'],'nosniff')
            self.assertEqual(report['display']['curve_points'],202)
            for e in report['examples']:
                self.assertEqual(e['selected_point']['free_concentration_nm'],0)
                self.assertEqual(e['selected_point']['time_h'],4)
                self.assertIsNone(e['curve_report']['patient_revision_id'])
                boundary=e['curve_report']['boundaries'][1]
                self.assertEqual(boundary['before']['fraction_bound'],boundary['after']['fraction_bound'])
                self.assertIn(4,[p['time_h'] for p in e['curve_report']['points']])
            digest=report.pop('report_sha256')
            self.assertEqual(digest,hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest())
            self.assertIn(digest,html)

    def test_off_grid_exact_selection_and_boundary_concentration(self):
        for time in [0,.137,3.999,4,4.001,24]:
            report=self.client.get(self.path+f'?time_h={time}&format=json').get_json()
            for e,kon,koff in zip(report['examples'],[.01,.1],[.1,1]):
                point=e['selected_point'];rate=kon*10+koff
                expected=.5*(1-math.exp(-rate*time)) if time<4 else .5*(1-math.exp(-rate*4))*math.exp(-koff*(time-4))
                self.assertEqual(point['time_h'],time)
                self.assertEqual(point['free_concentration_nm'],10 if time<4 else 0)
                self.assertAlmostEqual(point['fraction_bound'],expected,places=15)
        a=self.client.get(self.path+'?time_h=.137&format=json').get_json()
        self.assertEqual(a,self.client.get(self.path+'?time_h=.137&format=json').get_json())
        self.assertNotIn(.137,[p['time_h'] for p in a['examples'][0]['curve_report']['points']])

    def test_invalid_and_patient_linking_inputs_fail(self):
        for query in ['time_h=-1','time_h=25','time_h=nan','time_h=inf','time_h=1e999',
            'time_h=true','time_h=','time_h=1&time_h=2','format=csv','format=json&format=json',
            'revision_id=1','pk_run_id=1','cohort_id=4','concentration_nm=10','dose_mg=25','time_h=%3Cscript%3E']:
            with self.subTest(query=query):self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)

if __name__=='__main__':unittest.main()
