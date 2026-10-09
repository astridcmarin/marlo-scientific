"""Generic binding checks; no patient, Flask initialization or live evidence access."""
import copy
from decimal import Decimal,localcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('generic_occupancy',ROOT/'intelligence_store/target_occupancy.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
CLI=ROOT/'scripts/target_occupancy_demo.py'


class TargetOccupancyTests(unittest.TestCase):
    def test_zero_half_and_known_equilibrium_ratios(self):
        report=model.target_occupancy_example()
        for point,expected in zip(report['points'],[0,1/11,.5,.8,.9,.99]):
            self.assertAlmostEqual(point['fraction_bound'],expected,places=15)

    def test_monotonicity_and_tighter_binding_at_same_concentration(self):
        values=[0,.01,.1,1,10,100,1000]
        fractions=model.calculate_target_occupancy(kd_nm=10,free_concentrations_nm=values)['points']
        self.assertTrue(all(0<=p['fraction_bound']<=1 for p in fractions))
        self.assertTrue(all(b['fraction_bound']>a['fraction_bound'] for a,b in zip(fractions,fractions[1:])))
        low=model.calculate_target_occupancy(kd_nm=1,free_concentrations_nm=[10])['points'][0]['fraction_bound']
        high=model.calculate_target_occupancy(kd_nm=100,free_concentrations_nm=[10])['points'][0]['fraction_bound']
        self.assertGreater(low,high)

    def test_equivalent_common_scaling_and_decimal_reference(self):
        a=model.calculate_target_occupancy(kd_nm=10,free_concentrations_nm=[1,10,100])
        b=model.calculate_target_occupancy(kd_nm=1000,free_concentrations_nm=[100,1000,10000])
        self.assertEqual([p['fraction_bound'] for p in a['points']],[p['fraction_bound'] for p in b['points']])
        with localcontext() as ctx:
            ctx.prec=80
            for kd in [1e-12,1e-3,1,10,1e12]:
                for c in [0,1e-12,.1,10,10000,1e12]:
                    actual=model.calculate_target_occupancy(kd_nm=kd,free_concentrations_nm=[c])['points'][0]['fraction_bound']
                    expected=float(Decimal(str(c))/(Decimal(str(kd))+Decimal(str(c))))
                    self.assertLessEqual(abs(actual-expected),2e-16)

    def test_invalid_values_units_types_order_and_budget_rejected(self):
        for kd in [0,-1,True,'10',float('nan'),float('inf'),1e-13,1e13,10**1000]:
            with self.subTest(kd=repr(kd)[:30]),self.assertRaises(ValueError):
                model.calculate_target_occupancy(kd_nm=kd,free_concentrations_nm=[1])
        for concentrations in [[],[1,1],[2,1],[True],['10'],[-1],[float('nan')],[float('inf')],[1e13],list(range(1002)),(0,1)]:
            with self.subTest(concentrations=str(concentrations)[:30]),self.assertRaises(ValueError):
                model.calculate_target_occupancy(kd_nm=10,free_concentrations_nm=concentrations)
        with self.assertRaises(TypeError):model.calculate_target_occupancy(kd_nm=10,free_concentrations_ng_ml=[1])

    def test_input_preservation_determinism_digest_and_scientific_scope(self):
        values=[0,1,10];original=copy.deepcopy(values)
        a=model.calculate_target_occupancy(kd_nm=10,free_concentrations_nm=values)
        b=model.calculate_target_occupancy(kd_nm=10,free_concentrations_nm=values)
        self.assertEqual(values,original);self.assertEqual(a,b)
        sha=a.pop('report_sha256')
        self.assertEqual(sha,hashlib.sha256(json.dumps(a,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()).hexdigest())
        for key in ['drug','target','patient_revision_id','pk_run_id','clinical_response']:self.assertIsNone(a[key])
        self.assertIs(a['clinical_prediction_validated'],False)
        self.assertIs(a['ready_for_patient_simulation'],False)
        self.assertEqual(a['dynamic_simulation_status'],'not_run')
        self.assertEqual(a['inputs']['kd']['origin'],'invented_educational_input')
        a['concept_references'][0]['title']='changed'
        self.assertNotEqual(a['concept_references'],model.target_occupancy_example()['concept_references'])

    def run_cli(self,*args):
        return subprocess.run([sys.executable,str(CLI),*args],capture_output=True,text=True)

    def test_cli_json_roundtrip_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'demo.json'
            result=self.run_cli('--json','--output',str(path))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),json.loads(path.read_text()))
            before=path.read_bytes()
            result=self.run_cli('--output',str(path))
            self.assertNotEqual(result.returncode,0);self.assertEqual(path.read_bytes(),before)

    def test_cli_explicit_inputs_invalid_modes_and_no_patient_adapter(self):
        result=self.run_cli('--kd-nm','5','--free-concentrations-nm','0','5','20','--json')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['points'][1]['fraction_bound'],.5)
        for args in [('--kd-nm','10'),('--free-concentrations-nm','1'),
            ('--kd-nm','nan','--free-concentrations-nm','1'),('--patient-revision-id','1'),
            ('--kd-nm','10','--free-concentrations-nm','2','1')]:
            self.assertNotEqual(self.run_cli(*args).returncode,0)

    def test_standalone_does_not_initialize_package_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'intelligence_store').mkdir();(root/'scripts').mkdir()
            (root/'intelligence_store/__init__.py').write_text('raise RuntimeError("Storage initialization forbidden")')
            (root/'intelligence_store/target_occupancy.py').write_bytes((ROOT/'intelligence_store/target_occupancy.py').read_bytes())
            cli=root/'scripts/target_occupancy_demo.py';cli.write_bytes(CLI.read_bytes())
            result=subprocess.run([sys.executable,str(cli)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('No drug or patient model',result.stdout)


if __name__=='__main__':unittest.main()
