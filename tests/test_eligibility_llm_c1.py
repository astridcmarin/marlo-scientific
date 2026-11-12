"""Track C, plan v3: the language-model extractor llm-c1 (prompt, runner, scoring), checked on synthetic data."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from intelligence_store import dataset_ledger as dl
from intelligence_store import eligibility_extractor_llm as llm
from intelligence_store import eligibility_validation_llm as val

ROOT = Path(__file__).resolve().parents[1]


def answer(**over):
    base = {t: {'status': 'not_stated', 'values': []} for t in llm.TYPES}
    base.update(over)
    return base


PLT = {'status': 'stated', 'values': [{'comparator': '>=', 'value': '75', 'unit': 'x 10^9/L', 'section': 'inclusion',
                                       'segment': 'Platelets >= 75 x 10^9/L'}]}


class Frozen(unittest.TestCase):
    def test_prompt_and_plan_are_pinned(self):
        self.assertIn('prompt revision 2', llm.prompt_text())
        plan = val.load_plan()
        self.assertEqual(plan['inputs']['prompt']['sha256'], llm.PROMPT_SHA256)
        v2_plan = ROOT / plan['inputs']['plan_v2']['path']
        self.assertEqual(hashlib.sha256(v2_plan.read_bytes()).hexdigest(), plan['inputs']['plan_v2']['sha256'])
        self.assertFalse(plan['clinical_prediction_validated'])

    def test_plan_passes_the_ledger_blind_rule(self):
        dl.validate_plan_datasets(val.load_plan())
        self.assertTrue(any(u['model'] == 'eligibility_extractor_llm_c1' and u['role'] == 'reserved_for_blind_check'
                            for u in dl.load_ledger()['uses']))


class Parsing(unittest.TestCase):
    def test_valid_answer(self):
        extracted, problems = llm.parse_record(json.dumps(answer(platelets_min=PLT)))
        self.assertEqual(problems, [])
        self.assertEqual(extracted['platelets_min']['values'][0]['value'], '75')

    def test_invalid_answers_are_no_answer(self):
        bad_unit = {'status': 'stated', 'values': [dict(PLT['values'][0], unit='g/dL')]}
        for raw in ('not json', json.dumps({'platelets_min': PLT}), json.dumps(answer(platelets_min=bad_unit)),
                    json.dumps(answer(platelets_min={'status': 'stated', 'values': []}))):
            extracted, problems = llm.parse_record(raw)
            self.assertTrue(problems, raw)
            self.assertTrue(all(e == {'status': 'not_stated', 'values': []} for e in extracted.values()))

    def test_missing_or_duplicate_trials_are_no_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.jsonl'
            line = lambda n: json.dumps({'nct_id': n, 'answer': answer(platelets_min=PLT)})
            path.write_text('\n'.join([line('A'), line('B'), line('B')]) + '\n')
            got = llm.load_outputs(path, ['A', 'B', 'C'])
        self.assertEqual(set(got['problems']), {'B', 'C'})
        self.assertEqual(got['extracted']['A']['platelets_min']['status'], 'stated')


class DryRun(unittest.TestCase):
    def test_evaluate_on_synthetic_annotations(self):
        gold = {'T1': {'criteria': answer(platelets_min=PLT)}, 'T2': {'criteria': answer()}}
        run1 = {'T1': answer(platelets_min=PLT), 'T2': answer()}
        run2 = {'T1': answer(), 'T2': answer()}
        rule = {'T1': answer(), 'T2': answer(platelets_min=PLT)}
        out = val.evaluate(gold, ['T1', 'T2'], run1, run2, rule)
        self.assertEqual(out['run_1']['platelets_min']['tp'], 1)
        self.assertEqual(out['run_2']['platelets_min']['fn_pairs'], 1)
        self.assertEqual(out['paired_with_v1_1']['platelets_min'], {'only_llm_correct': 2, 'only_v1_1_correct': 0, 'both': 0, 'neither': 0})
        self.assertAlmostEqual(out['run_to_run_agreement']['per_type']['platelets_min'], 0.5)
        self.assertEqual(out['errors_run_1'], [])

    def test_two_hundred_trials_make_five_files(self):
        self.assertEqual([len(c) for c in val.chunks([str(i) for i in range(200)])], [40] * 5)


class Development(unittest.TestCase):
    def test_development_record_regenerates(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('dev', ROOT / 'scripts' / 'eligibility_llm_c1_development.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        stored = json.loads((ROOT / 'docs' / 'development' / 'eligibility_llm_c1_development.json').read_text())
        self.assertEqual(mod.build(), stored)
        self.assertEqual(stored['revisions'][-1]['prompt_sha256'], llm.PROMPT_SHA256)
        self.assertEqual([r['no_answer'] for r in stored['revisions']], [0, 0])


if __name__ == '__main__':
    unittest.main()
