import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mechanism_installer',ROOT/'scripts/install_mechanism_map_page.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class MechanismMapTests(unittest.TestCase):
    def setUp(self):
        from landscape_ui import register_landscape
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.client=app.test_client();self.path='/landscape/patient-lab/lenalidomide-mechanism'

    def test_html_json_source_links_hashes_and_no_database_network_pk(self):
        from intelligence_store.extensions import db
        with patch.object(db.session,'get',side_effect=AssertionError('No database read')), \
             patch.object(db.session,'execute',side_effect=AssertionError('No query')), \
             patch('requests.get',side_effect=AssertionError('No retrieval')), \
             patch('intelligence_store.educational_pk_runs.calculate_educational_pk',side_effect=AssertionError('No PK calculation')):
            page=self.client.get(self.path);self.assertEqual(page.status_code,200)
            html=page.get_data(as_text=True)
            export=self.client.get(self.path+'?format=json');report=export.get_json()
            self.assertEqual(export.status_code,200)
            self.assertEqual(html.count('class="nav-item active"'),1)
            self.assertIn('Qualitative research map',html)
            self.assertEqual(export.headers['Cache-Control'],'no-store')
            self.assertIn('attachment',export.headers['Content-Disposition'])
            claims={c['claim_id'] for c in report['evidence_plan']['claims']}
            self.assertEqual(len(report['stages']),4)
            for stage in report['stages']:
                self.assertIn(stage['label'],html)
                self.assertTrue(set(stage['claim_ids'])<=claims)
            for claim in claims:self.assertIn('id="claim-'+claim+'"',html)
            for edge in report['relationships']:
                self.assertTrue(set(edge['claim_ids'])<=claims)
            self.assertIsNone(report['pk_run_id']);self.assertIsNone(report['patient_revision_id'])
            self.assertEqual(report['simulation_status'],'not_run')
            self.assertFalse(report['clinical_prediction_validated'])
            self.assertFalse(report['ready_for_patient_simulation'])
            self.assertIn(report['evidence_plan_sha256'],html)
            digest=report.pop('report_sha256')
            self.assertEqual(digest,hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
            self.assertIn(digest,html)

    def test_patient_links_unknown_duplicate_query_and_post_rejected(self):
        for query in ['format=csv','format=json&format=json','revision_id=1','pk_run_id=1','cohort_id=4','dose=25']:
            with self.subTest(query=query):self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)

    def test_missing_invalid_or_promoted_plan_fails_closed(self):
        import intelligence_store.mechanism_evidence as evidence
        plan=json.loads(evidence.PLAN_PATH.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'plan.json'
            with patch.object(evidence,'PLAN_PATH',path):
                self.assertEqual(self.client.get(self.path).status_code,503)
                variants=[]
                for key,value in [('clinical_prediction_validated',True),('ready_for_patient_simulation',True),('entity_id','other')]:
                    changed=copy.deepcopy(plan);changed[key]=value;variants.append(changed)
                changed=copy.deepcopy(plan);changed['quantitative_inputs']['binary_binding_kd_nm']=10;variants.append(changed)
                changed=copy.deepcopy(plan);changed['claims'][0]['source_id']='wrong';variants.append(changed)
                changed=copy.deepcopy(plan);changed['claims'].append(changed['claims'][0]);variants.append(changed)
                for changed in variants:
                    path.write_text(json.dumps(changed))
                    self.assertEqual(self.client.get(self.path+'?format=json').status_code,503)
                for bad in ['{"schema_version":"x","schema_version":"y"}','{"value":NaN}','[]','{']:
                    path.write_text(bad);self.assertEqual(self.client.get(self.path).status_code,503)

    def test_report_is_deterministic_and_does_not_modify_plan(self):
        from intelligence_store.mechanism_evidence import PLAN_PATH,build_mechanism_map
        old=PLAN_PATH.read_bytes();a=build_mechanism_map();b=build_mechanism_map()
        self.assertEqual(a,b);self.assertEqual(PLAN_PATH.read_bytes(),old)
        self.assertEqual(a['evidence_plan_sha256'],hashlib.sha256(old).hexdigest())

    def fixture(self,folder,bad=False):
        root=Path(folder)
        for asset in ['intelligence_store/mechanism_evidence.py','intelligence_store/data/lenalidomide_mechanism_evidence_plan_v1.json',
            'landscape_ui/mechanism_map_pages.py','landscape_ui/templates/landscape_mechanism_map_demo.html',
            'landscape_ui/static/target-mechanism-map.css']:
            path=root/asset;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('asset')
        paths=[root/'landscape_ui/__init__.py',root/'landscape_ui/templates/landscape_base.html',root/'landscape_ui/templates/landscape_patient_lab_overview.html']
        paths[0].write_text('custom initializer\n'+installer.REGISTER_ANCHOR+'\n    app.register_blueprint(bp)')
        paths[1].write_text('custom base\n'+installer.NAV_ANCHOR+"'landscape.binding_pulse_demo', 'landscape.patient_lab'] %}")
        paths[2].write_text('custom overview\n'+('unknown' if bad else installer.OVERVIEW_ANCHOR))
        return root,paths

    def test_install_backup_custom_content_preservation_and_idempotence(self):
        with tempfile.TemporaryDirectory() as folder:
            root,paths=self.fixture(folder);before=[p.read_bytes() for p in paths]
            result=installer.install(root);self.assertEqual(result['status'],'installed')
            for p,raw in zip(paths,before):
                self.assertIn('custom',p.read_text())
                self.assertEqual((Path(result['code_backup_directory'])/p.relative_to(root)).read_bytes(),raw)
            self.assertIn('landscape.binding_pulse_demo',paths[1].read_text())
            self.assertEqual(installer.install(root)['status'],'already_installed')

    def test_unrecognized_anchor_changes_none_of_the_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root,paths=self.fixture(folder,True);before=[p.read_bytes() for p in paths]
            with self.assertRaises(ValueError):installer.install(root)
            self.assertEqual(before,[p.read_bytes() for p in paths]);self.assertFalse((root/'instance').exists())


if __name__=='__main__':unittest.main()
