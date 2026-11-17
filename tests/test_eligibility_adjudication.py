"""Adjudication of the second-annotation disagreements: pins, view, page, record rules and a synthetic dry run (16 November 2026)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from intelligence_store import eligibility_adjudication as adj

ROOT = Path(__file__).resolve().parent.parent


class Pins(unittest.TestCase):
    def test_report_is_pinned(self):
        raw = adj.REPORT_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), adj.REPORT_SHA256)

    def test_load_report_refuses_a_changed_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'report.json'
            p.write_text('{"plan_version": "tampered"}')
            with self.assertRaises(ValueError):
                adj.load_report(p)


class View(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = adj.view()

    def test_one_item_per_disagreement(self):
        report = adj.load_report()
        self.assertEqual(self.v['total'], len(report['disagreements_for_adjudication']))
        self.assertEqual(self.v['total'], len(self.v['items']))
        self.assertEqual(len({i['id'] for i in self.v['items']}), self.v['total'])

    def test_every_item_carries_both_readings_and_its_text(self):
        for it in self.v['items']:
            self.assertTrue(it['criteria_text'])
            for side in ('owner', 'annotator_b'):
                self.assertIn(it[side]['status'], ('stated', 'multiple', 'not_stated', 'unclear'))

    def test_the_two_readings_actually_differ(self):
        """The view must hold only pairs the readers disagreed on."""
        def shape(e):
            return (e['status'], sorted((v['comparator'], v['value'], v['unit']) for v in e['values']))
        for it in self.v['items']:
            self.assertNotEqual(shape(it['owner']), shape(it['annotator_b']), it['id'])

    def test_order_follows_the_report(self):
        report = adj.load_report()
        want = [f"{d['nct_id']}:{d['type']}" for d in report['disagreements_for_adjudication']]
        self.assertEqual([i['id'] for i in self.v['items']], want)


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = adj.view()

    def test_page_checksum_is_the_view_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'page.html'
            self.assertEqual(adj.write_page(p, self.v), self.v['view_sha256'])
            self.assertGreater(p.stat().st_size, 10_000)

    def test_page_holds_no_extractor_output_or_agreement_figures(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'page.html'
            adj.write_page(p, self.v)
            html = p.read_text(encoding='utf-8')
            for forbidden in ('v1_1', 'llm_run_1', 'exact_rate', 'exact_agreement', 'detection_kappa'):
                self.assertNotIn(forbidden, html, forbidden)

    def test_page_carries_guide_v2_which_both_readers_used(self):
        self.assertEqual(self.v['guide_sha256'],
                         hashlib.sha256((ROOT / 'docs' / 'ELIGIBILITY_ANNOTATION_GUIDE_V2.md').read_bytes()).hexdigest())


class Record(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = adj.view()

    def rec(self, choice='owner', reason='synthetic'):
        return {'schema_version': adj.RECORD_SCHEMA, 'view_sha256': self.v['view_sha256'],
                'plan_version': self.v['plan_version'], 'locked_at': '2026-11-20T10:00:00Z',
                'decisions': {i['id']: {'choice': choice, 'reason': reason} for i in self.v['items']}}

    def test_a_complete_record_passes(self):
        self.assertEqual(adj.validate_record(self.rec(), self.v)[0], [])

    def test_rules(self):
        ids = [i['id'] for i in self.v['items']]
        bad = self.rec()
        bad['view_sha256'] = 'x' * 64
        self.assertTrue(any('view_sha256' in p for p in adj.validate_record(bad, self.v)[0]))

        bad = self.rec()
        bad['schema_version'] = 'wrong'
        self.assertTrue(any('schema_version' in p for p in adj.validate_record(bad, self.v)[0]))

        bad = self.rec()
        bad['decisions'][ids[0]]['reason'] = '   '
        self.assertTrue(any('reason is required' in p for p in adj.validate_record(bad, self.v)[0]))

        bad = self.rec()
        bad['decisions'][ids[0]]['choice'] = 'the owner is right'
        self.assertTrue(any('choice must be one of' in p for p in adj.validate_record(bad, self.v)[0]))

        bad = self.rec()
        del bad['decisions'][ids[1]]
        self.assertTrue(any('no decision' in p for p in adj.validate_record(bad, self.v)[0]))

        bad = self.rec()
        bad['decisions']['NCT00000000:ecog_max'] = {'choice': 'owner', 'reason': 'x'}
        self.assertTrue(any('not a disagreeing pair' in p for p in adj.validate_record(bad, self.v)[0]))

    def test_dry_run_all_to_one_side(self):
        r = adj.resolution(self.rec('owner'), self.v)
        self.assertEqual(r['resolved_to']['owner'], self.v['total'])
        self.assertEqual(r['reader_errors_among_adjudicated']['annotator_b_wrong'], self.v['total'])
        self.assertEqual(r['reader_errors_among_adjudicated']['owner_annotation_wrong'], 0)
        self.assertFalse(r['clinical_prediction_validated'])

    def test_dry_run_mixed_splits_three_ways(self):
        rec = self.rec()
        for k, i in enumerate(i['id'] for i in self.v['items']):
            rec['decisions'][i]['choice'] = ('owner', 'annotator_b', 'unclear')[k % 3]
        r = adj.resolution(rec, self.v)
        self.assertEqual(sum(r['resolved_to'].values()), self.v['total'])
        self.assertEqual(r['reader_errors_among_adjudicated']['owner_annotation_wrong'], r['resolved_to']['annotator_b'])
        self.assertEqual(r['reader_errors_among_adjudicated']['annotator_b_wrong'], r['resolved_to']['owner'])
        self.assertEqual(sum(sum(row.values()) for row in r['by_type'].values()), self.v['total'])

    def test_resolution_refuses_an_invalid_record(self):
        bad = self.rec()
        bad['decisions'][next(iter(bad['decisions']))]['choice'] = ''
        with self.assertRaises(ValueError):
            adj.resolution(bad, self.v)

    def test_limitations_are_stated(self):
        r = adj.resolution(self.rec(), self.v)
        joined = ' '.join(r['limitations']).lower()
        for must in ('not blind', 'defer', 'only disagreements', 'own plan'):
            self.assertIn(must, joined)
        self.assertIn('lower bounds', r['reader_errors_among_adjudicated']['note'])


if __name__ == '__main__':
    unittest.main()
