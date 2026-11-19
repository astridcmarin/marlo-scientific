"""What the platform holds per drug (evidence-first plan items 6 and 7, 19 November 2026)."""
import unittest

from intelligence_store import drug_holdings as dh


class Holdings(unittest.TestCase):
    def test_unread_sources_carry_no_values_and_no_files(self):
        h = dh.holdings('carfilzomib')
        self.assertEqual({r['dataset'] for r in h['held_unread']},
                         {'badros_2013_carfilzomib_renal', 'quach_2017_carfilzomib_esrd'})
        for r in h['held_unread']:
            self.assertEqual(r['files'], [])
            self.assertIsNone(r['values_first_seen'])

    def test_fitting_data_never_seen_or_held_is_not_a_holding(self):
        keys = {r['dataset'] for r in dh.holdings('lenalidomide')['read'] + dh.holdings('lenalidomide')['held_unread']}
        self.assertNotIn('hughes_2019_fitting_data', keys)
        self.assertIn('cc5013_pk001', keys)

    def test_attribution_by_alias_and_by_model(self):
        self.assertIn('pomalyst_label', {r['dataset'] for r in dh.holdings('pomalidomide')['read']})      # brand alias
        self.assertIn('lignet_2022_platelet_data', {r['dataset'] for r in dh.holdings('bortezomib')['read']})  # model
        self.assertNotIn('kyprolis_label', {r['dataset'] for r in dh.holdings('bortezomib')['read']})

    def test_regulatory_kinds(self):
        self.assertEqual(dh.regulatory_kind({'title': 'NEOFORDEX EPAR public assessment report'}), 'EMA assessment report')
        self.assertEqual(dh.regulatory_kind({'title': 'CAN-1004: bortezomib (FDA review, NDA 021602 S-027)'}), 'FDA review')
        self.assertEqual(dh.regulatory_kind({'title': 'X', 'sources': ['an open-label, single-arm, phase I study']}), None)
        self.assertEqual(dh.regulatory_kind({'title': 'KYPROLIS label pharmacokinetics'}), 'Product label')

    def test_ixazomib_catalogue_files_show_the_round_4_review_for_this_drug_only(self):
        row = next(r for r in dh.holdings('ixazomib')['read'] if r['dataset'] == 'ninlaro_label')
        self.assertEqual(sum(1 for f in row['files'] if f['state'] == 'reviewed_by_owner'), 3)
        self.assertIsNone(dh._catalogue_review('intelligence_store/data/drug_safety_v2.json', 'bortezomib'))

    def test_later_versions_join_their_source_and_scope_files_are_not_sources(self):
        h = dh.holdings('lenalidomide')
        titles = [r['title'] for r in h['read']]
        self.assertFalse(any(t.startswith('Platform scope') for t in titles))
        self.assertEqual(sum(1 for t in titles if t.startswith('CC-5013-PK-001')), 1)
        cc = next(r for r in h['read'] if r['dataset'] == 'cc5013_pk001')
        files = [f['file'] for f in cc['files']]
        self.assertIn('landscape_ui/data/renal_pk/renal_pk_group_evidence_v2.json', files)
        self.assertNotIn('landscape_ui/data/renal_pk/renal_pk_group_evidence_v1.json', files)
        v2 = next(f for f in cc['files'] if f['file'].endswith('renal_pk_group_evidence_v2.json'))
        self.assertEqual(v2['state'], 'earlier_reviewed')

    def test_state_summary(self):
        row = {'files': [{'state': 'reviewed_by_owner'}, {'state': None}], 'checks': ['a', 'b']}
        self.assertEqual(dh.state_summary(row),
                         '1 of 2 files reviewed by the owner; 1 of 2 files not in a review queue; used in 2 locked checks.')


if __name__ == '__main__':
    unittest.main()
