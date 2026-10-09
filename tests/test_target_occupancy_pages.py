"""Strict generic inputs, matching exports and narrow backed-up installation."""
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
spec=importlib.util.spec_from_file_location('occupancy_installer',ROOT/'scripts/install_target_occupancy_page.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class TargetOccupancyPageTests(unittest.TestCase):
    def setUp(self):
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.client=app.test_client()
        self.path='/landscape/patient-lab/target-occupancy-demo'

    def test_page_and_export_match_without_database_network_or_pk_solve(self):
        from intelligence_store.extensions import db
        with patch.object(db.session,'get',side_effect=AssertionError('No database read')), \
             patch.object(db.session,'execute',side_effect=AssertionError('No database query')), \
             patch('requests.get',side_effect=AssertionError('No network')), \
             patch('intelligence_store.educational_pk_runs.calculate_educational_pk',side_effect=AssertionError('No PK solve')):
            page=self.client.get(self.path);self.assertEqual(page.status_code,200)
            html=page.get_data(as_text=True)
            self.assertIn('Invented inputs',html);self.assertIn('Fraction bound: <strong>0.5</strong>',html)
            self.assertIn('Free target-site concentration (nM)',html)
            self.assertEqual(html.count('<svg '),1)
            self.assertEqual(html.count('class="nav-item active"'),1)
            url=re.search(r'href="([^"]+)">Download this demonstration JSON',html).group(1).replace('&amp;','&')
            export=self.client.get(url);self.assertEqual(export.status_code,200)
            report=export.get_json()
            self.assertEqual(len(report['curve_report']['points']),201)
            self.assertEqual(report['selection_report']['points'][0]['fraction_bound'],.5)
            self.assertIs(report['curve_report']['pk_run_id'],None)
            sha=report.pop('report_sha256')
            self.assertEqual(sha,hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()).hexdigest())
            self.assertIn(sha,html)
            self.assertEqual(export.headers['Cache-Control'],'no-store')
            self.assertEqual(export.headers['X-Content-Type-Options'],'nosniff')

    def test_custom_selection_exact_equation_and_repeatability(self):
        url=self.path+'?kd_nm=5&max_nm=100&selected_nm=13&format=json'
        a=self.client.get(url).get_json();b=self.client.get(url).get_json()
        self.assertEqual(a,b)
        self.assertEqual(a['selection_report']['points'][0]['fraction_bound'],13/18)
        zero=self.client.get(self.path+'?selected_nm=0&format=json').get_json()
        leading=self.client.get(self.path+'?kd_nm=.5&selected_nm=00.5&format=json')
        self.assertEqual(leading.status_code,200)
        self.assertEqual(leading.get_json()['selection_report']['points'][0]['fraction_bound'],.5)
        self.assertEqual(zero['selection_report']['points'][0]['fraction_bound'],0)
        narrow=self.client.get(self.path+'?max_nm=1&format=json').get_json()
        self.assertEqual(narrow['selection_report']['points'][0]['free_concentration_nm'],1)

    def test_invalid_and_patient_linking_queries_rejected(self):
        for query in ['kd_nm=0','kd_nm=-1','kd_nm=nan','kd_nm=inf','kd_nm=1e999',
            'kd_nm=1&kd_nm=2','selected_nm=101','max_nm=0','max_nm=1e13',
            'kd_nm=1e-13','selected_nm=true','format=csv','revision_id=1','cohort_id=4','pk_run_id=1',
            'kd_nm=%3Cscript%3E','max_nm=1&selected_nm=2']:
            with self.subTest(query=query):self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)

    def project(self,folder,bad=False):
        root=Path(folder)
        for asset in ['intelligence_store/target_occupancy.py','landscape_ui/target_occupancy_pages.py',
            'landscape_ui/templates/landscape_target_occupancy_demo.html','landscape_ui/static/target-occupancy-demo.css']:
            path=root/asset;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('asset')
        paths=[root/'landscape_ui/__init__.py',root/'landscape_ui/templates/landscape_base.html',
            root/'landscape_ui/templates/landscape_patient_lab_overview.html']
        paths[0].write_text('custom initializer\n'+installer.REGISTER_ANCHOR+'\n    app.register_blueprint(bp)')
        paths[1].write_text('custom base\n'+installer.NAV_ANCHOR+"'landscape.patient_lab'] %}")
        paths[2].write_text('custom overview\n'+('unrecognized' if bad else installer.OVERVIEW_ANCHOR))
        return root,paths

    def test_install_preserves_all_custom_content_backups_and_idempotence(self):
        with tempfile.TemporaryDirectory() as folder:
            root,paths=self.project(folder);original=[p.read_bytes() for p in paths]
            result=installer.install(root);self.assertEqual(result['status'],'installed')
            for path,raw in zip(paths,original):
                self.assertEqual((Path(result['code_backup_directory'])/path.relative_to(root)).read_bytes(),raw)
                self.assertIn('custom',path.read_text())
            self.assertEqual(installer.install(root)['status'],'already_installed')

    def test_unknown_final_anchor_changes_none_of_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root,paths=self.project(folder,True);before=[p.read_bytes() for p in paths]
            with self.assertRaises(ValueError):installer.install(root)
            self.assertEqual([p.read_bytes() for p in paths],before)
            self.assertFalse((root/'instance').exists())


if __name__=='__main__':unittest.main()
