"""Phase 4.1c: reference-annotation storage, validation and page."""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from flask import Flask

from intelligence_store import eligibility_annotations as ea
from intelligence_store import eligibility_annotations_v2 as ea2
from landscape_ui import register_landscape

TEXT = ("Inclusion Criteria:\n* ECOG performance status 0-2\n* Creatinine clearance >= 30 mL/min (Cockcroft-Gault)\n"
        "Exclusion Criteria:\n* Total bilirubin > 1.5 x ULN")
TRIALS = [{'nct_id': 'NCT90000001', 'criteria_text': TEXT}, {'nct_id': 'NCT90000002', 'criteria_text': TEXT}]


def form2(**overrides):
    f = {f'{k}__status': 'not_stated' for k in ea2.TYPES}
    f.update({'ecog_max__status': 'stated', 'ecog_max__v1__comparator_as_written': '<=', 'ecog_max__v1__value': '2',
              'ecog_max__v1__unit': 'score', 'ecog_max__v1__section': 'inclusion',
              'ecog_max__v1__sentence': 'ECOG  performance status 0-2'})
    f.update(overrides)
    return f


def form(**overrides):
    f = {f'{k}__status': 'not_stated' for k in ea.TYPES}
    f.update({'ecog_max__status': 'stated', 'ecog_max__v1__comparator': '<=', 'ecog_max__v1__value': '2',
              'ecog_max__v1__unit': 'score', 'ecog_max__v1__section': 'inclusion',
              'ecog_max__v1__sentence': 'ECOG  performance status 0-2'})
    f.update(overrides)
    return f


class Parse(unittest.TestCase):
    def test_valid_annotation(self):
        a = ea.parse_form(form(), TEXT)
        self.assertEqual(a['ecog_max']['values'][0]['value'], '2')
        self.assertEqual(a['bilirubin_max'], {'status': 'not_stated', 'note': '', 'values': []})

    def test_problems_are_all_reported(self):
        bad = form(**{'ecog_max__v1__sentence': 'not in the text', 'kidney_function_min__status': 'stated',
                      'hemoglobin_min__status': 'unclear', 'anc_min__status': ''})
        with self.assertRaises(ValueError) as ctx:
            ea.parse_form(bad, TEXT)
        problems = ' | '.join(ctx.exception.args[0])
        for text in ('sentence was not found', "'stated' needs exactly one value", 'why it is unclear', 'choose a status'):
            self.assertIn(text, problems)

    def test_kidney_needs_an_equation_and_units_are_checked(self):
        f = form(**{'kidney_function_min__status': 'stated', 'kidney_function_min__v1__comparator': '>=',
                    'kidney_function_min__v1__value': '30', 'kidney_function_min__v1__unit': 'mg/dL',
                    'kidney_function_min__v1__section': 'inclusion',
                    'kidney_function_min__v1__sentence': 'Creatinine clearance >= 30 mL/min (Cockcroft-Gault)'})
        with self.assertRaises(ValueError) as ctx:
            ea.parse_form(f, TEXT)
        self.assertTrue(any('choose a unit' in e for e in ctx.exception.args[0]))
        self.assertTrue(any('estimating method' in e for e in ctx.exception.args[0]))
        f.update({'kidney_function_min__v1__unit': 'mL/min', 'kidney_function_min__equation': 'cockcroft_gault'})
        self.assertEqual(ea.parse_form(f, TEXT)['kidney_function_min']['equation'], 'cockcroft_gault')


