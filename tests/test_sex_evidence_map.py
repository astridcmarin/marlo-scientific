"""Track I: the sex-representation evidence map (plan docs/EVIDENCE_CONNECTIONS_PLAN.md, update 4)."""
import unittest

from intelligence_store import sex_evidence_map as m


class Map(unittest.TestCase):
    def setUp(self):
        self.map = m.build()

    def test_descriptive_only(self):
        self.assertFalse(self.map['clinical_prediction_validated'])
        self.assertIn('predicts nothing', self.map['reading'])

    def test_every_drug_has_a_status_and_sourced_statements(self):
        by = {d['drug']: d for d in self.map['drugs']}
        self.assertEqual(by['lenalidomide']['status'], 'stated')
        self.assertEqual(by['pomalidomide']['status'], 'gap_recorded')
        self.assertEqual(by['dexamethasone']['status'], 'nothing_on_sex_extracted')
        for d in self.map['drugs']:
            for s in d['statements']:
                if s['kind'] != 'gap':
                    self.assertTrue(s['source_title'], (d['drug'], s['text']))

    def test_platform_equations_are_the_published_ones(self):
        self.assertEqual({e['formula'] for e in self.map['platform_equations']},
                         {'fat_free_mass_janmahasatian', 'ideal_body_weight_devine', 'creatinine_clearance_cockcroft_gault',
                          'egfr_ckd_epi_2021_creatinine'})
        cg = next(e for e in self.map['platform_equations'] if e['formula'] == 'creatinine_clearance_cockcroft_gault')
        self.assertIn('0.85', cg['equation'])

    def test_trial_counts_come_from_the_pinned_corpus(self):
        t = self.map['trial_eligibility']
        self.assertEqual(sum(t['eligibility_sex'].values()), t['trials'])
        self.assertEqual(t['eligibility_sex'], {'ALL': 3437, 'FEMALE': 7, 'MALE': 6})
        self.assertIn('Not available', t['enrolment_by_sex'])


class Page(unittest.TestCase):
    def test_page(self):
        from app.app import app
        page = app.test_client().get('/models/sex-evidence')
        self.assertEqual(page.status_code, 200)
        for text in (b'predicts nothing', b'Cockcroft', b'Enrolment by sex', b'3437 open to all sexes'):
            self.assertIn(text, page.data)


if __name__ == '__main__':
    unittest.main()
