"""Blind re-reading of the eligibility v2 reference: plan pin, item list, record rules and a synthetic dry run (13 November 2026).

No real review decision exists when the plan is committed; the dry run uses invented decisions on the real list, so the
executable check is fixed before any decision is made (CLAUDE.md, F18).
"""
import json
import unittest
from pathlib import Path

from intelligence_store import eligibility_reference_review as rr
from intelligence_store import eligibility_validation_v2 as v2

ROOT = Path(__file__).resolve().parents[1]


class Plan(unittest.TestCase):
    def test_pinned_and_complete(self):
        plan = rr.load_plan()
        self.assertEqual(plan['recorded_on'], '2026-11-13')
        self.assertEqual(plan['controls'], {'size': 50, 'seed': 20261113})
        self.assertIn('Post hoc', plan['reporting']['label'])
        self.assertFalse(plan['clinical_prediction_validated'])
        import hashlib
        for name, ref in plan['inputs'].items():
            self.assertEqual(hashlib.sha256((ROOT / ref['file']).read_bytes()).hexdigest(), ref['sha256'], name)

    def test_changed_plan_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'plan.json'
            p.write_bytes(rr.PLAN_PATH.read_bytes() + b' ')
            with self.assertRaises(ValueError):
                rr.load_plan(p)


