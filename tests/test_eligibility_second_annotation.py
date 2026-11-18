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
        cls.plan = sa.load_plan(sa.PLANS['eligibility-second-annotation-plan-v2.1'][0])

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

    def test_the_plan_carries_the_keys_its_executable_reads(self):
        """v2.0 did not, so it would have run under plan v1's bootstrap seed and bar."""
        a = self.plan['analysis']
        for key in ('bootstrap_seed', 'bootstrap_resamples', 'reliability_bar', 'reading_rule', 'trial_order'):
            self.assertIn(key, a, key)
        self.assertEqual(a['reliability_bar'], 0.90)
        self.assertEqual(a['trial_order'], 'sorted')
        self.assertNotEqual(a['bootstrap_seed'], json.loads(
            (sa.DATA / 'eligibility_second_annotation_plan_v1.json').read_bytes())['analysis']['bootstrap_seed'])

    def test_it_supersedes_v2_0_and_says_why(self):
        sup = self.plan['supersedes']
        self.assertEqual(sup['plan_version'], 'eligibility-second-annotation-plan-v2.0')
        self.assertIn('could not govern its own analysis', sup['change'])
        self.assertIn('draw is identical', sup['change'])

    def _blank(self, payload):
        return {'schema_version': sa.RECORD_SCHEMA, 'page_sha256': payload['page_sha256'],
                'plan_version': self.plan['plan_version'], 'plan_sha256': payload.get('plan_sha256'),
                'locked_at': '2026-11-20T10:00:00Z', 'annotator': {'code': 'X', 'background': 'synthetic'},
                'annotations': {t['nct_id']: {f'{k}__status': 'not_stated' for k in v2.TYPES}
                                for t in payload['trials']}}

    def test_dry_run_two_readers_on_their_own_pages(self):
        pb, pa = sa.page_payload(self.plan, 'annotator_b'), sa.page_payload(self.plan, 'owner')
        self.assertNotEqual(pb['page_sha256'], pa['page_sha256'])
        rep = sa.agreement(self._blank(pb), pb, record_a=self._blank(pa), comparison='v2',
                           plan=self.plan, p_a=pa)
        self.assertEqual(rep['comparison'], 'v2')
        self.assertEqual(rep['reliability_reading']['bar'], 0.90)
        self.assertEqual(rep['overall']['pairs'], 400)
        # The report names the plan that governed it, not plan v1 (found 17 November 2026).
        self.assertEqual(rep['plan_version'], 'eligibility-second-annotation-plan-v2.1')
        self.assertEqual(rep['plan_sha256'], sa.PLANS['eligibility-second-annotation-plan-v2.1'][1])

    def test_the_interval_does_not_depend_on_whose_page_was_passed(self):
        pb, pa = sa.page_payload(self.plan, 'annotator_b'), sa.page_payload(self.plan, 'owner')
        rb, ra = self._blank(pb), self._blank(pa)
        first = next(iter(ra['annotations']))
        ra['annotations'][first]['ecog_max__status'] = 'unclear'
        ra['annotations'][first]['ecog_max__note'] = 'synthetic difference'
        one = sa.agreement(rb, pb, record_a=ra, comparison='v2', plan=self.plan, p_a=pa)
        two = sa.agreement(ra, pa, record_a=rb, comparison='v2', plan=self.plan, p_a=pb)
        self.assertLess(one['overall']['exact_rate'], 1.0)
        self.assertEqual(one['overall']['exact_rate'], two['overall']['exact_rate'])
        self.assertEqual(one['overall']['exact_trial_bootstrap_95'],
                         two['overall']['exact_trial_bootstrap_95'])

    def test_record_a_is_validated_against_its_own_page(self):
        pb, pa = sa.page_payload(self.plan, 'annotator_b'), sa.page_payload(self.plan, 'owner')
        with self.assertRaises(ValueError):
            sa.agreement(self._blank(pb), pb, record_a=self._blank(pa), comparison='v2', plan=self.plan)


class PinnedPlans(unittest.TestCase):
    """Every plan the module may run is pinned by its loader, and carries the analysis keys the executable reads."""

    def test_every_pinned_plan_loads_and_declares_its_own_version(self):
        for version, (path, sha) in sa.PLANS.items():
            plan = sa.load_plan(path)
            self.assertEqual(plan['plan_version'], version)
            self.assertEqual(sa.plan_sha256(plan), sha)

    # Plan v2.0 is pinned only so v2.1 can name what it supersedes. It omitted the bootstrap seed and resample count
    # and named the bar `bar`, so it cannot govern its own analysis; that is why v2.1 exists.
    NOT_RUNNABLE = {'eligibility-second-annotation-plan-v2.0'}
    KEYS = ('bootstrap_seed', 'bootstrap_resamples', 'reliability_bar', 'reading_rule')

    def test_every_runnable_plan_carries_the_analysis_keys_the_executable_reads(self):
        for version, (path, _) in sa.PLANS.items():
            if version in self.NOT_RUNNABLE:
                continue
            a = sa.load_plan(path)['analysis']
            for key in self.KEYS:
                self.assertIn(key, a, f'{version}: {key}')

    def test_plan_v2_0_is_the_one_that_does_not(self):
        a = sa.load_plan(sa.PLANS['eligibility-second-annotation-plan-v2.0'][0])['analysis']
        self.assertNotIn('bootstrap_seed', a)
        later = sa.load_plan(sa.PLANS['eligibility-second-annotation-plan-v2.1'][0])
        self.assertEqual(later['supersedes']['plan_version'], 'eligibility-second-annotation-plan-v2.0')

    def test_an_unpinned_plan_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'plan.json'
            p.write_bytes((sa.DATA / 'eligibility_second_annotation_plan_v2_1.json').read_bytes())
            with self.assertRaises(ValueError):
                sa.load_plan(p)


