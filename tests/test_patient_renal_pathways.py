"""Simulation 2.0b: lenalidomide elimination pathways for a saved synthetic patient."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kim_pk_runs as fixtures  # noqa: E402

from intelligence_store.lenalidomide_renal_pathways import calibrate, load_evidence, pathways
from intelligence_store.patient_renal_pathways import patient_renal_pathways
from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.run_record import record_for_renal_pathways


class PatientPathways(unittest.TestCase):
    setUp = fixtures.KimPKRunTests.setUp
    tearDown = fixtures.KimPKRunTests.tearDown

    def revision_with(self, **kw):
        parent = getattr(self, '_latest', self.revision)
        self._latest = save_revision(self.scenario.id, fixtures.full_state(**kw), parent_revision_id=parent.id, title=str(kw))
        return self._latest

    def test_completed_view_uses_the_estimate_and_the_intact_nephron_reading(self):
        v = patient_renal_pathways(self.revision_with(serum_creatinine=60).id)
        self.assertEqual(v['status'], 'completed')
        crcl = v['covariate_estimate']['estimates']['creatinine_clearance']['value']
        expected = pathways(calibrate(load_evidence(), 110.0, 0.77), crcl, 'A_intact_nephron')
        self.assertAlmostEqual(v['pathways_ml_min']['total_ml_min'], expected['total_ml_min'], places=9)
        self.assertAlmostEqual(sum(v['shares'].values()), 1.0, places=12)
        self.assertAlmostEqual(v['normal_reference']['fe'], 0.85, places=9)
        self.assertAlmostEqual(v['relative_exposure_same_dose'], v['calibration']['total_ml_min'] / v['pathways_ml_min']['total_ml_min'])
        self.assertIs(v['clinical_prediction_validated'], False)

    def test_lower_kidney_function_shifts_elimination_away_from_urine(self):
        a = patient_renal_pathways(self.revision_with(serum_creatinine=60).id)
        b = patient_renal_pathways(self.revision_with(serum_creatinine=250).id)
        self.assertLess(b['fraction_excreted_unchanged'], a['fraction_excreted_unchanged'])
        self.assertGreater(b['shares']['non_renal'], a['shares']['non_renal'])
        self.assertGreater(b['relative_exposure_same_dose'], a['relative_exposure_same_dose'])

    def test_moderate_range_warns_that_renal_elimination_is_probably_lower(self):
        v = patient_renal_pathways(self.revision_with(serum_creatinine=120).id)
        self.assertTrue(30 <= v['crcl_ml_min'] < 50)
        self.assertTrue(any('probably smaller' in w for w in v['warnings']))

    def test_end_stage_range_carries_the_esrd_and_dialysis_note(self):
        v = patient_renal_pathways(self.revision_with(serum_creatinine=600).id)
        self.assertLess(v['crcl_ml_min'], 10)
        self.assertTrue(any('39% of the dose' in w for w in v['warnings']))

    def test_missing_inputs_are_reported_not_filled(self):
        state = copy.deepcopy(fixtures.full_state())
        state['fields']['serum_creatinine'] = {'value': None, 'unit': state['fields']['serum_creatinine']['unit'],
                                               'origin': 'unknown', 'observed_at': None, 'source_ref': None}
        parent = getattr(self, '_latest', self.revision)
        rev = save_revision(self.scenario.id, state, parent_revision_id=parent.id, title='missing')
        v = patient_renal_pathways(rev.id)
        self.assertEqual(v['status'], 'missing_inputs')
        self.assertIn('serum_creatinine', v['missing_fields'])

    def test_run_record_and_page(self):
        rev = self.revision_with(serum_creatinine=120)
        record = record_for_renal_pathways(patient_renal_pathways(rev.id))
        self.assertEqual(record['model']['model_id'], 'lenalidomide_renal_pathways_2026')
        self.assertEqual(record['assumptions'][0]['status'], 'partly_contradicted')
        url = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{rev.id}/renal-pathways'
        html = self.client.get(url).get_data(as_text=True)
        for text in ('Kidney view', 'Tubular secretion', 'Reference: normal kidney function', 'Not a clinical prediction',
                     'Run record', 'In this range the check found the real increase larger'):
            self.assertIn(text, html)
        self.assertEqual(self.client.get(url + '?format=json').get_json()['status'], 'completed')
        detail = self.client.get(f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{rev.id}').get_data(as_text=True)
        self.assertIn('Lenalidomide elimination pathways', detail)


if __name__ == '__main__':
    unittest.main()
