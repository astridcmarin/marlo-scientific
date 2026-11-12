"""Extraction review round 3 (5 November 2026): its own queue, so the first queue and its records stay unchanged."""
import hashlib
import json
import unittest

from intelligence_store import extraction_review as er
from intelligence_store.drug_label_extracts import EXTRACTS, entries


def record(decisions, queue='round_3'):
    q = er.load_queue(*er.QUEUES[queue])
    return {'schema_version': er.RECORD_SCHEMA, 'queue_version': q['queue_version'], 'queue_sha256': er.QUEUES[queue][1],
            'reviewer': 'Platform owner', 'reviewed_on': '2026-11-06', 'decisions': decisions}


class RoundThreeQueue(unittest.TestCase):
    def setUp(self):
        self.q = er.load_queue(*er.QUEUES['round_3'])

    def test_rebuilds_exactly_from_the_script(self):
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'build_review_round_3.py'
        spec = importlib.util.spec_from_file_location('build_review_round_3', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(json.loads(json.dumps(mod.build())), self.q)

    def test_covers_every_label_entry_and_the_two_new_files(self):
        groups = {g['id']: g for g in self.q['groups']}
        for drug in EXTRACTS:
            self.assertEqual(len(groups[f'label_{drug}']['items']), len(entries(drug)), drug)
        self.assertEqual(sum(len(entries(d)) for d in EXTRACTS), 74)
        self.assertEqual(len(groups['fda_renal_2024']['items']), 7)
        self.assertEqual(len(groups['lenalidomide_label_pk']['items']), 18)
        self.assertEqual(len(groups['fda_hepatic_2026']['items']), 14)
        self.assertEqual(len(groups['lenalidomide_assays']['items']), 4)
        self.assertEqual(len(groups['hughes_precision']['items']), 4)
        self.assertEqual(sum(len(g['items']) for g in self.q['groups']), 121)

    def test_v3_kept_unchanged_and_v4_only_adds_the_precision_and_fixes_the_citation(self):
        v3_path = er.DATA / 'extraction_review_queue_round3_v3.json'
        self.assertEqual(hashlib.sha256(v3_path.read_bytes()).hexdigest(), er.ROUND_3_QUEUE_V3_SHA256)
        v3 = json.loads(v3_path.read_text())
        old = {g['id']: g['items'] for g in v3['groups']}
        new = {g['id']: g['items'] for g in self.q['groups']}
        self.assertEqual(set(new) - set(old), {'hughes_precision'})
        for gid in old:
            if gid != 'lenalidomide_assays':
                self.assertEqual(new[gid], old[gid], gid)
        self.assertNotIn('Hughes DM', json.dumps(self.q))

    def test_every_item_says_where_to_look_and_ids_are_unique_across_queues(self):
        main = er.item_ids(er.load_queue())
        ids = er.item_ids(self.q)
        self.assertFalse(main & ids)
        self.assertTrue(all(i['where_to_look'] and i['how_stored'] for g in self.q['groups'] for i in g['items']))


class Records(unittest.TestCase):
    def test_a_round_3_record_validates_against_its_own_queue(self):
        first = sorted(er.item_ids(er.load_queue(*er.QUEUES['round_3'])))[0]
        er.validate_record(record({first: {'decision': 'matches', 'note': ''}}))
        with self.assertRaises(er.ReviewError):
            er.validate_record(record({first: {'decision': 'matches', 'note': ''}}, queue='main'))

    def test_round_1_and_2_records_still_validate(self):
        self.assertEqual(len(er.load_records()), 2)
        self.assertEqual(er.queue_view()['counts']['matches'], 166)

    def test_round_3_status_feeds_owner_review(self):
        q = er.load_queue(*er.QUEUES['round_3'])
        group = next(g for g in q['groups'] if g['id'] == 'fda_renal_2024')
        rec = record({i['id']: {'decision': 'matches', 'note': ''} for i in group['items']})
        raw = json.dumps(rec).encode()
        name = 'extraction_review_record_test_round3.json'
        path = er.DATA / name
        try:
            path.write_bytes(raw)
            records = er.REVIEW_RECORDS + ((name, hashlib.sha256(raw).hexdigest()),)
            view = er.queue_view(records, 'round_3')
            [status] = er.owner_review(group['file'], view)
            self.assertTrue(status['all_match'])
            self.assertEqual(er.queue_view(records)['total'], 166)
        finally:
            path.unlink()

    def test_track_b_view_lists_what_the_plan_says_the_owner_reviews(self):
        from intelligence_store.double_extraction import load_result
        v = er.track_b_view()
        self.assertEqual(v['track_b_counts'], {'disagree': 35, 'not_comparable': 33, 'sampled_agreement': 20, 'out_of_scope': 21})
        self.assertEqual(v['round_total'], 109)
        listed = {i['id'] for g in v['groups'] for i in g['items']}
        todo = load_result()['owner_to_review']
        self.assertTrue(set(todo['disagreements']) | set(todo['not_comparable']) | set(todo['sampled_agreements']) <= listed)
        self.assertEqual(v['queue_sha256'], er.round_3_view()['queue_sha256'])
        for g in v['groups']:
            for i in g['items']:
                if i['second_reading']['reason'] != 'out_of_scope':
                    self.assertIsNotNone(i['second_reading']['value'], i['id'])

    def test_round_3_view(self):
        v = er.round_3_view()
        self.assertEqual((v['round'], v['round_total']), (3, 121))
        self.assertEqual(v['queue_sha256'], er.ROUND_3_QUEUE_SHA256)


if __name__ == '__main__':
    unittest.main()
