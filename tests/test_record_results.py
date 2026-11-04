"""Layout step 3: a saved record's results grouped by question, each with its status before opening."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kim_pk_runs as fixtures  # noqa: E402

from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.record_results import QUESTIONS, STATUS_TEXT, record_results


class RecordResults(unittest.TestCase):
    setUp = fixtures.KimPKRunTests.setUp
    tearDown = fixtures.KimPKRunTests.tearDown

    def revision_with(self, **kw):
        parent = getattr(self, '_latest', self.revision)
        self._latest = save_revision(self.scenario.id, fixtures.full_state(**kw), parent_revision_id=parent.id, title=str(kw))
        return self._latest

    def statuses(self, revision):
        return {item['title']: item['status'] for group in record_results(revision.id) for item in group['items']}

    def test_questions_and_statuses_are_from_the_fixed_vocabulary(self):
        groups = record_results(self.revision_with(serum_creatinine=80).id)
        self.assertEqual([g['id'] for g in groups], [key for key, _ in QUESTIONS])
        for group in groups:
            for item in group['items']:
                self.assertIn(item['status'], STATUS_TEXT)
                self.assertEqual(item['status_text'], STATUS_TEXT[item['status']])
                self.assertTrue(item['status_label'])

    def test_mild_kidney_function(self):
        s = self.statuses(self.revision_with(serum_creatinine=80))
        self.assertEqual(s['Elimination pathways'], 'checked')
        self.assertEqual(s['Body map (3D)'], 'checked')
        self.assertIn(s['Typical concentration curve (Hughes 2019)'], ('checked', 'within_data'))

    def test_moderate_kidney_function_is_flagged(self):
        s = self.statuses(self.revision_with(serum_creatinine=120))
        self.assertEqual(s['Elimination pathways'], 'partly_checked')   # 2.0e: depends on bioavailability
        self.assertEqual(s['Typical concentration curve (Hughes 2019)'], 'flagged')

    def test_below_the_models_data_is_not_available(self):
        s = self.statuses(self.revision_with(serum_creatinine=600))
        self.assertEqual(s['Elimination pathways'], 'not_available')
        self.assertEqual(s['Typical concentration curve (Hughes 2019)'], 'not_available')
        self.assertEqual(s['Typical concentration curve in renal impairment (Kim 2026)'], 'not_available')

    def test_missing_platelet_count_asks_for_input(self):
        s = self.statuses(self.revision_with(serum_creatinine=80))
        self.assertEqual(s['Platelet time course (Lignet 2022)'], 'needs_input')

    def test_record_page_shows_results_by_question(self):
        rev = self.revision_with(serum_creatinine=120)
        url = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{rev.id}'
        html = self.client.get(url).get_data(as_text=True)
        for text in ('Results for this record', 'How much drug is in the blood?', 'Where does the drug leave the body?',
                     'What happens to blood counts?', 'record-result-flagged', 'ms-status ms-status-flagged', STATUS_TEXT['flagged'],
                     f'{url}/body-map', f'{url}/renal-pathways', f'{url}/bortezomib-platelets', 'Saved educational runs'):
            self.assertIn(text, html)


if __name__ == '__main__':
    unittest.main()
