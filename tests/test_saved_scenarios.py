"""Saved synthetic results remain usable independently of current analysis data."""
import copy
from datetime import datetime
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_scenarios import load_scenario_presets
from intelligence_store.regulatory import digest
from intelligence_store.saved_scenarios import (SavedPatientScenario, analyze_for_save,
    save_scenario, read_scenario, scenarios_ready)


class SavedScenarioTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
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

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def save(self, key='a'):
        return save_scenario('Invented profile', 1, self.profile, digest(self.analysis), key*64)

    def test_frozen_report_and_manifest_are_self_contained(self):
        row = self.save()
        report = row.payload['analysis']['report']
        self.assertEqual(report['reference_trials']['count'], 1)
        self.assertEqual(report['criteria']['records'][0]['minimum_age']['raw_value'], '18 Years')
        ref = row.payload['analysis']['source_manifest']['NCT00000001']
        self.assertEqual(ref['raw_study_sha256'], digest(db.session.get(TrialSnapshot, self.snapshot_id).raw_study))
        saved = copy.deepcopy(row.payload)
        snap = db.session.get(TrialSnapshot, self.snapshot_id)
        snap.raw_study = {'changed': True}
        db.session.commit()
        # Catalog loading/source summary is not needed to reopen or retry a save.
        with patch('intelligence_store.saved_scenarios.analyze_for_save', side_effect=AssertionError('must not recalculate')):
            self.assertEqual(read_scenario(row.id).payload, saved)
            self.assertEqual(self.save().id, row.id)
        self.assertEqual(db.session.query(SavedPatientScenario).count(), 1)

    def test_changed_source_between_prepare_and_save_is_rejected(self):
        snap = db.session.get(TrialSnapshot, self.snapshot_id)
        raw = copy.deepcopy(snap.raw_study)
        raw['protocolSection']['eligibilityModule']['minimumAge'] = '100 Years'
        snap.raw_study = raw
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'changed after preparation'):
            self.save()
        self.assertEqual(db.session.query(SavedPatientScenario).count(), 0)

    def test_reuse_is_separate_and_does_not_replace_saved_profile(self):
        first = self.save()
        old = copy.deepcopy(first.payload)
        changed = copy.deepcopy(self.profile)
        changed['age_years'] = 99
        analysis = analyze_for_save(1, changed)
        second = save_scenario('Another invented profile', 1, analysis['report']['profile'], digest(analysis), 'b'*64)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(read_scenario(first.id).payload, old)
        self.assertEqual(second.payload['analysis']['report']['criteria']['records'][0]['combined_result'], 'outside')

    def test_duplicate_form_with_changed_inputs_is_rejected(self):
        self.save()
        with self.assertRaisesRegex(ValueError, 'different scenario'):
            save_scenario('Changed title', 1, self.profile, digest(self.analysis), 'a'*64)

    def test_payload_tampering_and_missing_table_are_detected(self):
        row = self.save()
        p = copy.deepcopy(row.payload)
        p['analysis']['report']['profile']['age_years'] = 1
        row.payload = p
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'integrity'):
            read_scenario(row.id)
        db.session.remove()
        SavedPatientScenario.__table__.drop(db.engine)
        with self.assertRaisesRegex(ValueError, 'Step 21'):
            scenarios_ready()

    def test_invalid_profile_title_and_cohort_do_not_write(self):
        for profile in [{**self.profile, 'purpose': 'clinical'}, {**self.profile, 'age_years': float('nan')}, {**self.profile, 'name': 'not allowed'}]:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                analyze_for_save(1, profile)
        for title in ['', 'x'*161, 'two\nlines']:
            with self.subTest(title=title), self.assertRaises(ValueError):
                save_scenario(title, 1, self.profile, digest(self.analysis), 'c'*64)
        with self.assertRaises(ValueError):
            analyze_for_save(True, self.profile)
        db.session.get(AnalysisCohort, 1).status = 'FAILED'
        db.session.commit()
        with self.assertRaises(ValueError):
            analyze_for_save(1, self.profile)
        self.assertEqual(db.session.query(SavedPatientScenario).count(), 0)


if __name__ == '__main__':
    unittest.main()
