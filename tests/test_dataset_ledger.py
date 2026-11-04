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
                                 ('eligibility_extractor_v1', 'eligibility_v1_sample', 'checked_blind')})

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

    def test_unseen_reserved_sample_is_allowed(self):
        self.assertEqual(dl.blind_check_problems('eligibility_extractor_v1_1', 'eligibility_v2_sample'), [])
        self.assertIn('eligibility_v2_sample', dl.summary()['unseen_datasets'])

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
        v3 = dl.load_ledger()
        self.assertEqual(v3['datasets'], v2['datasets'])
        self.assertEqual(v3['uses'][:len(v2['uses'])], v2['uses'])
        added = v3['uses'][len(v2['uses']):]
        self.assertEqual({(u['dataset'], u['role']) for u in added},
                         {('kim_2026_patients', 'built_from'), ('cc5013_pk001', 'checked_not_blind'), ('bridoux_2016', 'checked_not_blind')})
        self.assertTrue(all(u['model'] == 'lenalidomide_body_map_time_course' for u in added))

    def test_changed_ledger_is_refused(self):
        with self.assertRaises(dl.LedgerError):
            dl.load_ledger(sha256='0' * 64)


if __name__ == '__main__':
    unittest.main()