class RoundTwoPages(unittest.TestCase):
    """Each reader's page carries its own identity and the checksum of the plan in force (17 November 2026: both
    pages had come out as annotator B's, declaring plan v2.1 and carrying plan v1's checksum)."""

    @classmethod
    def setUpClass(cls):
        cls.plan = sa.load_plan(sa.PLANS['eligibility-second-annotation-plan-v2.1'][0])
        cls.dir = tempfile.TemporaryDirectory()
        cls.html = {}
        for reader in ('owner', 'annotator_b'):
            path = Path(cls.dir.name) / f'{reader}.html'
            sa.write_page(path, cls.plan, reader)
            cls.html[reader] = path.read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_each_page_names_its_own_reader(self):
        own, b = self.html['owner'], self.html['annotator_b']
        self.assertIn('<title>Eligibility annotation (the owner)</title>', own)
        self.assertIn("annotator: {code: 'A'", own)
        self.assertIn("'eligibility_owner_final_'", own)
        self.assertNotIn("'eligibility_annotator_b_", own)
        self.assertIn('<title>Eligibility annotation (annotator B)</title>', b)
        self.assertIn("annotator: {code: 'B'", b)
        self.assertIn("'eligibility_annotator_b_final_'", b)
        self.assertNotIn("'eligibility_owner_", b)

    def test_each_page_carries_the_checksum_of_the_plan_in_force(self):
        want = sa.PLANS['eligibility-second-annotation-plan-v2.1'][1]
        self.assertNotEqual(want, sa.PLAN_SHA256)
        for reader in ('owner', 'annotator_b'):
            self.assertEqual(sa.page_payload(self.plan, reader)['plan_sha256'], want)
            self.assertNotIn(sa.PLAN_SHA256, self.html[reader])

    def test_each_page_names_the_guide_it_carries(self):
        for reader in ('owner', 'annotator_b'):
            self.assertIn('The annotation guide (version 3)', self.html[reader])

    def test_a_record_from_the_other_reader_is_refused(self):
        p = sa.page_payload(self.plan, 'owner')
        record = {'schema_version': sa.RECORD_SCHEMA, 'page_sha256': p['page_sha256'], 'locked_at': '2026-11-20T10:00:00Z',
                  'annotator': {'code': 'B', 'background': 'synthetic'},
                  'annotations': {t['nct_id']: {f'{k}__status': 'not_stated' for k in v2.TYPES} for t in p['trials']}}
        problems, _ = sa.validate_record(record, p, reader='owner')
        self.assertTrue(any('reader' in x for x in problems), problems)
        record['annotator']['code'] = 'A'
        problems, _ = sa.validate_record(record, p, reader='owner')
        self.assertFalse(any('reader' in x for x in problems), problems)

    def test_reader_and_plan_build_that_readers_payload(self):
        p = sa.page_payload(self.plan, 'annotator_b')
        record = {'schema_version': sa.RECORD_SCHEMA, 'page_sha256': p['page_sha256'], 'locked_at': '2026-11-20T10:00:00Z',
                  'annotator': {'code': 'B', 'background': 'synthetic'},
                  'annotations': {t['nct_id']: {f'{k}__status': 'not_stated' for k in v2.TYPES} for t in p['trials']}}
        self.assertEqual(sa.validate_record(record, reader='annotator_b', plan=self.plan)[0], [])

    def test_round_one_page_is_unchanged(self):
        pinned = json.loads((sa.DATA / 'eligibility_annotator_b_record_v1.json').read_bytes())['page_sha256']
        self.assertEqual(sa.page_payload()['page_sha256'], pinned)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'round_one.html'
            sa.write_page(path)
            page = path.read_text(encoding='utf-8')
        self.assertIn('<title>Eligibility annotation (annotator B)</title>', page)
        self.assertIn("annotator: {code: 'B'", page)
        self.assertIn('The annotation guide (version 2)', page)

    def test_an_unknown_reader_is_refused(self):
        with self.assertRaises(ValueError):
            sa.reader_identity('annotator_c')


if __name__ == '__main__':
    unittest.main()
