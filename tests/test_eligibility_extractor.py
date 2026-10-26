"""Phase 4.1d: the rule-based eligibility extractor. Examples are taken or adapted from development-set trials only."""
import unittest

from intelligence_store.eligibility_extractor import canonical, clean, equation, extract, segments


def squeeze(text):
    return ' '.join(clean(text).split())


def values(text, ctype):
    r = extract(text)[ctype]
    return r['status'], [(v['comparator'], v['value'], v['unit']) for v in r['values']]


class Cleaning(unittest.TestCase):
    def test_registry_escapes_and_spelled_out_comparators(self):
        self.assertEqual(squeeze(r'ANC \>= 1000'), 'ANC >= 1000')
        self.assertEqual(squeeze('ECOG < or = 2'), 'ECOG <= 2')
        self.assertEqual(squeeze('Creatinine clearance greater than or equal to 30'), 'Creatinine clearance >= 30')
        self.assertEqual(squeeze('ALT less or equal to 2.5 times'), 'ALT <= 2.5 times')
        self.assertEqual(squeeze(r'ECOG score 0\~2'), 'ECOG score 0-2')

    def test_sections_are_tracked(self):
        segs = list(segments('Inclusion Criteria:\n* ECOG 0-2\n\nExclusion Criteria:\n* Platelets < 50,000/mm3'))
        self.assertEqual(segs[-1][0], 'exclusion')
        self.assertEqual(segs[1], ('inclusion', '* ECOG 0-2'))

    def test_numbered_items_run_together_are_split(self):
        segs = [s for _, s in segments('7. Recovered from toxicity 8. ECOG performance status <= 2 9. Estimated GFR >= 30 ml/min/1.73 m^2')]
        self.assertEqual(len(segs), 3)


class Thresholds(unittest.TestCase):
    def test_kidney_with_equation(self):
        r = extract('* Calculated creatinine clearance >= 30 mL/min (Cockcroft-Gault formula)')['kidney_function_min']
        self.assertEqual(r['status'], 'stated')
        self.assertEqual((r['values'][0]['comparator'], r['values'][0]['value'], r['values'][0]['unit'], r['values'][0]['equation']),
                         ('>=', '30', 'mL/min', 'cockcroft_gault'))
        self.assertEqual(values('* eGFR >= 30 mL/min/1.73 m2 (as calculated by MDRD formula)', 'kidney_function_min')[1],
                         [('>=', '30', 'mL/min/1.73 m2')])
        self.assertEqual(equation('eGFR by CKD-EPI'), 'ckd_epi')

    def test_counts_and_units(self):
        self.assertEqual(values('* Absolute neutrophil count >= 1,000/mm^3', 'anc_min'), ('stated', [('>=', '1000', '/mm3 (= /uL)')]))
        self.assertEqual(values('* ANC > 1 x 109 /l', 'anc_min'), ('stated', [('>', '1', 'x 10^9/L')]))
        self.assertEqual(values('5. ANC >= 0,5 x 109/L and platelet count >35 x 109/L.', 'anc_min')[1], [('>=', '0.5', 'x 10^9/L')])
        self.assertEqual(values('* Platelet count >50x10(9)/L', 'platelets_min')[1], [('>', '50', 'x 10^9/L')])
        self.assertEqual(values('* Hemoglobin >= 8 gram per deciliter (g/dL)', 'hemoglobin_min')[1], [('>=', '8', 'g/dL')])

    def test_exclusion_is_turned_into_the_eligible_side(self):
        text = 'Exclusion Criteria:\n* Creatinine clearance < 30 mL/min\n* Creatinine clearance <= 45 mL/min\n* Serum creatinine > 2.5 mg/dL'
        self.assertEqual(values(text, 'kidney_function_min')[1], [('>=', '30', 'mL/min'), ('>', '45', 'mL/min')])
        self.assertEqual(values(text, 'creatinine_max')[1], [('<=', '2.5', 'mg/dL')])

    def test_inclusion_starting_with_no_is_negated(self):
        self.assertEqual(values('* No decompensated liver disease with serum bilirubin > 2.0 mg/dL', 'bilirubin_max')[1], [('<=', '2.0', 'mg/dL')])

    def test_same_threshold_in_inclusion_and_exclusion_is_counted_once(self):
        text = 'Inclusion Criteria:\n* Platelets >= 75,000/mm3\nExclusion Criteria:\n* Platelet count < 75 x 10^9/L'
        self.assertEqual(values(text, 'platelets_min')[0], 'stated')

    def test_uln_wordings(self):
        self.assertEqual(values('* Serum bilirubin <= 2-fold of upper normal limit', 'bilirubin_max')[1], [('<=', '2', 'x ULN')])
        self.assertEqual(values('* Total bilirubin <= 1.5*the upper limit of normal', 'bilirubin_max')[1], [('<=', '1.5', 'x ULN')])
        self.assertEqual(values('* SGOT/SGPT <= 2.5 X institutional upper limit of normal', 'ast_alt_max')[1], [('<=', '2.5', 'x ULN')])
        self.assertEqual(values('* Creatinine <= ULN', 'creatinine_max')[1], [('<=', '1', 'x ULN')])

    def test_shared_value_across_joined_measures(self):
        text = 'Exclusion Criteria:\n* Clinically significant hepatic dysfunction as noted by bilirubin or AST >3 times the upper normal limit'
        self.assertEqual(values(text, 'bilirubin_max')[1], [('<=', '3', 'x ULN')])
        self.assertEqual(values(text, 'ast_alt_max')[1], [('<=', '3', 'x ULN')])

    def test_direct_bilirubin_is_not_total(self):
        self.assertEqual(values('* Serum direct bilirubin <= 2.0 mg/dl and transaminases <= 3x institution upper limit of normal.', 'bilirubin_max')[0], 'not_stated')

    def test_different_ast_and_alt_limits_are_multiple(self):
        status, vals = values('* AST <= 3 x ULN and ALT <= 2.5 x ULN', 'ast_alt_max')
        self.assertEqual(status, 'multiple')
        self.assertEqual(len(vals), 2)


