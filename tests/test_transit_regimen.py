import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.patient_state import digest
from intelligence_store.transit_regimen import transit_regimen_demo, register_transit_regimen_commands


def analytic_concentration(t):
    if t <= 0: return 0.0
    return 100/(.8**3)*(math.exp(-.2*t)-math.exp(-t)*(1+.8*t+(.8*t)**2/2))


def analytic_auc(t):
    if t <= 0: return 0.0
    integral = (1-math.exp(-.2*t))/.2
    for i in range(3):
        integral -= .8**i*(1-math.exp(-t)*sum(t**j/math.factorial(j) for j in range(i+1)))
    return 100/(.8**3)*integral


class TransitRegimenTests(unittest.TestCase):
    def test_concentration_and_auc_match_independent_analytic_superposition(self):
        report = transit_regimen_demo()
        for p in report['points']:
            t = p['time_h']
            self.assertAlmostEqual(p['concentration_ng_ml'],sum(analytic_concentration(t-d) for d in (0,8,16)),delta=1e-7)
            self.assertAlmostEqual(p['auc_0_t_ng_h_ml'],sum(analytic_auc(t-d) for d in (0,8,16)),delta=1e-7)
        self.assertEqual(report['analytic_auc_0_infinity_ng_h_ml'],1500)
        self.assertLess(report['auc_0_horizon_ng_h_ml'],1500)
        self.assertGreater(report['auc_0_horizon_ng_h_ml'],3*0)
        # A late addition contributes only its elapsed 8 hours by the horizon.
        self.assertAlmostEqual(report['auc_0_horizon_ng_h_ml'],sum(analytic_auc(t) for t in (24,16,8)),delta=1e-7)

    def test_event_jumps_are_local_and_concentration_and_auc_remain_continuous(self):
        report = transit_regimen_demo()
        self.assertEqual([e['time_h'] for e in report['events']],[0,8,16])
        for event in report['event_boundaries']:
            before, after = event['before'],event['after']
            self.assertEqual(before['time_h'],after['time_h'])
            self.assertAlmostEqual(after['transit_amounts_mg'][0]-before['transit_amounts_mg'][0],1)
            self.assertEqual(before['transit_amounts_mg'][1:],after['transit_amounts_mg'][1:])
            for key in ('central_amount_mg','eliminated_amount_mg','concentration_ng_ml','auc_0_t_ng_h_ml'):
                self.assertEqual(before[key],after[key])
            self.assertEqual(after['cumulative_administered_mg']-before['cumulative_administered_mg'],1)
            self.assertEqual(after,report['points'][int(event['time_h']*10)])

    def test_conservation_and_positive_states_hold_before_and_after_events(self):
        report = transit_regimen_demo()
        states = report['points']+[e[k] for e in report['event_boundaries'] for k in ('before','after')]
        for p in states:
            amounts=p['transit_amounts_mg']+[p['central_amount_mg'],p['eliminated_amount_mg']]
            self.assertTrue(all(math.isfinite(v) and v >= 0 for v in amounts))
            self.assertAlmostEqual(math.fsum(amounts),p['cumulative_administered_mg'],delta=1e-12)
        self.assertEqual(report['total_administered_mg'],3)
        # Before the second event the repeated response is exactly the single response.
        for repeat,single in zip(report['points'][:80],report['single_dose_reference_points'][:80]):
            self.assertEqual(repeat['concentration_ng_ml'],single['concentration_ng_ml'])
        self.assertGreater(report['points'][-1]['concentration_ng_ml'],report['single_dose_reference_points'][-1]['concentration_ng_ml'])

    def test_report_integrity_and_no_patient_catalog_database_or_network(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('sqlalchemy.engine.Engine.connect',side_effect=AssertionError('DB')), \
             patch('intelligence_store.patient_state_revisions.read_revision',side_effect=AssertionError('Patient')), \
             patch('intelligence_store.pk_parameter_reference.load_parameter_extract',side_effect=AssertionError('Catalog')):
            report=transit_regimen_demo()
            self.assertEqual(report,transit_regimen_demo())
        data=dict(report);sha=data.pop('report_sha256');self.assertEqual(sha,digest(data))
        self.assertFalse(report['ready_for_patient_simulation'])
        self.assertIsNone(report['drug']);self.assertIsNone(report['patient_revision_id'])

    def test_cli_json_text_and_non_overwriting_export_without_database(self):
        app=Flask(__name__);register_transit_regimen_commands(app);runner=app.test_cli_runner()
        text=runner.invoke(args=['transit-regimen-demo']);self.assertEqual(text.exit_code,0)
        self.assertIn('Invented parameters',text.output)
        result=runner.invoke(args=['transit-regimen-demo','--json']);self.assertEqual(result.exit_code,0)
        self.assertEqual(json.loads(result.stdout),transit_regimen_demo())
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'example.json'
            self.assertEqual(runner.invoke(args=['transit-regimen-demo','--output',str(p)]).exit_code,0)
            saved=p.read_bytes()
            self.assertNotEqual(runner.invoke(args=['transit-regimen-demo','--output',str(p)]).exit_code,0)
            self.assertEqual(p.read_bytes(),saved)
        self.assertNotEqual(runner.invoke(args=['transit-regimen-demo','--dose','25']).exit_code,0)


if __name__=='__main__':unittest.main()