class Store(unittest.TestCase):
    def test_save_correct_and_export(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(ea, 'load_sample', return_value={'annotation_order': ['NCT90000001', 'NCT90000002']}):
            path = Path(tmp) / 'a.json'
            ea.save_annotation(path, 'NCT90000001', ea.parse_form(form(), TEXT))
            with self.assertRaises(ValueError):
                ea.export(path)
            with self.assertRaises(ValueError):
                ea.save_annotation(path, 'NCT90000001', ea.parse_form(form(), TEXT))       # correction without a reason
            ea.save_annotation(path, 'NCT90000001', ea.parse_form(form(), TEXT), 'typo in ECOG')
            ea.save_annotation(path, 'NCT90000002', ea.parse_form(form(), TEXT))
            payload = ea.export(path)
            self.assertEqual(payload['annotated'], 2)
            self.assertEqual(len(payload['corrections']), 1)
            self.assertEqual(payload['plan_sha256'], ea.PLAN_SHA256)

    def test_a_file_for_another_plan_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.json'
            path.write_text(json.dumps(dict(ea.empty_store(), plan_sha256='0' * 64)))
            with self.assertRaises(ValueError):
                ea.load_store(path)

    def test_real_sample_has_120_trials_with_text(self):
        trials = ea.sample_trials()
        self.assertEqual(len(trials), 120)
        self.assertTrue(all(t['criteria_text'] for t in trials))


class Page(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, ELIGIBILITY_ANNOTATIONS_V2_PATH=os.path.join(self.tmp.name, 'a.json'))
        self.app.add_url_rule('/', 'home', lambda: 'Home')
        register_landscape(self.app)
        self.client = self.app.test_client()
        self.patch = mock.patch.object(ea2, 'sample_trials', return_value=TRIALS)
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()

    def test_annotate_flow(self):
        self.assertIn('0 of 2', self.client.get('/landscape/benchmarking/annotate').get_data(as_text=True))
        page = self.client.get('/landscape/benchmarking/annotate/NCT90000001').get_data(as_text=True)
        self.assertIn('ECOG performance status 0-2', page)
        token = re.search(r'name="form_token" value="([^"]+)"', page).group(1)
        self.assertEqual(self.client.post('/landscape/benchmarking/annotate/NCT90000001', data=form2()).status_code, 403)
        bad = self.client.post('/landscape/benchmarking/annotate/NCT90000001', data=dict(form2(**{'ecog_max__v1__sentence': 'nope'}), form_token=token))
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post('/landscape/benchmarking/annotate/NCT90000001', data=dict(form2(), form_token=token))
        self.assertEqual(ok.status_code, 303)
        self.assertTrue(ok.headers['Location'].endswith('/landscape/benchmarking/annotate/NCT90000002'))
        self.assertIn('1 of 2', self.client.get('/landscape/benchmarking/annotate').get_data(as_text=True))
        self.assertEqual(self.client.get('/landscape/benchmarking/annotate/NCT12345678').status_code, 404)


class Review(unittest.TestCase):
    """Self-review before export: the annotator's own work only."""
    def annotation(self, **overrides):
        return ea.parse_form(form(**overrides), TEXT)

    def test_locate_tolerates_the_page_normalisation(self):
        from intelligence_store import eligibility_annotation_review as review
        start, end = review.locate(TEXT, 'ecog  PERFORMANCE status 0-2')
        self.assertEqual(TEXT[start:end], 'ECOG performance status 0-2')
        self.assertIsNone(review.locate(TEXT, 'not there'))
        self.assertEqual(review.section_at(TEXT, TEXT.index('Total bilirubin')), 'exclusion')

    def test_highlight_and_mentions(self):
        from intelligence_store import eligibility_annotation_review as review
        pieces = review.pieces_with_mentions(TEXT, self.annotation())
        self.assertEqual(''.join(p['text'] for p in pieces), TEXT)
        self.assertIn({'text': 'ECOG performance status 0-2', 'types': ['ecog_max'], 'mention': False}, pieces)
        self.assertTrue(any(p['mention'] and p['text'].lower() == 'bilirubin' for p in pieces))

    def test_prompts(self):
        from intelligence_store import eligibility_annotation_review as review
        a = self.annotation(**{'bilirubin_max__status': 'stated', 'bilirubin_max__v1__comparator': '>', 'bilirubin_max__v1__value': '1.5',
                               'bilirubin_max__v1__unit': 'x ULN', 'bilirubin_max__v1__section': 'inclusion',
                               'bilirubin_max__v1__sentence': 'Total bilirubin > 1.5 x ULN'})
        p = review.prompts(TEXT, a)
        text = ' | '.join(p['bilirubin_max'])
        self.assertIn('a lower limit', text)
        self.assertIn('under the exclusion heading', text)
        self.assertTrue(any('names this measure' in q for q in p['kidney_function_min']))
        self.assertNotIn('ecog_max', p)
        a = self.annotation(**{'bilirubin_max__status': 'stated', 'bilirubin_max__v1__comparator': '<=', 'bilirubin_max__v1__value': '1.5',
                               'bilirubin_max__v1__unit': 'x ULN', 'bilirubin_max__v1__section': 'exclusion',
                               'bilirubin_max__v1__sentence': 'Total bilirubin > 1.5 x ULN'})
        self.assertNotIn('bilirubin_max', review.prompts(TEXT, a))
        a = self.annotation(**{'ecog_max__v1__value': '3'})
        self.assertTrue(any('does not appear' in q for q in review.prompts(TEXT, a)['ecog_max']))

    def test_strictness_prompt(self):
        from intelligence_store import eligibility_annotation_review as review
        f = review._strictness_mismatch
        self.assertIn('Should it be ≥', f({'comparator': '>', 'value': '30', 'section': 'inclusion', 'sentence': 'CrCl \\>= 30 mL/min'}))
        self.assertIsNone(f({'comparator': '>=', 'value': '30', 'section': 'inclusion', 'sentence': 'CrCl ≥ 30 mL/min'}))
        self.assertIsNone(f({'comparator': '>=', 'value': '30', 'section': 'exclusion', 'sentence': 'CrCl < 30 mL/min'}))
        self.assertIn('Should it be ≥', f({'comparator': '>', 'value': '30', 'section': 'exclusion', 'sentence': 'CrCl < 30 mL/min'}))
        self.assertIsNone(f({'comparator': '>', 'value': '30', 'section': 'exclusion', 'sentence': 'CrCl <= 30 mL/min'}))
        self.assertIsNone(f({'comparator': '<=', 'value': '2', 'section': 'inclusion', 'sentence': 'ECOG 0-2'}))
        self.assertIsNone(f({'comparator': '>=', 'value': '30', 'section': 'inclusion', 'sentence': 'CrCl at least 30 mL/min'}))

    def test_review_mark_follows_the_saved_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.json'
            with self.assertRaises(ValueError):
                ea.mark_reviewed(path, 'NCT90000001')
            ea.save_annotation(path, 'NCT90000001', self.annotation())
            store = ea.mark_reviewed(path, 'NCT90000001')
            self.assertTrue(ea.review_is_current(store, 'NCT90000001'))
            with mock.patch.object(ea, '_now', return_value='2099-01-01T00:00:00+00:00'):
                store = ea.save_annotation(path, 'NCT90000001', self.annotation(), reason='slip')
            self.assertFalse(ea.review_is_current(store, 'NCT90000001'))


class ReviewPage(Page):
    def test_review_flow(self):
        page = self.client.get('/landscape/benchmarking/annotate/NCT90000001').get_data(as_text=True)
        token = re.search(r'name="form_token" value="([^"]+)"', page).group(1)
        self.client.post('/landscape/benchmarking/annotate/NCT90000001', data=dict(form2(), form_token=token))
        self.assertEqual(self.client.get('/landscape/benchmarking/review/NCT90000002').status_code, 404)
        overview = self.client.get('/landscape/benchmarking/review').get_data(as_text=True)
        self.assertIn('0 of 1', overview)
        self.assertIn('≤ 2 score', overview)
        page = self.client.get('/landscape/benchmarking/review/NCT90000001').get_data(as_text=True)
        self.assertIn('<mark title="ECOG performance status threshold (incl. WHO, Zubrod, SWOG)">ECOG performance status 0-2</mark>', page)
        self.assertIn('names this measure', page)
        self.assertNotIn('extractor', page.lower().replace('never from the extractor', ''))
        token = re.search(r'name="form_token" value="([^"]+)"', page).group(1)
        self.assertEqual(self.client.post('/landscape/benchmarking/review/NCT90000001').status_code, 403)
        done = self.client.post('/landscape/benchmarking/review/NCT90000001', data={'form_token': token})
        self.assertEqual(done.status_code, 303)
        self.assertIn('1 of 1', self.client.get('/landscape/benchmarking/review').get_data(as_text=True))

    def test_annotate_flow(self):
        pass



class Version2(unittest.TestCase):
    """Phase 4.2a: comparators recorded as written; the eligible side is derived."""
    def test_eligible_side_is_derived(self):
        a = ea2.parse_form(form2(**{'bilirubin_max__status': 'stated', 'bilirubin_max__v1__comparator_as_written': '>',
                                    'bilirubin_max__v1__value': '1.5', 'bilirubin_max__v1__unit': 'x ULN',
                                    'bilirubin_max__v1__section': 'exclusion', 'bilirubin_max__v1__sentence': 'Total bilirubin > 1.5 x ULN'}), TEXT)
        v = a['bilirubin_max']['values'][0]
        self.assertEqual((v['comparator_as_written'], v['describes'], v['comparator'], v['describes_from_section']), ('>', 'excluded', '<=', True))
        self.assertEqual(a['ecog_max']['values'][0]['comparator'], '<=')

    def test_describes_can_override_the_section(self):
        a = ea2.parse_form(form2(**{'ecog_max__v1__comparator_as_written': '>', 'ecog_max__v1__describes': 'excluded'}), TEXT)
        self.assertEqual(a['ecog_max']['values'][0]['comparator'], '<=')
        with self.assertRaises(ValueError) as ctx:
            ea2.parse_form(form2(**{'ecog_max__v1__comparator_as_written': ''}), TEXT)
        self.assertTrue(any('as written' in e for e in ctx.exception.args[0]))

    def test_k_per_ul_unit_and_any_direction(self):
        self.assertIn('x 10^3/uL (K/uL)', ea2.TYPES['platelets_min']['units'])
        text = TEXT + '\n* eGFR < 40 mL/min/1.73 m2'
        a = ea2.parse_form(form2(**{'kidney_function_min__status': 'stated', 'kidney_function_min__v1__comparator_as_written': '<',
                                    'kidney_function_min__v1__value': '40', 'kidney_function_min__v1__unit': 'mL/min/1.73 m2',
                                    'kidney_function_min__v1__section': 'inclusion', 'kidney_function_min__v1__sentence': 'eGFR < 40 mL/min/1.73 m2',
                                    'kidney_function_min__equation': 'not_stated'}), text)
        self.assertEqual(a['kidney_function_min']['values'][0]['comparator'], '<')

    def test_store_and_export_report_reviews(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(ea2, 'load_sample', return_value={'annotation_order': ['NCT90000001']}):
            path = Path(tmp) / 'a.json'
            ea2.save_annotation(path, 'NCT90000001', ea2.parse_form(form2(), TEXT))
            self.assertEqual(ea2.export(path)['reviewed'], 0)
            ea2.mark_reviewed(path, 'NCT90000001')
            self.assertEqual(ea2.export(path)['reviewed'], 1)
            v1_file = Path(tmp) / 'v1.json'
            ea.save_annotation(v1_file, 'NCT90000001', ea.parse_form(form(), TEXT))
            with self.assertRaises(ValueError):
                ea2.load_store(v1_file)

    def test_real_v2_sample_is_disjoint_from_v1(self):
        v1 = ea.load_sample()
        v2 = ea2.load_sample()
        self.assertEqual(len(v2['validation_sample']), 200)
        self.assertFalse(set(v2['validation_sample']) & (set(v1['validation_sample']) | set(v1['development_set'])))
        from intelligence_store import eligibility_sample
        self.assertEqual(eligibility_sample.draw_v2()['validation_sample'], v2['validation_sample'])


if __name__ == '__main__':
    unittest.main()
