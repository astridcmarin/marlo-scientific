"""Simulation 3.0a: bortezomib platelet model transcription and observed reference values."""
from pathlib import Path
import tempfile
import unittest

from intelligence_store.covariate_estimation import CovariateEstimationError
from intelligence_store.bortezomib_platelet_evidence import (check_pk_scaling, load_model_extract,
                                                              load_observed_summary)

DATA = Path(__file__).resolve().parents[1] / 'intelligence_store' / 'data'


class Transcription(unittest.TestCase):
    def test_published_adult_pk_follows_from_the_pediatric_model(self):
        for row in check_pk_scaling():
            self.assertLess(row['relative_difference'], 0.006, row)

    def test_both_variants_and_every_open_question_are_recorded(self):
        extract = load_model_extract()
        self.assertEqual(set(extract['pd_model']['variants']), {'myelosuppression', 'platelet_budding'})
        for variant in extract['pd_model']['variants'].values():
            self.assertTrue({'gamma', 'mtt_h', 'circ0_1e9_per_l', 'slope'} <= set(variant))
        ids = {q['id'] for q in extract['open_questions']}
        self.assertTrue({'concentration_unit', 'negative_effect_term', 'kcirc', 'initial_conditions'} <= ids)
        aic = extract['model_comparison_in_source']['table_s2_bortezomib']
        self.assertLess(aic['platelet_budding']['aic'], aic['myelosuppression']['aic'])
        self.assertFalse(extract['clinical_prediction_validated'])

    def test_negative_effect_threshold_is_stated_correctly(self):
        variants = load_model_extract()['pd_model']['variants']
        self.assertAlmostEqual(1 / variants['myelosuppression']['slope'], 14.29, places=2)
        self.assertAlmostEqual(1 / variants['platelet_budding']['slope'], 2.0, places=6)

    def test_observed_ratio_matches_its_values(self):
        observed = load_observed_summary()
        values = {v['id']: v for v in observed['values']}
        ratio = values['cycle1_day11_mean']['value'] / values['baseline_mean']['value']
        self.assertAlmostEqual(ratio, observed['derived_for_checks']['cycle1_day11_over_baseline']['value'], places=4)

    def test_changed_files_are_refused(self):
        for name, loader in (('bortezomib_platelet_model_extract_v1.json', load_model_extract),
                             ('bortezomib_platelet_observed_v1.json', load_observed_summary)):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / name
                path.write_bytes((DATA / name).read_bytes() + b' ')
                with self.assertRaises(CovariateEstimationError):
                    loader(path)


if __name__ == '__main__':
    unittest.main()
