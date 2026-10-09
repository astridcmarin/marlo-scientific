"""Analytic checks of a generic solver; no lenalidomide model is inferred."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.patient_state import digest
from intelligence_store.transit_kernel import solve_transit,transit_demo,register_transit_kernel_commands


def case(**changes):
    values=dict(dose_mg=1,volume_l=10,clearance_l_h=2,transit_rate_h=1,stages=1,horizon_h=6,display_step_h=0.1)
    values.update(changes);return solve_transit(**values)


class TransitKernelTests(unittest.TestCase):
    def test_one_stage_matches_closed_form_concentration(self):
        report=case()
        for p in report['points']:
            t=p['time_h'];expected=100*1/(1-0.2)*(math.exp(-0.2*t)-math.exp(-t))
            self.assertAlmostEqual(p['concentration_ng_ml'],expected,delta=1e-7)

    def test_equal_absorption_and_elimination_rates_have_finite_limit(self):
        report=case(clearance_l_h=10,stages=3)
        for p in report['points']:
            t=p['time_h'];expected=100*math.exp(-t)*t**3/math.factorial(3)
            self.assertAlmostEqual(p['concentration_ng_ml'],expected,delta=1e-7)

    def test_transit_boxes_match_analytic_amounts_and_mass_is_conserved(self):
        report=case(stages=7)
        for p in report['points']:
            t=p['time_h']
            for i,amount in enumerate(p['transit_amounts_mg']):
                self.assertAlmostEqual(amount,math.exp(-t)*t**i/math.factorial(i),delta=2e-9)
            self.assertAlmostEqual(sum(p['transit_amounts_mg'])+p['central_amount_mg']+p['eliminated_amount_mg'],1,delta=1e-12)
        self.assertLess(report['amount_balance']['max_absolute_error_mg'],1e-12)

    def test_integrated_auc_matches_one_stage_integral_and_long_time_limit(self):
        r=case();last=r['points'][-1];t=last['time_h']
        expected=100/(1-0.2)*((1-math.exp(-0.2*t))/0.2-(1-math.exp(-t)))
        self.assertAlmostEqual(last['auc_0_t_ng_h_ml'],expected,delta=1e-7)
        long=case(stages=3,horizon_h=100,display_step_h=0.1)
        self.assertAlmostEqual(long['auc_0_horizon_ng_h_ml'],500,delta=1e-4)
        self.assertEqual(long['analytic_auc_0_infinity_ng_h_ml'],500)

    def test_step_refinement_reduces_error_and_input_dose_scales_linearly(self):
        coarse=case(max_step_h=0.05);fine=case(max_step_h=0.025)
        target=100/(1-0.2)*(math.exp(-0.2*6)-math.exp(-6))
        error_coarse=abs(coarse['points'][-1]['concentration_ng_ml']-target)
        error_fine=abs(fine['points'][-1]['concentration_ng_ml']-target)
        self.assertGreater(error_coarse,8*error_fine)
        doubled=case(dose_mg=2)
        base=case()
        for a,b in zip(base['points'],doubled['points']):
            self.assertAlmostEqual(b['concentration_ng_ml'],2*a['concentration_ng_ml'])
            self.assertAlmostEqual(b['auc_0_t_ng_h_ml'],2*a['auc_0_t_ng_h_ml'])

    def test_invalid_numbers_stages_and_excessive_work_fail(self):
        for value in (None,True,0,-1,'1',float('nan'),float('inf'),10**400):
            for key in ('dose_mg','volume_l','clearance_l_h','transit_rate_h','horizon_h','display_step_h','max_step_h'):
                with self.assertRaises(ValueError):case(**{key:value})
        for stages in (0,21,True,1.5):
            with self.assertRaises(ValueError):case(stages=stages)
        with self.assertRaises(ValueError):case(display_step_h=0.00001)
        with self.assertRaises(ValueError):case(max_step_h=0.00000001)
        with self.assertRaises(ValueError):case(transit_rate_h=1000000)

    def test_endpoint_grid_and_deterministic_integrity(self):
        r=case(horizon_h=1,display_step_h=0.3)
        self.assertEqual(len(r['points']),5)
        self.assertEqual(r['points'][0]['time_h'],0)
        self.assertEqual(r['points'][-1]['time_h'],1)
        body=copy.deepcopy(r);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)
        self.assertEqual(r,case(horizon_h=1,display_step_h=0.3))
        self.assertEqual(r['points'][0]['central_amount_mg'],0)
        self.assertEqual(r['points'][0]['transit_amounts_mg'],[1])

    def test_no_patient_published_model_or_network_connection(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            with patch('intelligence_store.pk_parameter_reference.load_parameter_extract',side_effect=AssertionError('No published extract')):
                with patch('intelligence_store.patient_state_revisions.read_revision',side_effect=AssertionError('No patient')):
                    r=transit_demo()
        self.assertIsNone(r['drug']);self.assertIsNone(r['patient_revision_id'])
        self.assertFalse(r['ready_for_patient_simulation'])
        self.assertEqual(r['model_kind'],'invented_mathematical_example')

    def test_cli_export_never_overwrites_and_needs_no_database(self):
        app=Flask(__name__);register_transit_kernel_commands(app);runner=app.test_cli_runner()
        result=runner.invoke(args=['transit-demo']);self.assertEqual(result.exit_code,0,result.output)
        result=runner.invoke(args=['transit-demo','--json']);self.assertEqual(result.exit_code,0,result.output)
        self.assertEqual(json.loads(result.output),transit_demo())
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'demo.json';args=['transit-demo','--output',str(p)]
            self.assertEqual(runner.invoke(args=args).exit_code,0);original=p.read_bytes()
            self.assertNotEqual(runner.invoke(args=args).exit_code,0);self.assertEqual(original,p.read_bytes())

if __name__=='__main__':unittest.main()
