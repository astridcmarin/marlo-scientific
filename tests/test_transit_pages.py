"""Read-only visualization contract for the fixed generic example."""
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from flask import Flask
from landscape_ui import register_landscape
from intelligence_store.transit_kernel import transit_demo


class TransitPageTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.add_url_rule('/', 'home', lambda: 'Home')
        register_landscape(self.app)
        self.client = self.app.test_client()
        self.path = '/landscape/patient-lab/transit-demo'

    def test_html_scope_values_and_one_active_navigation_item(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        for phrase in ('Invented parameters', 'No patient or drug model', 'not organs',
                       '491.963', '500.000', '241 time points', 'Patient simulation remains unavailable'):
            self.assertIn(phrase, body)
        self.assertEqual(body.count('aria-current="page"'), 1)
        self.assertIn('class="nav-item active" href="/landscape/simulation-lab"', body)
        self.assertNotIn('<script', body)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_json_exactly_matches_kernel_and_is_downloadable(self):
        response = self.client.get(self.path+'?format=json')
        self.assertEqual(response.json, transit_demo())
        self.assertIsNone(response.json['drug'])
        self.assertIsNone(response.json['patient_revision_id'])
        self.assertFalse(response.json['ready_for_patient_simulation'])
        self.assertEqual(response.mimetype, 'application/json')
        self.assertIn('generic-transit-demo.json', response.headers['Content-Disposition'])
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')

    def test_cohort_is_navigation_context_only(self):
        first = self.client.get(self.path+'?format=json').data
        self.assertEqual(first, self.client.get(self.path+'?format=json&cohort_id=4').data)
        body = self.client.get(self.path+'?cohort_id=4').get_data(as_text=True)
        self.assertIn('/landscape/patient-lab?cohort_id=4', body)
        self.assertIn('cohort_id=4', body)

    def test_patient_drug_solver_overrides_and_invalid_queries_rejected(self):
        for query in ('dose=25','drug=lenalidomide','revision_id=1','stages=7',
                      'format=csv','format=json&format=html','cohort_id=0',
                      'cohort_id=-1','cohort_id=abc','cohort_id=4&cohort_id=5',
                      'cohort_id='+('9'*1000),'cohort_id=%3Cscript%3E'):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(self.path+'?'+query).status_code, 400)
        self.assertEqual(self.client.post(self.path).status_code, 405)

    def test_svg_series_share_exact_report_grid_and_are_accessible(self):
        body = self.client.get(self.path).get_data(as_text=True)
        svgs = []
        for part in body.split('<svg ')[1:]:
            svgs.append(ET.fromstring('<svg '+part.split('</svg>')[0]+'</svg>'))
        self.assertEqual(len(svgs), 3)
        self.assertEqual([len(svg.findall('polyline')) for svg in svgs], [1, 5, 1])
        for svg in svgs:
            self.assertEqual(svg.attrib['role'], 'img')
            self.assertIsNotNone(svg.find('title'))
            self.assertIsNotNone(svg.find('desc'))
            for line in svg.findall('polyline'):
                coords = [tuple(map(float,p.split(','))) for p in line.attrib['points'].split()]
                self.assertEqual(len(coords), 241)
                self.assertEqual(coords[0][0], 70)
                self.assertEqual(coords[-1][0], 740)
                self.assertTrue(all(70 <= x <= 740 and 30 <= y <= 250 for x,y in coords))
        first_line = svgs[0].find('polyline').attrib['points'].split()
        points = transit_demo()['points']; scale = max(p['concentration_ng_ml'] for p in points)*1.1
        for coordinate, point in zip(first_line, points):
            x,y = map(float,coordinate.split(','))
            self.assertAlmostEqual(y,250-220*point['concentration_ng_ml']/scale,delta=.00051)
        self.assertIn('<caption>', body)
        self.assertIn('scope="col"', body)

    def test_html_and_json_need_no_database_catalog_patient_or_network(self):
        with patch('sqlalchemy.engine.Engine.connect',side_effect=AssertionError('DB read')), \
             patch('requests.get',side_effect=AssertionError('Network read')), \
             patch('intelligence_store.patient_state_revisions.read_revision',side_effect=AssertionError('Patient read')), \
             patch('intelligence_store.pk_parameter_reference.load_parameter_extract',side_effect=AssertionError('Catalog read')):
            self.assertEqual(self.client.get(self.path).status_code, 200)
            self.assertEqual(self.client.get(self.path+'?format=json').status_code, 200)


if __name__ == '__main__':
    unittest.main()
