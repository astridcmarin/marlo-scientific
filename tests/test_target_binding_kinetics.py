"""Constant-free binding solution, limits, provenance and standalone demo export."""
import copy
from decimal import Decimal,localcontext
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('binding_kinetics',ROOT/'intelligence_store/target_binding_kinetics.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)


class BindingKineticsTests(unittest.TestCase):
    def calculate(self,**changes):
        args=dict(free_concentration_nm=10,kon_nm_inv_h_inv=.01,koff_h_inv=.1,
            times_h=[0,.1,1,4,24],initial_fraction=0);args.update(changes)
        return model.calculate_binding_kinetics(**args)

    def test_initial_condition_equilibrium_limit_and_relaxation_half_time(self):
        report=self.calculate();d=report['derived']
        self.assertEqual(report['points'][0]['fraction_bound'],0)
        self.assertEqual(d['kd_nm'],10);self.assertEqual(d['equilibrium_fraction'],.5)
        half=self.calculate(times_h=[0,d['relaxation_half_time_h']])
        self.assertAlmostEqual(half['points'][-1]['fraction_bound'],.25,places=15)
        fast=self.calculate(kon_nm_inv_h_inv=.1,koff_h_inv=1,times_h=[0,72])
        self.assertAlmostEqual(fast['points'][-1]['fraction_bound'],.5,places=15)

    def test_same_affinity_different_speed_and_time_scaling(self):
        report=model.binding_kinetics_example();slow=report['slow_example'];fast=report['fast_example']
        self.assertEqual(slow['derived']['kd_nm'],fast['derived']['kd_nm'])
        self.assertEqual(slow['derived']['equilibrium_fraction'],fast['derived']['equilibrium_fraction'])
        self.assertGreater(fast['points'][3]['fraction_bound'],slow['points'][3]['fraction_bound'])
        shifted=self.calculate(times_h=[0,1,10])
        accelerated=self.calculate(kon_nm_inv_h_inv=.1,koff_h_inv=1,times_h=[0,.1,1])
        for a,b in zip(shifted['points'],accelerated['points']):self.assertAlmostEqual(a['fraction_bound'],b['fraction_bound'],places=15)

    def test_zero_free_concentration_decay_and_initial_equilibrium(self):
        decay=self.calculate(free_concentration_nm=0,initial_fraction=.8)
        for p in decay['points']:self.assertAlmostEqual(p['fraction_bound'],.8*math.exp(-.1*p['time_h']),places=15)
        equilibrium=self.calculate(initial_fraction=.5)
        for p in equilibrium['points']:self.assertAlmostEqual(p['fraction_bound'],.5,places=15)
        falling=self.calculate(initial_fraction=1)
        self.assertTrue(all(b['fraction_bound']<a['fraction_bound'] for a,b in zip(falling['points'],falling['points'][1:])))

    def test_decimal_solution_including_small_changes_and_rate_extremes(self):
        with localcontext() as ctx:
            ctx.prec=80
            for c,kon,koff,initial in [(10,.01,.1,0),(0,.01,.1,.8),(1e6,1e3,1e-9,1),
                (1e-9,1e-9,1e-9,0),(10,.01,.1,1)]:
                report=self.calculate(free_concentration_nm=c,kon_nm_inv_h_inv=kon,koff_h_inv=koff,
                    initial_fraction=initial,times_h=[0,1e-10,.1,1,72])
                dc,dkon,dkoff,di=map(lambda v:Decimal(str(v)),[c,kon,koff,initial])
                rate=dkon*dc+dkoff;eq=dkon*dc/rate
                for p in report['points']:
                    expected=float(eq+(di-eq)*(-rate*Decimal(str(p['time_h']))).exp())
                    self.assertLessEqual(abs(p['fraction_bound']-expected),3e-16)
                    if expected>0:self.assertLessEqual(abs(p['fraction_bound']-expected)/expected,3e-15)
                    self.assertTrue(0<=p['fraction_bound']<=1)

    def test_invalid_types_ranges_time_order_and_budget_fail(self):
        for changes in [{'koff_h_inv':0},{'kon_nm_inv_h_inv':True},{'free_concentration_nm':-1},
            {'initial_fraction':1.1},{'koff_h_inv':float('nan')},{'kon_nm_inv_h_inv':float('inf')},
            {'free_concentration_nm':'10'},{'times_h':[]},{'times_h':[1]},{'times_h':[0,1,1]},
            {'times_h':[0,2,1]},{'times_h':[0,73]},{'times_h':[0,True]},
            {'times_h':list(range(1002))},{'kon_nm_inv_h_inv':10**1000}]:
            with self.assertRaises(ValueError):self.calculate(**changes)

    def test_deterministic_hash_no_mutation_and_no_clinical_link(self):
        times=[0,1,2];before=copy.deepcopy(times)
        a=self.calculate(times_h=times);b=self.calculate(times_h=times)
        self.assertEqual(a,b);self.assertEqual(times,before)
        sha=a.pop('report_sha256');self.assertEqual(sha,model._hash(a))
        for key in ['drug','target','patient_revision_id','pk_run_id','clinical_response']:self.assertIsNone(a[key])
        self.assertIs(a['clinical_prediction_validated'],False)
        self.assertIs(a['ready_for_patient_simulation'],False)
        self.assertEqual(a['inputs']['kon']['unit'],'nM^-1 h^-1')
        self.assertEqual(a['inputs']['koff']['unit'],'h^-1')

    def test_cli_example_roundtrip_and_no_overwrite_or_patient_argument(self):
        cli=ROOT/'scripts/target_binding_kinetics_demo.py'
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'demo.json'
            result=subprocess.run([sys.executable,str(cli),'--json','--output',str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(output.read_text()),json.loads(result.stdout))
            before=output.read_bytes()
            result=subprocess.run([sys.executable,str(cli),'--output',str(output)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(output.read_bytes(),before)
            result=subprocess.run([sys.executable,str(cli),'--pk-run-id','1'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)


if __name__=='__main__':unittest.main()