class Review(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = rr.view()
        cls.by_id = {i['id']: i for i in cls.v['items']}

    def test_items(self):
        report = json.loads((ROOT / 'docs/verification/eligibility_validation_llm_c1.json').read_text())
        self.assertEqual(self.v['counts']['shared'], sum(c['neither'] for c in report['paired_with_v1_1'].values()))
        self.assertEqual(self.v['counts']['controls'], 50)
        self.assertEqual(self.v['total'], 216)
        self.assertEqual(len(self.by_id), 216)
        self.assertEqual([i['position'] for i in self.v['items']], list(range(1, 217)))
        self.assertEqual(self.v['view_sha256'], rr.view()['view_sha256'])  # seeded: the same list every time

    def test_client_view_hides_group(self):
        cv = rr.client_view(self.v)
        self.assertTrue(all('group' not in i and 'reveal' not in i for i in cv['items']))
        self.assertNotIn('"group"', json.dumps(cv))
        self.assertEqual(set(cv['reveals']), set(self.by_id))

    def _reading(self, item):
        """A valid synthetic reading built from the original annotation of that item (the annotation tool's own form)."""
        a, t = item['reveal']['annotated'], item['type']
        r = {f'{t}__status': a['status'], f'{t}__note': a.get('note') or ('synthetic' if a['status'] == 'unclear' else '')}
        for n, x in enumerate(a['values'], 1):
            for f in ('comparator_as_written', 'value', 'unit', 'section', 'sentence', 'qualifier'):
                r[f'{t}__v{n}__{f}'] = x.get(f) or ''
            if not x.get('describes_from_section', True):
                r[f'{t}__v{n}__describes'] = x['describes']
        if 'equation' in a:
            r[f'{t}__equation'] = a['equation']
        return r

    def test_reading_uses_annotation_rules(self):
        item = self.v['items'][0]
        self.assertEqual(rr.check_reading(self.v, item['id'], self._reading(item)), [])
        bad = {f"{item['type']}__status": 'stated'}
        self.assertTrue(rr.check_reading(self.v, item['id'], bad))
        self.assertEqual(rr.check_reading(self.v, 'NCT0:x', {}), ['Not in the list.'])

    def test_record_rules(self):
        i1, i2 = self.v['items'][0], self.v['items'][1]
        good = {'view_sha256': self.v['view_sha256'], 'items': {
            i1['id']: {'reading': self._reading(i1), 'locked_at': '2026-11-14T10:00:00Z', 'decision': 'annotation_stands', 'decided_at': '2026-11-14T10:01:00Z'}}}
        self.assertEqual(rr.validate_record(good, self.v)[0], [])
        bad = {'view_sha256': 'x', 'items': {
            i1['id']: {'reading': self._reading(i1), 'locked_at': '2026-11-14T10:00:00Z', 'decision': 'annotation_stands', 'decided_at': '2026-11-14T09:59:00Z'},
            i2['id']: {'reading': self._reading(i2), 'locked_at': '2026-11-14T10:00:00Z', 'decision': 'annotation_needs_correcting', 'decided_at': '2026-11-14T10:02:00Z', 'note': ' '},
            'NCT0:x': {}}}
        problems = rr.validate_record(bad, self.v)[0]
        self.assertEqual(len(problems), 4, problems)
        self.assertTrue(any('decided before' in p for p in problems))
        self.assertTrue(any('needs a note' in p for p in problems))

    def test_dry_run_on_synthetic_decisions(self):
        """Synthetic: every reading equals the original; one shared item 'corrected' to not stated, one control 'unclear'."""
        shared = next(i for i in self.v['items'] if i['group'] == 'shared' and i['reveal']['annotated']['values'])
        control = next(i for i in self.v['items'] if i['group'] == 'control')
        t = shared['type']
        corrected = {f'{t}__status': 'not_stated'}
        record = {'view_sha256': self.v['view_sha256'], 'items': {
            shared['id']: {'reading': corrected, 'locked_at': '2026-11-14T10:00:00Z', 'decision': 'annotation_needs_correcting',
                           'decided_at': '2026-11-14T10:01:00Z', 'note': 'synthetic dry run'},
            control['id']: {'reading': self._reading(control), 'locked_at': '2026-11-14T10:00:00Z', 'decision': 'trial_unclear',
                            'decided_at': '2026-11-14T10:01:00Z', 'note': 'synthetic dry run'}}}
        rep = rr.sensitivity(record, self.v)
        primary = json.loads((ROOT / 'docs/verification/eligibility_validation_v2.json').read_text())
        for t2 in v2.TYPES:
            self.assertEqual(rep['analyses']['original_primary']['v1_1'][t2]['decision'], primary['per_type'][t2]['decision'])
        self.assertEqual(rep['correction_rates']['shared']['corrections'], 1)
        self.assertEqual(rep['correction_rates']['control']['unclear'], 1)
        self.assertEqual(rep['blind_reading_reproducibility']['control'], {'blind_reading_equals_original': 1, 'of': 1})
        self.assertEqual(rep['blind_reading_reproducibility']['shared'], {'blind_reading_equals_original': 0, 'of': 1})
        self.assertEqual(rep['corrections'][0]['to']['status'], 'not_stated')
        self.assertFalse(rep['clinical_prediction_validated'])
        self.assertEqual(set(rep['analyses']), {'original_primary', 'corrected_unclear_kept', 'corrected_unclear_excluded'})

    def test_deviation_handling(self):
        skip = rr.unblinded_items()
        self.assertEqual(len(skip), 5)
        self.assertTrue(all(k in self.by_id and self.by_id[k]['group'] == 'shared' for k in skip))
        item = self.by_id[skip[0]]
        t = item['type']
        record = {'view_sha256': self.v['view_sha256'], 'items': {
            item['id']: {'reading': {f'{t}__status': 'not_stated'}, 'locked_at': '2026-11-14T10:00:00Z',
                         'decision': 'annotation_needs_correcting', 'decided_at': '2026-11-14T10:01:00Z', 'note': 'synthetic dry run'}}}
        out = rr.report(record, self.v)
        self.assertEqual(out['all_decisions']['correction_rates']['shared']['corrections'], 1)
        self.assertEqual(out['without_unblinded_items']['correction_rates']['shared']['corrections'], 0)
        self.assertEqual(out['all_decisions']['blind_reading_reproducibility']['shared']['of'], 0)
        self.assertEqual(out['without_unblinded_items']['analyses']['corrected_unclear_kept'],
                         out['without_unblinded_items']['analyses']['original_primary'])


class ComparisonV1(unittest.TestCase):
    """Pins _same's behaviour before comparison v2 was added (17 November 2026).

    Both locked results — the reference re-reading and the second-annotation agreement — are scored with this
    function, so it must keep comparing the comparator, the value as written and the unit as written, with no
    normalisation at all. Comparison v2 is a separate function; this test is what stops it leaking into v1.
    """

    @staticmethod
    def e(status, *values):
        return {'status': status, 'note': '',
                'values': [{'comparator': c, 'value': v, 'unit': u} for c, v, u in values]}

    def test_identical_entries_agree(self):
        a = self.e('stated', ('>=', '8', 'g/dL'))
        self.assertTrue(rr._same('hemoglobin_min', a, self.e('stated', ('>=', '8', 'g/dL'))))

    def test_status_difference_disagrees(self):
        self.assertFalse(rr._same('hemoglobin_min', self.e('stated', ('>=', '8', 'g/dL')), self.e('not_stated')))

    def test_trailing_zero_disagrees_under_v1(self):
        """">=8" against ">=8.0": the same threshold, scored as a disagreement."""
        self.assertFalse(rr._same('hemoglobin_min',
                                  self.e('stated', ('>=', '8', 'g/dL')),
                                  self.e('stated', ('>=', '8.0', 'g/dL'))))

    def test_equivalent_unit_spellings_disagree_under_v1(self):
        """Two spellings of per-microlitre, both offered by the same picker, scored as a disagreement."""
        self.assertFalse(rr._same('anc_min',
                                  self.e('stated', ('>', '1000', 'cells/uL')),
                                  self.e('stated', ('>', '1000', '/mm3 (= /uL)'))))

    def test_converted_units_disagree_under_v1(self):
        self.assertFalse(rr._same('hemoglobin_min',
                                  self.e('stated', ('>=', '8', 'g/dL')),
                                  self.e('stated', ('>=', '80', 'g/L'))))

    def test_comparator_difference_disagrees(self):
        self.assertFalse(rr._same('hemoglobin_min',
                                  self.e('stated', ('>=', '8', 'g/dL')),
                                  self.e('stated', ('>', '8', 'g/dL'))))

    def test_value_order_does_not_matter(self):
        a = self.e('multiple', ('>=', '100', 'x 10^9/L'), ('>=', '75', 'x 10^9/L'))
        b = self.e('multiple', ('>=', '75', 'x 10^9/L'), ('>=', '100', 'x 10^9/L'))
        self.assertTrue(rr._same('platelets_min', a, b))

    def test_ctype_is_ignored_by_v1(self):
        a, b = self.e('stated', ('>=', '8', 'g/dL')), self.e('stated', ('>=', '8', 'g/dL'))
        self.assertTrue(rr._same(None, a, b))
        self.assertTrue(rr._same('anything', a, b))


class ComparisonV2(unittest.TestCase):
    """Comparison v2 applies the equivalences the extractor scoring already uses (docs/decisions/0002)."""

    e = staticmethod(ComparisonV1.e)

    def test_trailing_zero_agrees(self):
        self.assertTrue(rr._same_v2('hemoglobin_min',
                                    self.e('stated', ('>=', '8', 'g/dL')),
                                    self.e('stated', ('>=', '8.0', 'g/dL'))))

    def test_equivalent_unit_spellings_agree(self):
        """The two per-microlitre spellings anc_min's own picker offers."""
        self.assertTrue(rr._same_v2('anc_min',
                                    self.e('stated', ('>', '1000', 'cells/uL')),
                                    self.e('stated', ('>', '1000', '/mm3 (= /uL)'))))

    def test_it_also_converts_magnitudes_which_v1_did_not(self):
        """Documented consequence: v2 is more permissive than "same spelling"."""
        self.assertTrue(rr._same_v2('hemoglobin_min',
                                    self.e('stated', ('>=', '8', 'g/dL')),
                                    self.e('stated', ('>=', '80', 'g/L'))))
        self.assertTrue(rr._same_v2('anc_min',
                                    self.e('stated', ('>=', '1', 'x 10^9/L')),
                                    self.e('stated', ('>=', '1000', '/mm3 (= /uL)'))))

    def test_a_real_difference_still_disagrees(self):
        for a, b in (((">=", '8', 'g/dL'), ('>', '8', 'g/dL')),
                     ((">=", '8', 'g/dL'), ('>=', '9', 'g/dL'))):
            self.assertFalse(rr._same_v2('hemoglobin_min', self.e('stated', a), self.e('stated', b)))
        self.assertFalse(rr._same_v2('hemoglobin_min', self.e('stated', ('>=', '8', 'g/dL')), self.e('not_stated')))

    def test_a_unit_outside_the_canonical_basis_falls_back_to_the_unit_as_written(self):
        self.assertTrue(rr._same_v2('kidney_function_min',
                                    self.e('stated', ('>=', '45', 'mL/min')),
                                    self.e('stated', ('>=', '45.0', 'mL/min'))))
        self.assertFalse(rr._same_v2('kidney_function_min',
                                     self.e('stated', ('>=', '45', 'mL/min')),
                                     self.e('stated', ('>=', '45', 'mL/min/1.73 m2'))))

    def test_both_versions_are_registered(self):
        self.assertEqual(set(rr.COMPARISONS), {'v1', 'v2'})
        self.assertIs(rr.COMPARISONS['v1'], rr._same)
        self.assertIs(rr.COMPARISONS['v2'], rr._same_v2)


if __name__ == '__main__':
    unittest.main()
