"""Revision lineage, retries and integrity preserve prior synthetic inputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from sqlalchemy import select, update, delete, inspect
from sqlalchemy.exc import IntegrityError
from flask import Flask, current_app
from datetime import datetime
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_scenarios import load_scenario_presets
from intelligence_store.saved_scenarios import analyze_for_save, save_scenario
from intelligence_store.extensions import db
from intelligence_store.patient_state import example_state, digest, state_from_scenario
from intelligence_store.patient_state_revisions import (PatientStateRevision, save_revision,
    read_revision, export_revision, register_patient_state_revision_commands)
from intelligence_store.validation import validate_platform


class PatientStatePageTests(unittest.TestCase):
    def setUp(self):
            app = Flask(__name__)
            app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', INTELLIGENCE_WORKSPACE_SECRET='web-test-secret-31')
            app.add_url_rule('/', 'home', lambda: 'Home')
            from landscape_ui import register_landscape
            register_landscape(app)
            self.app=app
            self.client=app.test_client()
            db.init_app(app)
            self.context = app.app_context()
            self.context.push()
            db.create_all()
            db.session.add(AnalysisCohort(id=1, condition='Synthetic example',
                api_url='https://clinicaltrials.gov/api/v2/studies', query_params={'query.cond': 'Example'},
                query_version='qa-v1', normalization_version='qa-v1', scope='all-studies',
                max_pages=1, status='COMPLETE', expected_count=1, retrieved_count=1,
                pages_fetched=1, page_log=[], finished_at_utc=datetime(2026, 10, 7)))
            raw = {'protocolSection': {
                'identificationModule': {'nctId': 'NCT00000001', 'briefTitle': 'Frozen title'},
                'statusModule': {'overallStatus': 'RECRUITING'},
                'designModule': {'studyType': 'INTERVENTIONAL'},
                'armsInterventionsModule': {'interventions': [{'type': 'DRUG', 'name': 'Lenalidomide'}]},
                'eligibilityModule': {'minimumAge': '18 Years', 'maximumAge': '80 Years', 'sex': 'ALL'}}}
            snap = TrialSnapshot(nct_id='NCT00000001', source_url='https://clinicaltrials.gov/study/NCT00000001', raw_study=raw)
            db.session.add(snap)
            db.session.flush()
            self.snapshot_id = snap.id
            db.session.add(CohortTrial(cohort_id=1, nct_id=snap.nct_id, snapshot_id=snap.id))
            db.session.commit()
            self.profile = load_scenario_presets()['index']['interaction-reference']['profile']
            self.analysis = analyze_for_save(1, self.profile)
            self.profile = self.analysis['report']['profile']

    def save_scenario(self, key='a'):
            return save_scenario('Invented profile', 1, self.profile, digest(self.analysis), key*64)

    def tearDown(self):
        # Explicit test-only cleanup, descendants first. SQLite DROP TABLE
        # otherwise conflicts with the intentional self-FK RESTRICT links.
        db.session.rollback()
        if inspect(db.engine).has_table(PatientStateRevision.__tablename__):
            ids=list(db.session.scalars(select(PatientStateRevision.id)
                        .order_by(PatientStateRevision.revision_number.desc())))
            for item in ids:
                db.session.execute(delete(PatientStateRevision).where(PatientStateRevision.id==item))
            db.session.commit()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def setup_scenario(self):
        self.scenario=self.save_scenario()
        self.base=state_from_scenario(self.scenario.payload['analysis']['report']['profile'])
        self.path=f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state'
        return self.scenario

    def form(self):
        import re
        response=self.client.get(self.path)
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        data={key:re.search(r'name="'+key+r'" value="([^"]*)"',html).group(1) for key in ('form_token','ticket')}
        latest=db.session.scalar(select(PatientStateRevision).order_by(PatientStateRevision.revision_number.desc()))
        state=latest.payload['state'] if latest else self.base
        data['title']='Web baseline'
        for name,field in state['fields'].items():
            for prefix,key in [('value','value'),('origin','origin'),('time','observed_at'),('source','source_ref')]:
                data[prefix+'__'+name]='' if field[key] is None else str(field[key])
        return data

    def post(self,data):
        return self.client.post(self.path+'/save',data=data)

    def test_baseline_append_export_and_retry_leave_report_unchanged(self):
        self.setup_scenario();before=copy.deepcopy(self.scenario.payload)
        panel=self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}')
        self.assertIn(b'Create baseline patient state',panel.data)
        data=self.form();response=self.post(data)
        self.assertEqual(response.status_code,303)
        detail=self.client.get(response.location)
        self.assertEqual(detail.status_code,200)
        self.assertIn(b'Unknown',detail.data)
        export=self.client.get(response.location+'?format=json')
        self.assertEqual(export.json,export_revision(1))
        self.assertEqual(export.headers['Cache-Control'],'no-store')
        self.assertEqual(self.post(data).location,response.location)
        nextform=self.form();nextform.update({'title':'Height added','value__height':'165','origin__height':'synthetic_input'})
        self.assertEqual(self.post(nextform).status_code,303)
        self.assertEqual(read_revision(2).revision_number,2)
        self.assertEqual(self.scenario.payload,before)
        self.assertEqual(read_revision(1).payload['state'],self.base)
        original=self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}?format=json')
        self.assertEqual(original.json['payload'],before)

    def test_copied_value_edit_requires_new_origin_and_preserves_entries(self):
        self.setup_scenario();data=self.form();data['value__age_years']='71'
        response=self.post(data);self.assertEqual(response.status_code,400)
        self.assertIn(b'changed copied inputs',response.data)
        self.assertIn(b'value="71"',response.data)
        self.assertEqual(db.session.query(PatientStateRevision).count(),0)
        data['origin__age_years']='synthetic_input'
        self.assertEqual(self.post(data).status_code,303)

    def test_zero_and_unknown_are_distinct_and_assumptions_need_reference(self):
        self.setup_scenario();data=self.form();data.update({'value__egfr_indexed':'0','origin__egfr_indexed':'synthetic_input','value__height':'165','origin__height':'assumption'})
        self.assertEqual(self.post(data).status_code,400)
        data['source__height']='Teaching assumption'
        response=self.post(data);self.assertEqual(response.status_code,303)
        state=read_revision(1).payload['state']['fields']
        self.assertEqual(state['egfr_indexed']['value'],0)
        self.assertIsNone(state['serum_creatinine']['value'])
        self.assertIn(b'<td>0.0</td>',self.client.get(response.location).data)

    def test_invalid_values_fields_and_missing_title_do_not_save(self):
        self.setup_scenario();baseline=self.form()
        for changes in ({'value__height':'nan','origin__height':'synthetic_input'}, {'unit__height':'m'}, {'title':''}):
            data=dict(baseline);data.update(changes)
            self.assertEqual(self.post(data).status_code,400)
        self.assertEqual(db.session.query(PatientStateRevision).count(),0)

    def test_security_ticket_origin_and_cross_scenario(self):
        self.setup_scenario();data=self.form()
        for key in ('form_token','ticket'):
            bad=dict(data);bad[key]='bad';self.assertEqual(self.post(bad).status_code,403)
        self.assertEqual(self.client.post(self.path+'/save',data=data,headers={'Origin':'https://other.test'}).status_code,403)
        good=self.post(data);self.assertEqual(good.status_code,303)
        other=self.save_scenario('b')
        self.assertEqual(self.client.get(f'/landscape/workspace/scenarios/{other.id}/patient-state/revisions/1').status_code,404)

    def test_stale_form_keeps_entries_without_branching(self):
        self.setup_scenario();data=self.form();self.post(data)
        stale=self.form();first=read_revision(1)
        state=copy.deepcopy(first.payload['state']);state['fields']['height'].update(value=165,origin='synthetic_input')
        save_revision(self.scenario.id,state,parent_revision_id=first.id,title='Concurrent revision')
        stale.update({'title':'Stale change','value__height':'170','origin__height':'synthetic_input'})
        response=self.post(stale);self.assertEqual(response.status_code,409)
        self.assertIn(b'value="170"',response.data)
        self.assertEqual(db.session.query(PatientStateRevision).count(),2)

    def test_corrupt_revision_does_not_hide_original_scenario(self):
        self.setup_scenario();self.post(self.form())
        db.session.execute(update(PatientStateRevision).where(PatientStateRevision.id==1).values(title='Tampered'));db.session.commit();db.session.expire_all()
        self.assertEqual(self.client.get(self.path+'/revisions/1').status_code,409)
        page=self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}')
        self.assertEqual(page.status_code,200)
        self.assertIn(b'Saved criteria records',page.data)
        self.assertEqual(self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}?format=json').status_code,200)

    def test_history_pagination_and_read_only_gets(self):
        self.setup_scenario();parent=None
        for i in range(26):
            row=save_revision(self.scenario.id,self.base,parent_revision_id=parent,title=f'Revision {i+1}')
            parent=row.id
        response=self.client.get(self.path+'?page=2');self.assertEqual(response.status_code,200)
        self.assertIn(b'Page 2 of 2',response.data)
        self.assertEqual(self.client.get(self.path+'?page=3').status_code,404)
        self.assertEqual(db.session.query(PatientStateRevision).count(),26)

    def test_missing_state_table_preserves_original_report(self):
        self.setup_scenario()
        PatientStateRevision.__table__.drop(db.engine)
        self.assertEqual(self.client.get(self.path).status_code,409)
        response=self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Saved criteria records',response.data)
        self.assertEqual(self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}?format=json').status_code,200)

    def test_reads_need_no_catalog_or_network_and_escape_titles(self):
        from unittest.mock import patch
        self.setup_scenario();data=self.form();data['title']='<script>alert(1)</script>'
        saved=self.post(data)
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            with patch('intelligence_store.patient_scenarios.load_scenario_presets',side_effect=AssertionError('No catalog')):
                response=self.client.get(saved.location)
                self.assertEqual(response.status_code,200)
                self.assertIn(b'&lt;script&gt;',response.data)
                self.assertNotIn(b'<script>alert(1)</script>',response.data)
                editor=self.client.get(self.path)
                self.assertEqual(editor.status_code,200)
                self.assertEqual(editor.text.count('class="nav-item active"'),1)

if __name__=='__main__':unittest.main()
