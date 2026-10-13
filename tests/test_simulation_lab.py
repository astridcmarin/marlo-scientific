"""Combined navigation and export smoke checks, with no configured database."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from flask import Flask, url_for
from landscape_ui import register_landscape
from landscape_ui.simulation_lab_pages import GROUPS


class SimulationLabTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__);self.app.config['TESTING']=True
        self.app.add_url_rule('/','home',lambda:'Home');register_landscape(self.app)
        self.client=self.app.test_client()

    def test_hub_does_not_run_models_or_access_storage(self):
        targets=[
            'landscape_ui.transit_pages.transit_demo',
            'landscape_ui.transit_regimen_pages.transit_regimen_demo',
            'landscape_ui.binding_pulse_pages.calculate_binding_schedule',
            'landscape_ui.protein_turnover_pages.turnover_example',
            'landscape_ui.protein_turnover_experiment_pages.compare_turnover_mechanisms',
            'landscape_ui.binding_turnover_pages.calculate_binding_turnover',
            'landscape_ui.site_exposure_response_pages.calculate_site_response',
            'requests.get',
        ]
        with ExitStack() as stack:
            for target in targets:stack.enter_context(patch(target,side_effect=AssertionError('Hub must not calculate or fetch')))
            page=self.client.get('/landscape/simulation-lab')
        self.assertEqual(page.status_code,200)
        text=page.get_data(as_text=True)
        self.assertEqual(text.count('class="nav-item active"'),1)
        self.assertIn('aria-current="page"><span aria-hidden="true">◌</span> Simulation Lab',text)
        self.assertIn('Hypothetical educational models',text)
        self.assertIn('Clinical prediction validated: <strong>false</strong>',text)
        self.assertEqual(sum(len(g['experiments']) for g in GROUPS),9)
        self.assertEqual(page.headers['Cache-Control'],'no-store')

    def test_every_experiment_renders_exports_and_returns_to_hub(self):
        for group in GROUPS:
            for experiment in group['experiments']:
                with self.subTest(experiment=experiment['endpoint']):
                    with self.app.test_request_context():path=url_for('landscape.'+experiment['endpoint'])
                    page=self.client.get(path)
                    self.assertEqual(page.status_code,200)
                    text=page.get_data(as_text=True)
                    self.assertIn('All Simulation Lab experiments',text)
                    self.assertEqual(text.count('class="nav-item active"'),1)
                    self.assertIn('aria-current="page"><span aria-hidden="true">◌</span> Simulation Lab',text)
                    exported=self.client.get(path,query_string={'format':'json'})
                    self.assertEqual(exported.status_code,200)
                    self.assertEqual(exported.mimetype,'application/json')
                    flags=[]
                    def check_flags(value):
                        if isinstance(value,dict):
                            for key,item in value.items():
                                if key in ('clinical_prediction_validated','ready_for_patient_simulation'):
                                    self.assertIs(item,False);flags.append(key)
                                check_flags(item)
                        elif isinstance(value,list):
                            for item in value:check_flags(item)
                    check_flags(exported.json)
                    self.assertTrue(flags)

    def test_hub_rejects_patient_parameters_and_mutating_requests(self):
        for query in ['patient_id=1','pk_run_id=1','cohort_id=4','format=json','q=x']:
            self.assertEqual(self.client.get('/landscape/simulation-lab?'+query).status_code,400)
        self.assertEqual(self.client.post('/landscape/simulation-lab').status_code,405)


if __name__=='__main__':unittest.main()
