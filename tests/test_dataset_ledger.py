"""The dataset ledger: what each model was built from, tuned on or checked against, and which checks were blind."""
import json
import unittest
from datetime import date
from pathlib import Path

from intelligence_store import dataset_ledger as dl

ROOT = Path(__file__).resolve().parents[1]
NOT_CHECKS = ('repository_checkpoint_', 'eligibility_validation_v1_posthoc', 'synthetic_numerical_crosscheck')


class Ledger(unittest.TestCase):
    def setUp(self):
        self.ledger = dl.load_ledger()

    def test_files_plans_and_reports_exist(self):
        for d in self.ledger['datasets'].values():
            for f in d['files']:
                self.assertTrue((ROOT / f).exists(), f)
        for u in self.ledger['uses']:
            for key in ('plan', 'report'):
                if u[key]:
                    self.assertTrue((ROOT / u[key]).exists(), u[key])

    def test_every_check_report_is_listed(self):
        listed = {u['report'] for u in self.ledger['uses'] if u['report']}
        for f in sorted((ROOT / 'docs' / 'verification').glob('*.json')):
            if f.name.startswith(NOT_CHECKS):
                continue
            self.assertIn(f'docs/verification/{f.name}', listed, f'{f.name} has no entry in the dataset ledger')

    def test_blind_checks_were_locked_before_the_values_were_seen(self):
        for u in self.ledger['uses']:
            if u['role'] in dl.BLIND_ROLES:
                plan = json.loads((ROOT / u['plan']).read_text())
                seen = self.ledger['datasets'][u['dataset']]['values_first_seen']
                self.assertLessEqual(date.fromisoformat(plan['recorded_on']), date.fromisoformat(seen), u)

    def test_the_three_blind_checks(self):
        blind = {(u['model'], u['dataset'], u['role']) for u in self.ledger['uses'] if u['role'] in dl.BLIND_ROLES}
        self.assertEqual(blind, {('lenalidomide_hughes_2019', 'bridoux_2016', 'checked_blind_with_deviation'),
                                 ('lenalidomide_kim_2026', 'bridoux_2016', 'checked_blind_with_deviation'),
                                 ('label_exposure_dexamethasone', 'neofordex_epar_studies', 'checked_blind'),
                                 ('eligibility_extractor_v1', 'eligibility_v1_sample', 'checked_blind'),
                                 ('eligibility_extractor_v1_1', 'eligibility_v2_sample', 'checked_blind')})

    def test_reports_that_say_not_blind_are_not_listed_as_blind(self):
        for u in self.ledger['uses']:
            if u['role'] in dl.BLIND_ROLES:
                report = json.loads((ROOT / u['report']).read_text())
                self.assertNotIn('not_blind', str(report.get('classification', '')))


