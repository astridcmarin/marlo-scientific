"""Owner review of AI-assisted extractions: queue integrity, record validation, page."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence_store import extraction_review as er

ROOT = Path(__file__).resolve().parent.parent


def record(decisions, **kw):
    q = er.load_queue()
    return dict({'schema_version': er.RECORD_SCHEMA, 'queue_version': q['queue_version'], 'queue_sha256': er.QUEUE_SHA256,
                 'reviewer': 'Platform owner', 'reviewed_on': '2026-11-01', 'decisions': decisions}, **kw)


class Queue(unittest.TestCase):
    def test_queue_resolves_and_lists_pinned_files_only(self):
        q = er.load_queue()
        self.assertEqual(sum(len(g['items']) for g in q['groups']), 166)
        modules = [p.read_text(encoding='utf-8') for p in (ROOT / 'intelligence_store').glob('*.py') if p.name != 'extraction_review.py']
        for g in q['groups']:
            self.assertTrue(any(g['sha256'] in m for m in modules), g['file'])
        ids = [i['id'] for g in q['groups'] for i in g['items']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i['location'] and i['location'] != 'see source note' for g in q['groups'] for i in g['items']))

    def test_key_values_are_listed(self):
        values = {i['id']: i['value'] for g in er.load_queue()['groups'] for i in g['items']}
        self.assertEqual(values['lenalidomide_renal_groups:/groups/0/measurements/auc_infinity/mean'], 2181)
        self.assertEqual(values['lenalidomide_exposure_safety:/odds_ratios_multiple_myeloma/grade_3_4_thrombocytopenia/ci95'], [1.027, 8.598])
        self.assertEqual(values['lenalidomide_hughes_parameters:/parameters/crcl_exponent/value'], 0.224)
        self.assertFalse(any(k.endswith('average_daily_mg') for k in values))

    def test_changed_value_is_refused(self):
        q = json.loads(er.QUEUE_PATH.read_text())
        q['groups'][0]['items'][0]['value'] = 999
        raw = (json.dumps(q) + '\n').encode()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'q.json'
            p.write_bytes(raw)
            with self.assertRaises(er.ReviewError):
                er.load_queue(p, hashlib.sha256(raw).hexdigest())
        with self.assertRaises(er.ReviewError):
            er.load_queue(er.QUEUE_PATH, '0' * 64)


class Records(unittest.TestCase):
    def setUp(self):
        self.first = next(iter(sorted(er.item_ids())))

    def test_validation(self):
        er.validate_record(record({self.first: {'decision': 'matches', 'note': ''}}))
        bad = [record({self.first: {'decision': 'wrong', 'note': ' '}}),
               record({'nope': {'decision': 'matches'}}),
               record({self.first: {'decision': 'maybe'}}),
               record({self.first: {'decision': 'matches'}}, queue_sha256='0' * 64),
               record({self.first: {'decision': 'matches'}}, reviewed_on='yesterday'),
               record({})]
        for r in bad:
            with self.assertRaises(er.ReviewError):
                er.validate_record(r)

    def test_pinned_record_sets_status(self):
        rec = record({self.first: {'decision': 'wrong', 'note': 'Source shows 12.1'}})
        raw = (json.dumps(rec) + '\n').encode()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'r.json').write_bytes(raw)
            with mock.patch.object(er, 'DATA', Path(d)):
                view = er.queue_view(records=(('r.json', hashlib.sha256(raw).hexdigest()),))
                with self.assertRaises(er.ReviewError):
                    er.queue_view(records=(('r.json', '0' * 64),))
        self.assertEqual(view['counts']['wrong'], 1)
        self.assertEqual(view['counts']['unreviewed'], 165)
        st = [i['status'] for g in view['groups'] for i in g['items'] if i['id'] == self.first][0]
        self.assertEqual((st['decision'], st['note']), ('wrong', 'Source shows 12.1'))

    def test_rounds_1_and_2_pinned(self):
        self.assertEqual([n for n, _ in er.REVIEW_RECORDS], ['extraction_review_record_2026-11-03_v1.json',
                                                            'extraction_review_record_2026-11-04_round2_v1.json'])
        round_1 = er.queue_view(er.REVIEW_RECORDS[:1])
        self.assertEqual(round_1['counts'], {'unreviewed': 1, 'matches': 143, 'wrong': 12, 'cannot_check': 10})
        view = er.queue_view()
        self.assertEqual(view['counts'], {'unreviewed': 0, 'matches': 166, 'wrong': 0, 'cannot_check': 0})
        self.assertEqual({r['reviewer'] for r in view['records']}, {'Astrid'})


class Round2(unittest.TestCase):
    def test_round_2_lists_exactly_the_items_not_matching_in_round_1(self):
        view = er.round_2_view()
        ids = [i['id'] for g in view['groups'] for i in g['items']]
        self.assertEqual(len(ids), 23)
        self.assertIn('pomalidomide_label:/scenarios/ketoconazole_strong_cyp3a4_pgp_inhibitor/auc_fold', ids)
        self.assertTrue(all(i['status']['decision'] == 'matches' for g in view['groups'] for i in g['items']))
        before = er.round_2_view(er.REVIEW_RECORDS[:1])
        self.assertTrue(all(i['status'] is None or i['status']['decision'] != 'matches' for g in before['groups'] for i in g['items']))
        self.assertTrue(all(i['where_to_look'] and i['how_stored'] for g in view['groups'] for i in g['items']))

    def test_conversions_stated_agree_with_stored_values(self):
        view = er.round_2_view()
        item = {i['id']: i for g in view['groups'] for i in g['items']}
        dialysis = item['pomalidomide_label:/scenarios/renal_severe_requiring_dialysis/auc_fold']
        self.assertEqual(dialysis['value'], 1.38)
        self.assertIn('+38% → 1.38', dialysis['how_stored'])
        smoking = item['pomalidomide_label:/scenarios/smoking_25_per_day/auc_fold']
        self.assertIn('−32% → 0.68', smoking['how_stored'])

    def test_changed_round_2_list_is_refused(self):
        with mock.patch.object(er, 'ROUND_2_SHA256', '0' * 64):
            with self.assertRaises(er.ReviewError):
                er.round_2_view()


class OwnerReview(unittest.TestCase):
    def test_every_key_resolves_to_queued_files(self):
        queued = {g['file'] for g in er.load_queue()['groups']}
        for key, files in er.KEY_FILES.items():
            self.assertTrue(set(files) <= queued, key)

    def test_all_match_after_rounds_1_and_2(self):
        for key in er.KEY_FILES:
            for r in er.owner_review(key):
                self.assertTrue(r['all_match'], key)
                self.assertIn('Not an independent review', r['text'])

    def test_round_1_alone_reports_the_open_items(self):
        view = er.queue_view(er.REVIEW_RECORDS[:1])
        [r] = er.owner_review('label:pomalidomide', view)
        self.assertFalse(r['all_match'])
        self.assertEqual(r['counts'], {'matches': 18, 'wrong': 12, 'cannot_check': 3, 'unreviewed': 1})
        self.assertIn('12 found wrong', r['text'])

    def test_only_the_exact_file_is_covered(self):
        self.assertEqual(er.owner_review('landscape_ui/data/renal_pk/renal_pk_group_evidence_v2.json'), [])
        self.assertEqual(len(er.owner_review('landscape_ui/data/renal_pk/renal_pk_group_evidence_v1.json')), 1)


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.app = app
        self.client = app.test_client()

    def test_page_and_json(self):
        r = self.client.get('/models/extraction-review')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Download review record', r.data)
        self.assertEqual(r.data.count(b'type="radio"'), 166 * 3)
        self.assertNotIn(b'Round 2: re-check', r.data)
        se = self.client.get('/models/eligibility/shared-errors')
        self.assertEqual(se.status_code, 200)
        self.assertIn(b'Shared-error review', se.data)
        tb = self.client.get('/models/extraction-review/round-3/track-b')
        self.assertEqual(tb.status_code, 200)
        self.assertIn(b'sampled agreements', tb.data)
        self.assertIn(b'The second reading', tb.data)
        r2 = self.client.get('/models/extraction-review/round-2')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data.count(b'type="radio"'), 23 * 3)
        self.assertIn(b'How stored:', r2.data)
        j = json.loads(self.client.get('/models/extraction-review.json').data)
        self.assertEqual(j['total'], 166)

    def test_cli_check(self):
        first = next(iter(sorted(er.item_ids())))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'r.json'
            p.write_text(json.dumps(record({first: {'decision': 'matches', 'note': ''}})))
            res = self.app.test_cli_runner().invoke(args=['extraction-review-check', str(p)])
            self.assertEqual(res.exit_code, 0, res.output)
            self.assertTrue(json.loads(res.output)['valid'])
            p.write_text(json.dumps(record({first: {'decision': 'wrong', 'note': ''}})))
            self.assertNotEqual(self.app.test_cli_runner().invoke(args=['extraction-review-check', str(p)]).exit_code, 0)


if __name__ == '__main__':
    unittest.main()
