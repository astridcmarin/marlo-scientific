import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.patient_state import digest
from intelligence_store.published_transit_reference import (
    load_structure_contract, published_transit_reference, _reference_calculation,
    register_published_transit_reference_commands)


def closed_form(t):
    # Erlang-chain convolution: 8 equal-rate precentral boxes feeding central.
    n=8;k=13.5;ke=12/68.8;x=(k-ke)*t
    if t==0:return 0.0
    if x<10:
        term=x**n/math.factorial(n);total=term
        for j in range(n+1,200):
            term*=x/j;total+=term
            if term<1e-17*total:break
        tail=math.exp(-x)*total
    else:
        tail=1-math.exp(-x)*sum(x**j/math.factorial(j) for j in range(n))
    return 1000/68.8*(k/(k-ke))**n*math.exp(-ke*t)*tail


class PublishedTransitReferenceTests(unittest.TestCase):
    def test_exact_source_topology_units_and_main_text_agreement(self):
        report=published_transit_reference();s=report['structure']
        self.assertEqual(s['precentral_stage_count'],8)
        self.assertEqual(s['serial_precentral_order'],['ABS']+[f'TRANS{i}' for i in range(1,8)])
        self.assertEqual(s['source_compartment_order'][:2],['ABS','CEN'])
        self.assertEqual(s['central_inflow_source_index'],9)
        self.assertEqual(report['units']['source_CP'],'mg/L')
        self.assertEqual(report['units']['conversion_factor'],1000)
        self.assertEqual(report['reference_values']['apparent_clearance_l_h'],12)
        self.assertEqual(report['reference_values']['apparent_volume_l'],68.8)
        self.assertEqual(report['source']['sha256'],'261734ad9632f1a0f19156b8b4b6cd88d6637cbefe89be4363791caeeda11849')

    def test_eight_stage_response_matches_independent_closed_form(self):
        report=published_transit_reference()
        for p in report['points']:
            self.assertAlmostEqual(p['concentration_ng_ml'],closed_form(p['time_h']),delta=1e-8)
            amounts=p['transit_amounts_mg']+[p['central_amount_mg'],p['eliminated_amount_mg']]
            self.assertEqual(len(p['transit_amounts_mg']),8)
            self.assertAlmostEqual(math.fsum(amounts),1,delta=1e-12)
            self.assertAlmostEqual(p['concentration_ng_ml'],1000*p['central_amount_mg']/68.8,delta=1e-12)
        self.assertAlmostEqual(report['analytic_auc_0_infinity_ng_h_ml'],1000/12)
        self.assertLess(report['auc_0_horizon_ng_h_ml'],1000/12)

    def test_step_refinement_and_wrong_seven_box_convention(self):
        coarse=_reference_calculation(.004);fine=_reference_calculation(.002)
        ec=max(abs(p['concentration_ng_ml']-closed_form(p['time_h'])) for p in coarse['points'])
        ef=max(abs(p['concentration_ng_ml']-closed_form(p['time_h'])) for p in fine['points'])
        self.assertGreater(ec/ef,8)
        from intelligence_store.transit_kernel import solve_transit
        wrong=solve_transit(dose_mg=1,volume_l=68.8,clearance_l_h=12,transit_rate_h=13.5,
                           stages=7,max_step_h=.001)
        correct=published_transit_reference()
        self.assertGreater(max(abs(a['concentration_ng_ml']-b['concentration_ng_ml'])
            for a,b in zip(correct['points'],wrong['points'])),.1)

    def test_integrity_and_missing_or_changed_contract_fail_closed(self):
        report=published_transit_reference();copy=dict(report);sha=copy.pop('report_sha256')
        self.assertEqual(digest(copy),sha)
        self.assertEqual(report,published_transit_reference())
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'changed.json'
            with self.assertRaises(ValueError):load_structure_contract(path)
            path.write_text('{}')
            with self.assertRaises(ValueError):load_structure_contract(path)
        with patch('intelligence_store.published_transit_reference.load_structure_contract',side_effect=ValueError('Missing contract')):
            with self.assertRaises(ValueError):published_transit_reference()

    def test_no_patient_database_network_or_clinical_ready_claim(self):
        with patch('sqlalchemy.engine.Engine.connect',side_effect=AssertionError('Database')), \
             patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('intelligence_store.patient_state_revisions.read_revision',side_effect=AssertionError('Patient')):
            report=published_transit_reference()
        self.assertFalse(report['ready_for_patient_simulation']);self.assertIsNone(report['patient_revision_id'])
        self.assertEqual(report['verification_input']['amount_mg'],1)
        self.assertIn('Not a NONMEM run',report['validation_scope'])

    def test_cli_text_json_and_export_never_overwrite(self):
        app=Flask(__name__);register_published_transit_reference_commands(app);runner=app.test_cli_runner()
        text=runner.invoke(args=['pk-structure-reference']);self.assertEqual(text.exit_code,0)
        self.assertIn('8 = ABS + TRANS1 through TRANS7',text.output)
        result=runner.invoke(args=['pk-structure-reference','--json']);self.assertEqual(result.exit_code,0)
        self.assertEqual(json.loads(result.output),published_transit_reference())
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.json'
            self.assertEqual(runner.invoke(args=['pk-structure-reference','--output',str(path)]).exit_code,0)
            saved=path.read_bytes()
            self.assertNotEqual(runner.invoke(args=['pk-structure-reference','--output',str(path)]).exit_code,0)
            self.assertEqual(saved,path.read_bytes())
        self.assertNotEqual(runner.invoke(args=['pk-structure-reference','--revision-id','1']).exit_code,0)


if __name__=='__main__':unittest.main()
