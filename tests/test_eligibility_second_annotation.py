"""Second annotator for eligibility v2: plan pin, blind sample, standalone page, record rules and a synthetic dry run (13 November 2026)."""
import json
import tempfile
import unittest
from pathlib import Path

from intelligence_store import eligibility_second_annotation as sa
from intelligence_store import eligibility_validation_v2 as v2

ROOT = Path(__file__).resolve().parents[1]


def form_from(entry, key):
    """The annotation tool's form fields that reproduce one annotation entry (synthetic records only)."""
    f = {f'{key}__status': entry['status'], f'{key}__note': entry.get('note') or ('synthetic' if entry['status'] == 'unclear' else '')}
    for n, x in enumerate(entry['values'], 1):
        for k in ('comparator_as_written', 'value', 'unit', 'section', 'sentence', 'qualifier'):
            f[f'{key}__v{n}__{k}'] = x.get(k) or ''
        if not x.get('describes_from_section', True):
            f[f'{key}__v{n}__describes'] = x['describes']
    if 'equation' in entry:
        f[f'{key}__equation'] = entry['equation']
    return f


class Plan(unittest.TestCase):
    def test_pinned(self):
        plan = sa.load_plan()
        self.assertEqual(plan['sample']['size'], 50)
        self.assertEqual(plan['analysis']['reliability_bar'], 0.90)
        self.assertFalse(plan['clinical_prediction_validated'])
        import hashlib
        for name, ref in plan['inputs'].items():
            self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], name)


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sa.page_payload()

    def test_sample(self):
        study, practice = sa.sample()
        order = v2.load_sample()['annotation_order']
        self.assertEqual(len(set(study)), 50)
        self.assertTrue(set(study) <= set(order))
        self.assertEqual(len(practice), 5)
        self.assertFalse(set(practice) & set(order))
        self.assertEqual(sa.page_payload()['page_sha256'], self.p['page_sha256'])

    def test_page_holds_no_label_or_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'page.html'
            self.assertEqual(sa.write_page(path), self.p['page_sha256'])
            page = path.read_text(encoding='utf-8')
        for word in ('"annotated"', '"values"', '"outcome"', '"group"', 'v1_1', 'llm_run', '"criteria": {'):
            self.assertNotIn(word, page)
        self.assertIn('Lock and download', page)
        self.assertIn('<table>', page)  # the guide's status table rendered
        self.assertEqual(set(self.p), {'plan_version', 'plan_sha256', 'guide_sha256', 'types', 'statuses', 'comparators', 'sections',
                                       'describes', 'max_values', 'practice', 'trials', 'page_sha256'})


class Record(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sa.page_payload()
        a = v2.load_annotations()['annotations']
        cls.forms = {}
        for t in cls.p['trials']:
            f = {}
            for key in v2.TYPES:
                f.update(form_from(a[t['nct_id']]['criteria'][key], key))
            cls.forms[t['nct_id']] = f

    def rec(self, forms):
        return {'schema_version': sa.RECORD_SCHEMA, 'page_sha256': self.p['page_sha256'], 'locked_at': '2026-11-20T10:00:00Z',
                'annotator': {'code': 'B', 'background': 'synthetic'}, 'annotations': forms}

    def test_rules(self):
        self.assertEqual(sa.validate_record(self.rec(self.forms), self.p)[0], [])
        forms = json.loads(json.dumps(self.forms))
        first = self.p['trials'][0]['nct_id']
        del forms[self.p['trials'][1]['nct_id']]
        forms[first]['ecog_max__status'] = ''
        bad = self.rec(forms)
        bad['locked_at'] = None
        problems = sa.validate_record(bad, self.p)[0]
        self.assertTrue(any('not locked' in x for x in problems))
        self.assertTrue(any('missing' in x for x in problems))
        self.assertTrue(any('choose a status' in x for x in problems))

    def test_dry_run_identical_reader_agrees_fully(self):
        rep = sa.agreement(self.rec(self.forms), self.p)
        self.assertEqual(rep['overall']['exact_rate'], 1.0)
        self.assertEqual(rep['reliability_reading']['reading'], 'adequate')
        self.assertEqual(rep['disagreements_for_adjudication'], [])
        self.assertEqual(rep['extractors_on_sample_descriptive']['owner_annotation'], rep['extractors_on_sample_descriptive']['annotator_b'])
        self.assertFalse(rep['clinical_prediction_validated'])

    def test_dry_run_with_synthetic_disagreements(self):
        forms = json.loads(json.dumps(self.forms))
        for t in self.p['trials'][:30]:  # a synthetic reader who calls ECOG not stated in 30 trials
            f = forms[t['nct_id']]
            for k in [k for k in f if k.startswith('ecog_max__')]:
                del f[k]
            f['ecog_max__status'] = 'not_stated'
        rep = sa.agreement(self.rec(forms), self.p)
        changed = sum(1 for t in self.p['trials'][:30] if self.forms[t['nct_id']]['ecog_max__status'] != 'not_stated')
        self.assertEqual(rep['per_type']['ecog_max']['exact_agreement'], 50 - changed)
        self.assertEqual(len(rep['disagreements_for_adjudication']), changed)
        self.assertEqual(rep['overall']['pairs'], 400)
        lo, hi = rep['overall']['exact_trial_bootstrap_95']
        self.assertLessEqual(lo, rep['overall']['exact_rate'])
        self.assertGreaterEqual(hi, rep['overall']['exact_rate'])


if __name__ == '__main__':
    unittest.main()
