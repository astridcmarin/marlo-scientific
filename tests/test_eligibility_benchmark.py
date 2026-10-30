"""Phase 4.1f: protocol benchmarking (gating on the locked v2 check, grouping, draft comparison, pages)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flask import Flask

from intelligence_store import eligibility_benchmark as eb
from intelligence_store import eligibility_validation_v2 as v2
from landscape_ui import register_landscape

TEXTS = {
    'NCT90000001': 'Inclusion Criteria:\n* Creatinine clearance >= 30 mL/min\n* Platelets >= 75,000/mm3\n* ECOG 0-2',
    'NCT90000002': 'Inclusion Criteria:\n* Creatinine clearance >= 45 mL/min\n* Platelets >= 50 x 10^9/L\n* ECOG 0-1',
    'NCT90000003': 'Inclusion Criteria:\n* eGFR must be <40 ml/min/1.73m2\nExclusion Criteria:\n* Platelets < 75,000/mm3',
    'NCT90000004': 'Inclusion Criteria:\n* Adequate organ function',
}


def fake_corpus():
    from intelligence_store import eligibility_extractor_v1_1 as ex
    rows = [{'nct_id': n, 'title': f'Trial {n[-1]}', 'status': 'COMPLETED' if n[-1] in '12' else 'RECRUITING',
             'phase_group': 'phase_2', 'start_year': 2010 + int(n[-1]), 'extracted': ex.extract(t)} for n, t in TEXTS.items()]
    return {'corpus_content_sha256': 'x' * 64, 'extractor_version': ex.VERSION, 'extractor_sha256': eb.extractor_sha256(), 'trials': rows}


class Logic(unittest.TestCase):
    def setUp(self):
        self.rows = fake_corpus()['trials']

    def test_grouping_keeps_measures_apart(self):
        d = eb.distribution(self.rows, 'kidney_function_min')
        keys = {g['key']: g for g in d['groups']}
        self.assertIn('mL/min|usual', keys)
        self.assertIn('mL/min/1.73 m2|other', keys)
        self.assertEqual(d['stated'], 3)
        p = eb.distribution(self.rows, 'platelets_min')
        bins = {b['label']: b['n'] for g in p['groups'] for b in g['bins']}
        self.assertEqual(bins, {'≥ 50,000 /µL': 1, '≥ 75,000 /µL': 2})

    def test_unit_equivalences(self):
        self.assertEqual(eb.group('anc_min', {'comparator': '>=', 'value': '1.0', 'unit': 'x 10^3/uL (K/uL)'})[3], 1000.0)
        self.assertEqual(eb.group('hemoglobin_min', {'comparator': '>=', 'value': '80', 'unit': 'g/L'})[3], 8.0)
        self.assertEqual(eb.group('creatinine_max', {'comparator': '<=', 'value': '176.8', 'unit': 'umol/L'})[3], 2.0)
        self.assertNotEqual(eb.group('creatinine_max', {'comparator': '<=', 'value': '2', 'unit': 'x ULN'})[0],
                            eb.group('creatinine_max', {'comparator': '<=', 'value': '2', 'unit': 'mg/dL'})[0])
        self.assertEqual(eb.group('ecog_max', {'comparator': '<', 'value': '2', 'unit': 'score'})[2:], ('<=', 1.0))

    def test_draft_comparison(self):
        r = eb.compare_draft(self.rows, 'kidney_function_min', '>=', 40, 'mL/min')
        self.assertEqual((len(r['stricter']), len(r['equal']), len(r['more_permissive'])), (1, 0, 1))
        r = eb.compare_draft(self.rows, 'platelets_min', '>=', 75, 'x 10^9/L')
        self.assertEqual((len(r['stricter']), len(r['equal']), len(r['more_permissive'])), (0, 2, 1))
        r = eb.compare_draft(self.rows, 'ecog_max', '<=', 1, 'score')
        self.assertEqual((len(r['stricter']), len(r['equal']), len(r['more_permissive'])), (0, 1, 1))

    def test_filters(self):
        self.assertEqual(len(eb.filter_trials(self.rows, status='RECRUITING')), 2)
        self.assertEqual(len(eb.filter_trials(self.rows, start_from=2013)), 2)

    def test_validation_status_requires_a_matching_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'r.json'
            self.assertFalse(eb.validation_status(path)['available'])
            path.write_text(json.dumps({'plan_sha256': v2.PLAN_SHA256, 'extractor_sha256': 'f' * 64, 'passing_types': ['ecog_max']}))
            self.assertEqual(eb.validation_status(path)['passing_types'], [])
            path.write_text(json.dumps({'plan_sha256': v2.PLAN_SHA256, 'extractor_sha256': v2.EXTRACTOR_SHA256,
                                        'passing_types': ['ecog_max'], 'per_type': {}}))
            self.assertEqual(eb.validation_status(path)['passing_types'], ['ecog_max'])


class Pages(unittest.TestCase):
    def client(self, preview=False, passing=()):
        app = Flask(__name__)
        app.config.update(TESTING=True, ELIGIBILITY_BENCHMARK_PREVIEW=preview)
        app.add_url_rule('/', 'home', lambda: 'Home')
        register_landscape(app)
        status = {'available': bool(passing), 'reason': 'not run', 'passing_types': list(passing),
                  'per_type': {t: {'precision': 0.95, 'precision_95ci': [0.9, 0.98], 'recall': 0.9, 'recall_95ci': [0.8, 0.95]} for t in passing}}
        self.patches = [mock.patch.object(eb, 'extracted_corpus', fake_corpus), mock.patch.object(eb, 'validation_status', lambda: status)]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        return app.test_client()

    def test_nothing_shown_before_the_check(self):
        c = self.client()
        page = c.get('/landscape/benchmarking').get_data(as_text=True)
        self.assertIn('No criterion type is shown yet', page)
        self.assertNotIn('Stated in', page)
        self.assertEqual(c.get('/landscape/benchmarking/criteria/ecog_max').status_code, 404)

    def test_only_passing_types_are_shown(self):
        c = self.client(passing=('ecog_max',))
        page = c.get('/landscape/benchmarking').get_data(as_text=True)
        self.assertIn('ECOG performance status', page)
        self.assertNotIn('Platelet count</a>', page)
        self.assertEqual(c.get('/landscape/benchmarking/criteria/platelets_min').status_code, 404)
        t = c.get('/landscape/benchmarking/criteria/ecog_max?draft_comparator=%3C%3D&draft_value=1&draft_unit=score').get_data(as_text=True)
        self.assertIn('Measured accuracy', t)
        self.assertIn('Stricter than the draft', t)
        self.assertIn('NCT90000001', t)

    def test_preview_is_labelled(self):
        c = self.client(preview=True)
        page = c.get('/landscape/benchmarking').get_data(as_text=True)
        self.assertIn('Unvalidated preview', page)
        self.assertIn('Platelet count', page)
        bad = c.get('/landscape/benchmarking/criteria/platelets_min?draft_comparator=%3E%3D&draft_value=abc&draft_unit=x+10%5E9%2FL')
        self.assertIn('non-negative number', bad.get_data(as_text=True))
        self.assertEqual(c.get('/landscape/benchmarking/criteria/nope').status_code, 404)


if __name__ == '__main__':
    unittest.main()
