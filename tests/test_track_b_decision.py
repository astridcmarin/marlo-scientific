"""Track B (19 November 2026): the owner's round 3 record and the double-extraction plan's decision rule."""
import unittest

from intelligence_store import double_extraction as de
from intelligence_store import extraction_review as er

RECORD = 'extraction_review_record_2026-11-19_round3_track_b_v1.json'
CORRECTED = {
    'fda_renal_2024:/renal_function_measure/indexed_egfr/quote',
    'fda_renal_2024:/renal_function_measure/cockcroft_gault_weight/quote',
    'fda_hepatic_2026:/recommendations/child_pugh/quote',
    'fda_hepatic_2026:/recommendations/cp_groups/quote',
    'fda_hepatic_2026:/child_pugh_table_1/groups/0',
    'fda_hepatic_2026:/child_pugh_table_1/groups/1',
    'fda_hepatic_2026:/child_pugh_table_1/groups/2',
}


class TrackBRecord(unittest.TestCase):
    def test_pinned_record_covers_the_track_b_list_with_seven_wrong(self):
        rec = next(r for r in er.load_records() if r['file'] == RECORD)
        self.assertEqual(er.queue_key(rec), 'round_3')
        self.assertEqual(len(rec['decisions']), 109)
        wrong = {k for k, d in rec['decisions'].items() if d['decision'] == 'wrong'}
        self.assertEqual(wrong, CORRECTED)
        self.assertTrue(all(rec['decisions'][k]['note'] for k in wrong))


class Decision(unittest.TestCase):
    def test_the_rule_passes_and_labels_the_twelve_unsampled_agreements(self):
        d = de.decision()
        self.assertEqual(d['outcome'], 'pass')
        self.assertEqual((d['sampled'], d['sampled_reviewed'], d['sampled_wrong']), (20, 20, []))
        self.assertEqual(len(d['agreed_sampled_ids']), 12)
        sampled = set(de.load_result()['agreement_sample']['ids'])
        self.assertFalse(sampled & set(d['agreed_sampled_ids']))
        self.assertFalse(CORRECTED & sampled)

    def test_without_the_record_the_rule_is_pending(self):
        records = [r for r in er.REVIEW_RECORDS if r[0] != RECORD]
        self.assertEqual(de.decision(records)['outcome'], 'pending')
        self.assertEqual(de.decision(records)['agreed_sampled_ids'], [])

    def test_a_wrong_sampled_agreement_fails_the_rule(self):
        import hashlib, json, tempfile
        from pathlib import Path
        from unittest import mock
        path = er.DATA / RECORD
        rec = json.loads(path.read_text())
        first = de.load_result()['agreement_sample']['ids'][0]
        rec['decisions'][first] = {'decision': 'wrong', 'note': 'synthetic'}
        raw = json.dumps(rec).encode()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x.json').write_bytes(raw)
            with mock.patch.object(er, 'DATA', Path(d)):
                out = de.decision([('x.json', hashlib.sha256(raw).hexdigest())])
        self.assertEqual(out['outcome'], 'fail')
        self.assertEqual(out['sampled_wrong'], [first])
        self.assertEqual(len(out['review_in_full_ids']), 12)


class Views(unittest.TestCase):
    def test_round_3_is_settled(self):
        self.assertEqual(er.round_3_view()['counts'],
                         {'unreviewed': 0, 'matches': 102, 'wrong': 7, 'cannot_check': 0, 'agreed_sampled': 12})

    def test_file_status_names_agreed_entries_apart_from_owner_review(self):
        text = er.owner_review('intelligence_store/data/label_extract_selinexor_v1.json')[0]['text']
        self.assertIn('18 of 20', text)
        self.assertIn('2 agreed by two independent extractions, sampled, not owner-reviewed', text)
        self.assertNotIn('not yet reviewed', text)


if __name__ == '__main__':
    unittest.main()