class Ecog(unittest.TestCase):
    def test_wordings(self):
        for text, expected in [('* ECOG performance status 0-2.', '2'), ('* ECOG performance status of 0, 1 or 2.', '2'),
                               ('* Eastern Cooperative Oncology Group (ECOG) performance status of 0 or 1.', '1'),
                               ('* ECOG performance status <= 2', '2'), ('* ECOG < 3', '2'),
                               ('2. Have an ECOG performance status score of 2 or less', '2')]:
            self.assertEqual(values(text, 'ecog_max'), ('stated', [('<=', expected, 'score')]), text)

    def test_exclusion_and_karnofsky(self):
        self.assertEqual(values('Exclusion Criteria:\n* ECOG performance status (PS) >2.', 'ecog_max')[1], [('<=', '2', 'score')])
        self.assertEqual(values('* Karnofsky performance status >= 70%', 'ecog_max')[0], 'not_stated')
        self.assertEqual(values('* Performance status of 2 as per SWOG scale, unless PS of 3-4 based solely on bone pain.', 'ecog_max')[0], 'not_stated')


class Qualifiers(unittest.TestCase):
    def test_marrow_involvement_exception_is_a_qualifier(self):
        text = '2. Absolute neutrophil count >= 1000/ul and platelet count >= 50,000/ul (>= 30,000/ul if bone marrow plasma cells are >= 50% of cellularity).'
        self.assertEqual(values(text, 'platelets_min'), ('stated', [('>=', '50000', '/mm3 (= /uL)')]))
        self.assertEqual(values(text, 'anc_min'), ('stated', [('>=', '1000', '/mm3 (= /uL)')]))

    def test_gilbert_exception_is_a_qualifier(self):
        text = "* Total bilirubin <= 2.0 mg/dl, except in patients with Gilbert's Syndrome who must have a total bilirubin < 3.0 mg/dL"
        self.assertEqual(values(text, 'bilirubin_max'), ('stated', [('<=', '2.0', 'mg/dL')]))

    def test_unless_clause_second_measure(self):
        text = ('* Neutrophils >= 1.0 x109/L (unless the participant has a known diagnosis of familial neutropenia '
                'in which case an ANC >= 0.75 x 109/L is allowed)')
        self.assertEqual(values(text, 'anc_min'), ('stated', [('>=', '1.0', 'x 10^9/L')]))

    def test_restated_value_in_another_unit_is_one_value(self):
        self.assertEqual(values('* Platelets >= 75,000/mm^3 (>= 75 x 10^9/L)', 'platelets_min'), ('stated', [('>=', '75000', '/mm3 (= /uL)')]))
        self.assertEqual(values('* Hemoglobin >= 8 g/dL (80 g/L)', 'hemoglobin_min')[0], 'stated')

    def test_not_thresholds(self):
        self.assertEqual(values('* Platelet count < 100,000 required for diagnosis', 'platelets_min')[0], 'not_stated')
        self.assertEqual(values('Anaemia: haemoglobin value of >20 g/L below the lower limit of normal', 'hemoglobin_min')[0], 'not_stated')
        self.assertEqual(values('* Granulocyte colony stimulating factor within 2 weeks', 'anc_min')[0], 'not_stated')
        self.assertEqual(values('* Bone marrow infiltration (> 30 percent) and platelets', 'platelets_min')[0], 'not_stated')
        self.assertEqual(values('* Adequate organ function', 'creatinine_max')[0], 'not_stated')


class Canonical(unittest.TestCase):
    def test_exact_equivalences_of_the_plan(self):
        self.assertEqual(canonical('anc_min', '1.0', 'x 10^9/L'), canonical('anc_min', '1000', '/mm3 (= /uL)'))
        self.assertEqual(canonical('anc_min', '1000', 'cells/uL'), canonical('anc_min', '1000', '/mm3 (= /uL)'))
        self.assertEqual(canonical('hemoglobin_min', '80', 'g/L'), canonical('hemoglobin_min', '8', 'g/dL'))
        self.assertEqual(canonical('bilirubin_max', '34.2', 'umol/L'), canonical('bilirubin_max', '2.0', 'mg/dL'))
        self.assertNotEqual(canonical('creatinine_max', '2', 'x ULN'), canonical('creatinine_max', '2', 'mg/dL'))


if __name__ == '__main__':
    unittest.main()
