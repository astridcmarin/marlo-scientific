import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pulse_cli', ROOT/'scripts/target_binding_pulse_demo.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
model = cli._load()


class BindingScheduleTests(unittest.TestCase):
    def calculate(self, **changes):
        args = dict(phases=[{'start_time_h':0,'free_concentration_nm':10},
                            {'start_time_h':4,'free_concentration_nm':0}],
                    kon_nm_inv_h_inv=.01, koff_h_inv=.1,
                    times_h=[0,1,4,5,8,24], initial_fraction=0)
        args.update(changes)
        return model.calculate_binding_schedule(**args)

    def test_pulse_matches_independent_association_and_dissociation_equations(self):
        report = self.calculate()
        bound_at_switch = .5*(1-math.exp(-.2*4))
        for p in report['points']:
            t=p['time_h']
            expected=.5*(1-math.exp(-.2*t)) if t<4 else bound_at_switch*math.exp(-.1*(t-4))
            self.assertAlmostEqual(p['fraction_bound'],expected,places=15)
        switch=report['boundaries'][1]
        self.assertEqual(switch['before']['fraction_bound'],switch['after']['fraction_bound'])
        self.assertEqual(switch['before']['free_concentration_nm'],10)
        self.assertEqual(switch['after']['free_concentration_nm'],0)
        self.assertIsNone(report['boundaries'][0]['before'])
        self.assertEqual(report['points'][2]['phase_index'],1)

    def test_off_grid_boundary_is_exact_and_reexposure_carries_state(self):
        switch=4.137
        report=self.calculate(phases=[{'start_time_h':0,'free_concentration_nm':10},
            {'start_time_h':switch,'free_concentration_nm':0},
            {'start_time_h':8,'free_concentration_nm':20}],times_h=[0,1,5,8,12])
        theta1=.5*(1-math.exp(-.2*switch))
        theta2=theta1*math.exp(-.1*(8-switch))
        theta3=2/3+(theta2-2/3)*math.exp(-.3*4)
        self.assertEqual(report['boundaries'][1]['time_h'],switch)
        self.assertAlmostEqual(report['boundaries'][1]['after']['fraction_bound'],theta1,places=15)
        self.assertAlmostEqual(report['boundaries'][2]['after']['fraction_bound'],theta2,places=15)
        self.assertAlmostEqual(report['points'][-1]['fraction_bound'],theta3,places=15)

    def test_split_constant_phase_matches_unsplit_with_nonzero_initial(self):
        whole=self.calculate(phases=[{'start_time_h':0,'free_concentration_nm':10}],initial_fraction=.9)
        split=self.calculate(phases=[{'start_time_h':0,'free_concentration_nm':10},
            {'start_time_h':2.123,'free_concentration_nm':10}],initial_fraction=.9)
        for a,b in zip(whole['points'],split['points']):
            self.assertAlmostEqual(a['fraction_bound'],b['fraction_bound'],places=15)

    def test_invalid_schedule_types_ranges_order_and_budget(self):
        cases=[{'phases':[]},{'phases':[{'start_time_h':1,'free_concentration_nm':10}]},
            {'phases':[{'start_time_h':0,'free_concentration_nm':10,'dose_mg':25}]},
            {'phases':[{'start_time_h':0,'free_concentration_nm':True}]},
            {'phases':[{'start_time_h':0,'free_concentration_nm':float('nan')}]},
            {'phases':[{'start_time_h':0,'free_concentration_nm':-1}]},
            {'phases':[{'start_time_h':0,'free_concentration_nm':1},
                       {'start_time_h':24,'free_concentration_nm':0}]},
            {'phases':[{'start_time_h':0,'free_concentration_nm':1}]*9},
            {'koff_h_inv':0},{'kon_nm_inv_h_inv':'0.01'},{'initial_fraction':1.1},
            {'times_h':[0]},{'times_h':[0,0,1]},{'times_h':[1,2]},
            {'times_h':[0,73]},{'times_h':[i/100 for i in range(1002)]}]
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.calculate(**changes)

    def test_deterministic_integrity_and_scope_without_input_mutation(self):
        phases=[{'start_time_h':0,'free_concentration_nm':10}]
        saved=copy.deepcopy(phases)
        report=self.calculate(phases=phases)
        self.assertEqual(phases,saved)
        self.assertEqual(report,self.calculate(phases=phases))
        unhashed=copy.deepcopy(report);digest=unhashed.pop('report_sha256')
        self.assertEqual(digest,model._hash(unhashed))
        for key in ['drug','target','patient_revision_id','pk_run_id','clinical_response']:
            self.assertIsNone(report[key])
        self.assertFalse(report['clinical_prediction_validated'])
        self.assertFalse(report['ready_for_patient_simulation'])
        for segment in report['segments']:
            nested=copy.deepcopy(segment['constant_concentration_report'])
            self.assertEqual(nested.pop('report_sha256'),model._hash(nested))

    def test_private_loader_preserves_real_package_and_cleans_namespace(self):
        before=dict(sys.modules)
        loaded=cli._load()
        self.assertEqual(set(sys.modules),set(before))
        for key,value in before.items():self.assertIs(sys.modules[key],value)
        self.assertEqual(loaded.binding_pulse_example(),model.binding_pulse_example())

    def test_cli_json_roundtrip_and_no_overwrite_without_application_initializer(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'pulse.json'
            command=[sys.executable,str(ROOT/'scripts/target_binding_pulse_demo.py'),'--json','--output',str(output)]
            result=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),json.loads(output.read_text()))
            contents=output.read_bytes()
            again=subprocess.run(command,text=True,capture_output=True)
            self.assertNotEqual(again.returncode,0)
            self.assertEqual(output.read_bytes(),contents)


if __name__=='__main__':unittest.main()
