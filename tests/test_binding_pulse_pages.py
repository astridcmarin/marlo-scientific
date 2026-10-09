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
spec=importlib.util.spec_from_file_location('pulse_installer',ROOT/'scripts/install_binding_pulse_page.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


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

    def project(self,folder,bad=False):
        root=Path(folder)
        for asset in ['intelligence_store/target_binding_kinetics.py','intelligence_store/target_binding_schedule.py',
            'landscape_ui/binding_pulse_pages.py','landscape_ui/templates/landscape_binding_pulse_demo.html',
            'landscape_ui/static/target-binding-pulse.css']:
            path=root/asset;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('asset')
        paths=[root/'landscape_ui/__init__.py',root/'landscape_ui/templates/landscape_base.html',root/'landscape_ui/templates/landscape_patient_lab_overview.html']
        paths[0].write_text('custom initializer\n'+installer.REGISTER_ANCHOR+'\n    app.register_blueprint(bp)')
        paths[1].write_text('custom base\n'+installer.NAV_ANCHOR+"'landscape.binding_kinetics_demo', 'landscape.patient_lab'] %}")
        paths[2].write_text('custom overview\n'+('unrecognized' if bad else installer.OVERVIEW_ANCHOR))
        return root,paths

    def test_install_preserves_content_backup_modes_and_idempotence(self):
        with tempfile.TemporaryDirectory() as folder:
            root,paths=self.project(folder);original=[p.read_bytes() for p in paths]
            result=installer.install(root)
            self.assertEqual(result['status'],'installed')
            for p,raw in zip(paths,original):
                self.assertEqual((Path(result['code_backup_directory'])/p.relative_to(root)).read_bytes(),raw)
                self.assertIn('custom',p.read_text())
            self.assertIn('landscape.binding_kinetics_demo',paths[1].read_text())
            self.assertEqual(installer.install(root)['status'],'already_installed')

    def test_bad_final_anchor_leaves_existing_files_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root,paths=self.project(folder,True);before=[p.read_bytes() for p in paths]
            with self.assertRaises(ValueError):installer.install(root)
            self.assertEqual(before,[p.read_bytes() for p in paths])
            self.assertFalse((root/'instance').exists())


if __name__=='__main__':unittest.main()
