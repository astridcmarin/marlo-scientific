"""Drug catalogue v2 (18 November 2026): ixazomib added from the NINLARO DailyMed SPL, version 18.

Evidence-first plan item 5. The four linked catalogues (names, mechanism, safety, interactions) move to v2 together,
because each dependent catalogue pins the name catalogue. The v1 files stay unchanged; every v1 entry is carried into
v2 unchanged, and ixazomib is the only addition.
"""
import hashlib
import json
import unittest
from pathlib import Path

from intelligence_store import drug_aliases, interactions, mechanisms, safety

DATA = Path(drug_aliases.__file__).parent / 'data'
NAMES = ('drug_aliases', 'drug_annotations', 'drug_safety', 'drug_interactions')
V1_PINS = {'drug_aliases': drug_aliases.CATALOG_V1_SHA256, 'drug_annotations': mechanisms.ANNOTATION_V1_SHA256,
           'drug_safety': safety.CATALOG_V1_SHA256, 'drug_interactions': interactions.CATALOG_V1_SHA256}
SPL = {'set_id': '038f2461-834b-4488-9ebd-863c83eef5a7', 'label_version': 18, 'label_effective_date': '20260811',
       'retrieved_xml_sha256': '2292dfec663f940ba661c067346ed3ad88142029dbe6f2a3bbfde18619cb40e8'}


def raw(name, version):
    return (DATA / f'{name}_v{version}.json').read_bytes()


def entry_id(entry):
    return entry.get('id') or entry['entity_id']


def summary_with(names_by_trial):
    """The smallest summary reconcile_drug_aliases reads: one raw-name row per name."""
    rows = {}
    for nct, names in names_by_trial.items():
        for name in names:
            rows.setdefault(name, []).append(nct)
    return {'groups': {'drug_intervention': [{'label': n, 'count': len(ids), 'nct_ids': ids} for n, ids in rows.items()]}}


class CatalogueV2(unittest.TestCase):
    def test_v1_files_are_kept_unchanged(self):
        for name in NAMES:
            self.assertEqual(hashlib.sha256(raw(name, 1)).hexdigest(), V1_PINS[name], name)

    def test_v2_is_v1_plus_ixazomib_only(self):
        for name in NAMES:
            v1, v2 = json.loads(raw(name, 1)), json.loads(raw(name, 2))
            self.assertEqual(v2['entries'][:-1], v1['entries'], name)
            self.assertEqual(entry_id(v2['entries'][-1]), 'ixazomib', name)
            self.assertEqual({k for k in v2 if v2[k] != v1.get(k)} - {'entries'},
                             {'catalog_version'} | ({'alias_catalog_version', 'alias_catalog_sha256'}
                                                    if name != 'drug_aliases' else set()), name)
            self.assertTrue(v2['catalog_version'].endswith('-v1.4'), name)

    def test_dependent_catalogues_pin_the_v2_names(self):
        names = drug_aliases.load_alias_catalog()
        self.assertEqual(names['sha256'], drug_aliases.CATALOG_SHA256)
        for name in NAMES[1:]:
            doc = json.loads(raw(name, 2))
            self.assertEqual((doc['alias_catalog_version'], doc['alias_catalog_sha256']),
                             (names['catalog_version'], names['sha256']), name)

    def test_loaders_accept_v2_and_cover_ixazomib(self):
        names = drug_aliases.load_alias_catalog()
        pins = {'catalog_version': names['catalog_version'], 'catalog_sha256': names['sha256'],
                'catalog_entries': names['entries']}
        for loader in (mechanisms.load_annotation_catalog, safety.load_safety_catalog, interactions.load_interaction_catalog):
            self.assertIn('ixazomib', loader(pins)['entity_index'], loader.__name__)

    def test_every_ixazomib_entry_cites_the_same_spl_version(self):
        for name in NAMES:
            source = json.loads(raw(name, 2))['entries'][-1]['source']
            self.assertEqual({k: source[k] for k in SPL}, SPL, name)
            self.assertTrue(source['url'].endswith('setid=' + SPL['set_id'] + '&version=18'), name)
            self.assertEqual(source['verified_on'], '2026-11-18', name)

    def test_names_are_the_generic_and_the_brand_only(self):
        entry = drug_aliases.load_alias_catalog()['entries'][-1]
        self.assertEqual(entry['aliases'], ['Ixazomib', 'Ninlaro'])

    def test_reviewed_names_now_join_the_ixazomib_row(self):
        # The reviewed formatting mappings for Ixazomib Citrate and MLN9708 point at entity 'ixazomib'; with v1 they
        # stayed a reviewed row outside the catalogue, with v2 they join the label-sourced row.
        summary = summary_with({'NCT0001': ['Ixazomib'], 'NCT0002': ['Ninlaro'], 'NCT0003': ['Ixazomib Citrate'],
                                'NCT0004': ['MLN9708'], 'NCT0005': ['Bortezomib']})
        rows = {r['key']: r for r in drug_aliases.reconcile_drug_aliases(summary)['groups']}
        ixa = rows['catalog:ixazomib']
        self.assertEqual(ixa['nct_ids'], ['NCT0001', 'NCT0002', 'NCT0003', 'NCT0004'])
        self.assertEqual(ixa['mapping_status'], 'source-backed')
        self.assertEqual(ixa['reviewed_mapping_keys'], ['ixazomib citrate', 'mln9708'])
        self.assertNotIn('reviewed:ixazomib', rows)
        self.assertEqual(rows['catalog:bortezomib']['nct_ids'], ['NCT0005'])

    def test_v1_kept_ixazomib_outside_the_catalogue(self):
        # Pins the earlier behaviour this version changes.
        doc = json.loads(raw('drug_aliases', 1))
        self.assertNotIn('ixazomib', {e['id'] for e in doc['entries']})

    def test_safety_entry_has_no_boxed_warning_and_section_5_topics(self):
        entry = json.loads(raw('drug_safety', 2))['entries'][-1]
        self.assertFalse(entry['boxed_warning']['present'])
        self.assertEqual([w['sections'] for w in entry['selected_warnings']],
                         [['5.1'], ['5.2'], ['5.3'], ['5.6'], ['5.7'], ['5.9']])

    def test_interaction_partners_are_the_studied_drugs_only(self):
        entry = json.loads(raw('drug_interactions', 2))['entries'][-1]
        self.assertEqual([(r['partner_name'], r['finding']) for r in entry['references']],
                         [('Rifampin', 'exposure_change_reported'), ('Clarithromycin', 'no_significant_effect_reported')])


if __name__ == '__main__':
    unittest.main()
