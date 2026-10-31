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

    def test_no_records_pinned_yet(self):
        self.assertEqual(er.REVIEW_RECORDS, ())
        self.assertEqual(er.queue_view()['counts']['unreviewed'], 166)


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