class Gate(unittest.TestCase):
    def test_seen_datasets_refuse_a_blind_check(self):
        for did in ('cc5013_pk001', 'bridoux_2016', 'kim_2026_patients'):
            with self.assertRaises(dl.LedgerError):
                dl.assert_blind_allowed('lenalidomide_renal_pathways_2026', did)

    def test_reserved_before_the_values_were_seen_is_allowed(self):
        # The v2 sample was seen on 12 November (extractor v1.1 scored); the Track C plan was locked on 11 November.
        self.assertEqual(dl.blind_check_problems('eligibility_extractor_llm_c1', 'eligibility_v2_sample'), [])
        self.assertNotIn('eligibility_v2_sample', dl.summary()['unseen_datasets'])
        # A model with no such reservation is refused.
        with self.assertRaises(dl.LedgerError):
            dl.assert_blind_allowed('eligibility_extractor_v2_future', 'eligibility_v2_sample')

    def test_unknown_dataset_must_be_added_first(self):
        with self.assertRaises(dl.LedgerError):
            dl.assert_blind_allowed('lenalidomide_renal_pathways_2026', 'some_new_study')

    def test_plan_declaring_a_blind_check_on_seen_data_is_refused(self):
        plan = {'model': 'lenalidomide_renal_pathways_2026', 'datasets': [{'id': 'bridoux_2016', 'role': 'checked_blind'}]}
        with self.assertRaises(dl.LedgerError):
            dl.validate_plan_datasets(plan)
        plan['datasets'][0]['role'] = 'checked_not_blind'
        self.assertIs(dl.validate_plan_datasets(plan), plan)

    def test_v1_kept_and_v2_only_adds_the_five_labels(self):
        import hashlib
        v1_path = dl.LEDGER_PATH.with_name('dataset_ledger_v1.json')
        self.assertEqual(hashlib.sha256(v1_path.read_bytes()).hexdigest(), dl.LEDGER_V1_SHA256)
        v2_path = dl.LEDGER_PATH.with_name('dataset_ledger_v2.json')
        self.assertEqual(hashlib.sha256(v2_path.read_bytes()).hexdigest(), dl.LEDGER_V2_SHA256)
        v1, v2 = json.loads(v1_path.read_text()), json.loads(v2_path.read_text())
        self.assertEqual(v2['uses'], v1['uses'])
        added = set(v2['datasets']) - set(v1['datasets'])
        self.assertEqual(added, {'kyprolis_label', 'xpovio_label', 'thalomid_label', 'sarclisa_label', 'empliciti_label'})
        self.assertTrue(all(v2['datasets'][d]['values_first_seen'] == '2026-11-04' for d in added))
        self.assertEqual({d: v2['datasets'][d] for d in v1['datasets']}, v1['datasets'])

    def test_v3_only_adds_three_time_course_uses(self):
        v2 = json.loads(dl.LEDGER_PATH.with_name('dataset_ledger_v2.json').read_text())
        v3_path = dl.LEDGER_PATH.with_name('dataset_ledger_v3.json')
        import hashlib
        self.assertEqual(hashlib.sha256(v3_path.read_bytes()).hexdigest(), dl.LEDGER_V3_SHA256)
        v3 = json.loads(v3_path.read_text())
        self.assertEqual(v3['datasets'], v2['datasets'])
        self.assertEqual(v3['uses'][:len(v2['uses'])], v2['uses'])
        added = v3['uses'][len(v2['uses']):]
        self.assertEqual({(u['dataset'], u['role']) for u in added},
                         {('kim_2026_patients', 'built_from'), ('cc5013_pk001', 'checked_not_blind'), ('bridoux_2016', 'checked_not_blind')})
        self.assertTrue(all(u['model'] == 'lenalidomide_body_map_time_course' for u in added))

    def test_v4_adds_the_mass_balance_and_2_0e(self):
        v3 = json.loads(dl.LEDGER_PATH.with_name('dataset_ledger_v3.json').read_text())
        v4 = dl.load_ledger(dl.LEDGER_PATH.with_name('dataset_ledger_v4.json'), dl.LEDGER_V4_SHA256)
        self.assertEqual(set(v4['datasets']) - set(v3['datasets']), {'chen_2012_mass_balance'})
        self.assertEqual(v4['uses'][:len(v3['uses'])], v3['uses'])
        added = v4['uses'][len(v3['uses']):]
        self.assertTrue(all(u['report'].endswith('lenalidomide_renal_pathways_check_v3.json') for u in added))
        self.assertFalse(any(u['role'] in dl.BLIND_ROLES for u in added))

    def test_v5_adds_notes_and_one_use(self):
        v4 = dl.load_ledger(dl.LEDGER_PATH.with_name('dataset_ledger_v4.json'), dl.LEDGER_V4_SHA256)
        v5 = dl.load_ledger(dl.LEDGER_PATH.with_name('dataset_ledger_v5.json'), dl.LEDGER_V5_SHA256)
        self.assertEqual(v5['datasets'], v4['datasets'])
        self.assertEqual(set(v5['roles']), set(v4['roles']))
        strip = lambda u: {k: v for k, v in u.items() if k != 'note'}
        self.assertEqual([strip(u) for u in v5['uses'][:len(v4['uses'])]], v4['uses'])
        self.assertEqual([(u['model'], u['dataset'], u['role']) for u in v5['uses'][len(v4['uses']):]],
                         [('lenalidomide_exposure_safety_2016', 'cc5013_pk001', 'built_from')])
        self.assertTrue(all('largely known' in u['note'] for u in v5['uses'] if u['role'] == 'checked_blind_with_deviation'))

    def test_v6_adds_two_track_c_uses(self):
        v5 = dl.load_ledger(dl.LEDGER_PATH.with_name('dataset_ledger_v5.json'), dl.LEDGER_V5_SHA256)
        v6 = dl.load_ledger(dl.LEDGER_PATH.with_name('dataset_ledger_v6.json'), dl.LEDGER_V6_SHA256)
        self.assertEqual(v6['datasets'], v5['datasets'])
        self.assertEqual(v6['uses'][:len(v5['uses'])], v5['uses'])
        self.assertEqual([(u['model'], u['dataset'], u['role']) for u in v6['uses'][len(v5['uses']):]],
                         [('eligibility_extractor_llm_c1', 'eligibility_v1_sample', 'tuned_on'),
                          ('eligibility_extractor_llm_c1', 'eligibility_v2_sample', 'reserved_for_blind_check')])

    def test_v7_adds_four_acceptance_rule_v2_uses(self):
        v6 = dl.load_ledger(dl.LEDGER_PATH.with_name('dataset_ledger_v6.json'), dl.LEDGER_V6_SHA256)
        v7 = dl.load_ledger(dl.LEDGER_PATH.with_name('dataset_ledger_v7.json'), dl.LEDGER_V7_SHA256)
        self.assertEqual(v7['datasets'], v6['datasets'])
        self.assertEqual(v7['uses'][:len(v6['uses'])], v6['uses'])
        added = v7['uses'][len(v6['uses']):]
        self.assertEqual({(u['model'], u['dataset'], u['role']) for u in added},
                         {(m, d, 'checked_not_blind') for m in ('lenalidomide_hughes_2019', 'lenalidomide_kim_2026')
                          for d in ('cc5013_pk001', 'bridoux_2016')})

    def test_v8_records_the_blind_eligibility_v2_check(self):
        v8 = dl.load_ledger()
        use = next(u for u in v8['uses'] if (u['model'], u['dataset']) == ('eligibility_extractor_v1_1', 'eligibility_v2_sample'))
        self.assertEqual((use['role'], use['report']), ('checked_blind', 'docs/verification/eligibility_validation_v2.json'))
        llm = next(u for u in v8['uses'] if (u['model'], u['dataset']) == ('eligibility_extractor_llm_c1', 'eligibility_v2_sample'))
        self.assertEqual(llm['role'], 'reserved_for_blind_check')

    def test_changed_ledger_is_refused(self):
        with self.assertRaises(dl.LedgerError):
            dl.load_ledger(sha256='0' * 64)


if __name__ == '__main__':
    unittest.main()
