"""Extraction review round 4 (19 November 2026): the ixazomib entries of drug catalogue v2, in their own queue so round 3
records, including drafts in progress, stay valid."""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

from intelligence_store import extraction_review as er

ROOT = Path(__file__).resolve().parents[1]


def record(decisions, queue='round_4'):
    q = er.load_queue(*er.QUEUES[queue])
    return {'schema_version': er.RECORD_SCHEMA, 'queue_version': q['queue_version'], 'queue_sha256': er.QUEUES[queue][1],
            'reviewer': 'Platform owner', 'reviewed_on': '2026-11-19', 'decisions': decisions}


class RoundFourQueue(unittest.TestCase):
    def setUp(self):
        self.q = er.load_queue(*er.QUEUES['round_4'])

    def test_rebuilds_exactly_from_the_script(self):
        spec = importlib.util.spec_from_file_location('build_review_round_4', ROOT / 'scripts' / 'build_review_round_4.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(json.loads(json.dumps(mod.build())), self.q)

    def test_lists_every_ixazomib_entry_of_the_four_v2_catalogues(self):
        self.assertEqual(self.q['round'], 4)
        groups = {g['id']: g for g in self.q['groups']}
        self.assertEqual({k: len(g['items']) for k, g in groups.items()},
                         {'catalogue_names': 2, 'catalogue_mechanism': 3, 'catalogue_safety': 7, 'catalogue_interactions': 2})
        self.assertEqual({g['file'] for g in self.q['groups']},
                         {f'intelligence_store/data/{n}_v2.json' for n in
                          ('drug_aliases', 'drug_annotations', 'drug_safety', 'drug_interactions')})
        for g in self.q['groups']:
            doc = json.loads((ROOT / g['file']).read_text())
            for i in g['items']:
                index = int(i['pointer'].split('/')[2])
                entry = doc['entries'][index]
                self.assertEqual(entry.get('id') or entry.get('entity_id'), 'ixazomib', i['id'])

    def test_every_item_says_where_to_look_and_ids_are_unique_across_queues(self):
        ids = er.item_ids(self.q)
        self.assertFalse(ids & er.item_ids(er.load_queue()))
        self.assertFalse(ids & er.item_ids(er.load_queue(*er.QUEUES['round_3'])))
        self.assertTrue(all(i['where_to_look'] and i['how_stored'] for g in self.q['groups'] for i in g['items']))

    def test_round_3_queue_is_unchanged(self):
        path, pin = er.QUEUES['round_3']
        self.assertEqual(path.name, 'extraction_review_queue_round3_v4.json')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin)


class Records(unittest.TestCase):
    def test_a_round_4_record_validates_against_round_4(self):
        rec = record({'catalogue_safety:/entries/9/boxed_warning': {'decision': 'matches', 'note': ''}})
        self.assertIs(er.validate_record(rec), rec)
        self.assertEqual(er.queue_key(rec), 'round_4')

    def test_a_round_4_item_in_a_round_3_record_is_refused(self):
        rec = record({'catalogue_safety:/entries/9/boxed_warning': {'decision': 'matches', 'note': ''}}, queue='round_3')
        with self.assertRaises(er.ReviewError):
            er.validate_record(rec)

    def test_round_4_record_pinned_all_fourteen_match(self):
        view = er.round_4_view()
        self.assertEqual(view['counts'], {'unreviewed': 0, 'matches': 14, 'wrong': 0, 'cannot_check': 0})
        self.assertEqual([r['file'] for r in view['records']], ['extraction_review_record_2026-11-19_round4_v1.json'])

    def test_other_queues_are_not_affected_by_the_round_4_record(self):
        self.assertEqual(er.queue_view()['counts']['matches'], 166)
        self.assertEqual(er.round_3_view()['records'], [])


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()

    def test_round_4_page_and_link(self):
        r = self.client.get('/models/extraction-review/round-4')
        self.assertEqual(r.status_code, 200)
        page = r.data.decode()
        self.assertIn('Extraction review, round 4', page)
        self.assertEqual(page.count('type="radio"'), 14 * 3)
        self.assertIn('Where to look, and how it was written', page)
        self.assertIn('038f2461-834b-4488-9ebd-863c83eef5a7', page)
        self.assertIn('/models/extraction-review/round-4', self.client.get('/models/extraction-review').data.decode())


if __name__ == '__main__':
    unittest.main()
