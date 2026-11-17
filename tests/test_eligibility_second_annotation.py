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

    def test_sample_is_pinned_for_plan_v1(self):
        """Pins the draw before the sampler learned about restricted pools (17 November 2026)."""
        import hashlib
        study, practice = sa.sample()
        self.assertEqual(hashlib.sha256(json.dumps(study).encode()).hexdigest(),
                         'a9c720b27e66c5aa5e78f304385b38e6f5f9a34e3ef68363f70705ba8ec0e3d3')
        self.assertEqual(hashlib.sha256(json.dumps(practice).encode()).hexdigest(),
                         '6bf834f57f65aad766e71266d2a08719dd1369cc3ce86c7914a23bb36ae713dc')

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

    def test_regression_pinned_report_digests(self):
        """Pins agreement's output before the reader-A change of 16 November (plan v1 path must not move)."""
        rep = sa.agreement(self.rec(self.forms), self.p)
        self.assertEqual(rep['report_sha256'], 'a6c96f5e16bd816e82b2b9c0a7a186289891433edb6bb30ca5a01206b8d1a406')
        forms = json.loads(json.dumps(self.forms))
        for t in self.p['trials'][:30]:
            f = forms[t['nct_id']]
            for k in [k for k in f if k.startswith('ecog_max__')]:
                del f[k]
            f['ecog_max__status'] = 'not_stated'
        rep2 = sa.agreement(self.rec(forms), self.p)
        self.assertEqual(rep2['report_sha256'], '9738b1cbfa2f22316a44180ab517371abe560e9aded573a7d2fa7ba966688bb9')
        self.assertEqual(rep2['overall']['exact_rate'], 0.9675)

    def test_reader_a_record_matches_the_pinned_annotation_path(self):
        """Passing the owner's own annotation as reader A reproduces the default path."""
        rep = sa.agreement(self.rec(self.forms), self.p)
        owner = self.rec(self.forms)
        rep_b = sa.agreement(self.rec(self.forms), self.p, record_a=owner)
        self.assertEqual(rep_b['overall']['exact_rate'], 1.0)
        self.assertEqual(rep_b['readers']['a'], 'record')
        self.assertNotIn('readers', rep)  # the default path's report is unchanged, digest included

    def test_pair_subset_restricts_the_second_overall_block(self):
        forms = json.loads(json.dumps(self.forms))
        for t in self.p['trials'][:30]:
            f = forms[t['nct_id']]
            for k in [k for k in f if k.startswith('ecog_max__')]:
                del f[k]
            f['ecog_max__status'] = 'not_stated'
        subset = [f"{t['nct_id']}:ecog_max" for t in self.p['trials'][:30]]
        rep = sa.agreement(self.rec(forms), self.p, pair_subset=subset)
        self.assertEqual(rep['overall_subset']['pairs'], len(subset))
        self.assertLess(rep['overall_subset']['exact_rate'], rep['overall']['exact_rate'])
        self.assertIsNone(sa.agreement(self.rec(forms), self.p).get('overall_subset'))

    def test_comparison_v1_is_the_default_and_leaves_no_trace(self):
        rep = sa.agreement(self.rec(self.forms), self.p)
        self.assertNotIn('comparison', rep)
        self.assertEqual(rep['report_sha256'],
                         sa.agreement(self.rec(self.forms), self.p, comparison='v1')['report_sha256'])

    def test_comparison_v2_is_recorded_in_the_report(self):
        rep = sa.agreement(self.rec(self.forms), self.p, comparison='v2')
        self.assertEqual(rep['comparison'], 'v2')

    def test_an_unknown_comparison_is_refused(self):
        with self.assertRaises(ValueError):
            sa.agreement(self.rec(self.forms), self.p, comparison='v3')


class RoundTwoPlan(unittest.TestCase):
    """Round two draws from a restricted pool and gives each reader its own order (plan v2, 17 November 2026)."""

    @classmethod
    def setUpClass(cls):
        import json as _json
        cls.plan = _json.loads((sa.DATA / 'eligibility_second_annotation_plan_v2.json').read_bytes())

    def test_pins_guide_v3(self):
        import hashlib
        g = self.plan['inputs']['guide']
        self.assertTrue(g['file'].endswith('ELIGIBILITY_ANNOTATION_GUIDE_V3.md'))
        self.assertEqual(hashlib.sha256((sa.ROOT / g['file']).read_bytes()).hexdigest(), g['sha256'])

    def test_pins_comparison_v2(self):
        self.assertEqual(self.plan['inputs']['comparison'], 'v2')

    def test_both_readers_get_the_same_50_trials_in_different_orders(self):
        a, _ = sa.sample(self.plan, 'owner')
        b, _ = sa.sample(self.plan, 'annotator_b')
        self.assertEqual(len(a), 50)
        self.assertEqual(set(a), set(b))
        self.assertNotEqual(a, b)

    def test_the_pool_excludes_round_one_and_the_re_reading(self):
        from intelligence_store import eligibility_reference_review as rr
        a, practice = sa.sample(self.plan, 'owner')
        r1_study, r1_practice = sa.sample()
        self.assertEqual(set(a) & (set(r1_study) | set(r1_practice)), set())
        self.assertEqual(set(a) & {it['nct_id'] for it in rr.view()['items']}, set())
        self.assertEqual(len(set(a)), 50)
        self.assertEqual(set(a) & set(practice), set())

    def test_the_pool_size_is_asserted_so_it_cannot_drift(self):
        plan = json.loads(json.dumps(self.plan))
        plan['sample']['pool']['expected_size'] = 999
        with self.assertRaises(ValueError):
            sa.sample(plan, 'owner')

    def test_a_reader_is_required_and_checked(self):
        with self.assertRaises(ValueError):
            sa.sample(self.plan)
        with self.assertRaises(ValueError):
            sa.sample(self.plan, 'somebody_else')

    def test_plan_v1_still_takes_no_reader(self):
        study, _ = sa.sample()
        self.assertEqual(len(study), 50)

    def test_the_reading_rule_names_what_a_second_failure_means(self):
        does_not = self.plan['reading']['does_not_clear'].lower()
        self.assertIn('not viable', does_not)
        self.assertIn('no third round', does_not)
        self.assertEqual(self.plan['analysis']['bar'], 0.90)

    def test_adjudication_gains_a_fourth_choice(self):
        self.assertIn('both', self.plan['adjudication'].lower())

    def test_the_owner_is_recorded_as_not_naive(self):
        self.assertIn('never a naive reader', ' '.join(self.plan['limitations']))
        self.assertFalse(self.plan['clinical_prediction_validated'])


if __name__ == '__main__':
    unittest.main()
