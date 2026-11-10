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
            mar.build('bortezomib_pk_lignet_2022')


class PublishedModels(unittest.TestCase):
    def test_hughes_and_kim_reports(self):
        h, k = mar.build('lenalidomide_hughes_2019'), mar.build('lenalidomide_kim_2026')
        self.assertEqual([r['finding']['id'] for r in h['results']], ['hughes_cc5013', 'renal_recheck', 'bridoux_hughes_kim'])
        self.assertEqual([r['finding']['id'] for r in k['results']], ['kim_cc5013', 'renal_recheck', 'bridoux_hughes_kim'])
        self.assertEqual(k['results'][1]['rows'][1], ['Moderate', 'model under-predicts', 'model under-predicts', 'changed'])
        bridoux = h['results'][2]
        self.assertTrue(bridoux['finding']['blind'])
        self.assertIn('Recorded deviation', bridoux['note'])
        self.assertIn('Three locked checks', h['executive_summary'])

    def test_exposure_safety_report_without_checks(self):
        r = mar.build('lenalidomide_exposure_safety_2016')
        self.assertEqual(r['findings_summary'], [])
        self.assertEqual(r['appendices']['model_analysis_plans'], [])
        self.assertEqual(r['appendices']['reports'], [])
        self.assertEqual([x['title'] for x in r['results']], ['Published estimates as implemented (multiple myeloma)',
                                                             'What the implemented formula gives (illustration)'])
        self.assertEqual(r['results'][0]['rows'][0][1], '2.972 (1.027–8.598)')
        self.assertTrue(r['results'][1]['rows'][0][3].startswith('2.13 '))
        self.assertTrue(all(not x['finding']['blind'] for x in r['results']))
        self.assertIn('no locked check', r['executive_summary'])

    def test_every_lenalidomide_model_has_a_report(self):
        self.assertEqual(set(mar.available()), {'lenalidomide_renal_pathways_2026', 'lenalidomide_hughes_2019',
                                                'lenalidomide_kim_2026', 'lenalidomide_exposure_safety_2016'})

    def test_every_narrative_is_pinned(self):
        import hashlib
        for model_id, (name, sha) in mar.TEXTS.items():
            self.assertEqual(hashlib.sha256((mar.DATA / name).read_bytes()).hexdigest(), sha, model_id)


class SupersededTexts(unittest.TestCase):
    def test_superseded_texts_kept_unchanged(self):
        import hashlib
        from intelligence_store import model_analysis_report as mar
        for name, sha in mar.SUPERSEDED_TEXTS.items():
            self.assertEqual(hashlib.sha256((mar.DATA / name).read_bytes()).hexdigest(), sha, name)


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
        self.assertEqual(self.client.get('/models/bortezomib_pk_lignet_2022/report').status_code, 404)
        self.assertEqual(self.client.get(f'/models/{MODEL}/report?format=xml').status_code, 400)
        self.assertIn(f'/models/{MODEL}/report', self.client.get(f'/models/{MODEL}/credibility').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
