"""Strict generic inputs and matching exports."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask

ROOT=Path(__file__).resolve().parents[1]


class BindingKineticsPageTests(unittest.TestCase):
    def setUp(self):
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.client=app.test_client()
        self.path='/landscape/patient-lab/binding-kinetics-demo'

    def test_page_and_export_match_without_database_network_or_pk_solve(self):
        from intelligence_store.extensions import db
        with patch.object(db.session,'get',side_effect=AssertionError('No database read')), \
             patch.object(db.session,'execute',side_effect=AssertionError('No database query')), \
             patch('requests.get',side_effect=AssertionError('No network')), \
             patch('intelligence_store.educational_pk_runs.calculate_educational_pk',side_effect=AssertionError('No PK solve')):
            page=self.client.get(self.path);self.assertEqual(page.status_code,200)
            html=page.get_data(as_text=True)
            self.assertIn('Two invented systems',html);self.assertIn('0.0906346',html);self.assertIn('0.432332',html)
            self.assertIn('Elapsed binding time (h)',html)
            self.assertEqual(html.count('<svg '),1)
            self.assertEqual(html.count('class="nav-item active"'),1)
            url=re.search(r'href="([^"]+)">Download this comparison JSON',html).group(1).replace('&amp;','&')
            export=self.client.get(url);self.assertEqual(export.status_code,200)
            report=export.get_json()
            self.assertEqual(len(report['examples']),2)
            for e in report['examples']:
                self.assertEqual(len(e['curve_report']['points']),201)
                self.assertEqual(e['selection_report']['points'][-1]['time_h'],1)
                self.assertEqual(e['curve_report']['derived']['kd_nm'],10)
                self.assertIs(e['curve_report']['pk_run_id'],None)
            sha=report.pop('report_sha256')
            self.assertEqual(sha,hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()).hexdigest())
            self.assertIn(sha,html)
            self.assertEqual(export.headers['Cache-Control'],'no-store')
            self.assertEqual(export.headers['X-Content-Type-Options'],'nosniff')

    def test_custom_initial_state_and_off_grid_selection_exact_solution(self):
        import math
        url=self.path+'?concentration_nm=20&initial_fraction=1&horizon_h=4&time_h=.137&format=json'
        a=self.client.get(url).get_json();b=self.client.get(url).get_json()
        self.assertEqual(a,b)
        for e,rate in zip(a['examples'],[.3,3]):
            selected=e['selection_report']['points'][-1]
            self.assertAlmostEqual(selected['fraction_bound'],2/3+(1/3)*math.exp(-rate*.137),places=15)
            self.assertEqual(e['curve_report']['points'][0]['fraction_bound'],1)
            self.assertNotIn(.137,[p['time_h'] for p in e['curve_report']['points']])
        zero=self.client.get(self.path+'?time_h=0&initial_fraction=.8&format=json').get_json()
        self.assertTrue(all(e['selection_report']['points'][0]['fraction_bound']==.8 for e in zero['examples']))
        narrow=self.client.get(self.path+'?horizon_h=.5&format=json').get_json()
        self.assertEqual(narrow['display']['selected_time_h'],.5)
        decay=self.client.get(self.path+'?concentration_nm=0&initial_fraction=1&format=json').get_json()
        self.assertTrue(all(e['curve_report']['points'][-1]['fraction_bound']<1 for e in decay['examples']))

    def test_invalid_and_patient_linking_queries_rejected(self):
        for query in ['concentration_nm=-1','concentration_nm=1e7','concentration_nm=nan','horizon_h=inf',
            'horizon_h=0','horizon_h=73','time_h=25','time_h=1&time_h=2','initial_fraction=1.1',
            'initial_fraction=true','format=csv','revision_id=1','cohort_id=4','pk_run_id=1','kon=.1',
            'time_h=%3Cscript%3E','horizon_h=1&time_h=2']:
            with self.subTest(query=query):self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)

if __name__=='__main__':unittest.main()
