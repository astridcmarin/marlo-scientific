"""Reviewer's checklist M3: a model analysis report in ICH M15 Appendix 2 order, assembled from pinned sources."""
import json
import unittest

from intelligence_store import model_analysis_report as mar

MODEL = 'lenalidomide_renal_pathways_2026'


class Report(unittest.TestCase):
    def setUp(self):
        self.r = mar.build(MODEL)

    def test_sections_in_m15_order(self):
        keys = list(self.r)
        order = ['executive_summary', 'introduction', 'objectives', 'data_and_methods', 'results', 'discussion', 'conclusions', 'appendices']
        self.assertEqual([k for k in keys if k in order], order)
        self.assertIn('Appendix 2', self.r['structure'])

    def test_results_cover_every_finding_for_the_model_and_read_the_reports(self):
        from intelligence_store.check_findings import findings_view
        ids = [f['id'] for a in findings_view()['areas'] for f in a['rows'] if MODEL in f['subjects']]
        self.assertEqual([res['finding']['id'] for res in self.r['results']], ids)
        a = self.r['results'][0]
        self.assertEqual(a['rows'][1][0], 'Moderate')
        self.assertIn('model under-predicts', a['rows'][1][3])
        e = next(res for res in self.r['results'] if res['finding']['id'] == 'pathways_2_0e')
        self.assertIn('not established', e['note'])
        self.assertIn('9.6–28.7', e['note'])
        self.assertTrue(all(not res['finding']['blind'] for res in self.r['results']))

    def test_appendix_plans_match_the_credibility_record(self):
        from intelligence_store.credibility_records import record
        self.assertEqual(self.r['appendices']['model_analysis_plans'], record(MODEL)['model_analysis_plans'])
        self.assertEqual(len(self.r['appendices']['model_analysis_plans']), 4)

    def test_narrative_is_pinned_and_current(self):
        text = ' '.join([self.r['executive_summary'], self.r['introduction']] + self.r['discussion'] + self.r['conclusions'])
        self.assertIn('depend on bioavailability', text)
        self.assertIn('not established', text)
        self.assertNotIn('falls faster than proportional', text)
        original = mar.TEXTS[MODEL]
        try:
            mar.TEXTS[MODEL] = (original[0], '0' * 64)
            with self.assertRaises(mar.ReportError):
                mar.build(MODEL)
        finally:
            mar.TEXTS[MODEL] = original

    def test_reproducible_and_flag_false(self):
        self.assertEqual(self.r['report_sha256'], mar.build(MODEL)['report_sha256'])
        self.assertFalse(self.r['clinical_prediction_validated'])
        with self.assertRaises(KeyError):
            mar.build('lenalidomide_hughes_2019')


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_page_json_and_links(self):
        html = self.client.get(f'/models/{MODEL}/report').get_data(as_text=True)
        for text in ('1. Executive summary', '5. Results', '8. Appendices', 'Across the bioavailability the data allow (2.0e)',
                     'an AI review, not independent'):
            self.assertIn(text, html)
        body = json.loads(self.client.get(f'/models/{MODEL}/report?format=json').get_data(as_text=True))
        self.assertEqual(body['model_id'], MODEL)
        self.assertEqual(self.client.get('/models/lenalidomide_hughes_2019/report').status_code, 404)
        self.assertEqual(self.client.get(f'/models/{MODEL}/report?format=xml').status_code, 400)
        self.assertIn(f'/models/{MODEL}/report', self.client.get(f'/models/{MODEL}/credibility').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
