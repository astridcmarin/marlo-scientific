import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from flask import Flask
from landscape_ui import register_landscape
from intelligence_store.transit_regimen import transit_regimen_demo


class TransitRegimenPageTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__);app.config['TESTING']=True
        app.add_url_rule('/','home',lambda:'Home');register_landscape(app)
        self.client=app.test_client();self.path='/landscape/patient-lab/transit-regimen-demo'

    def test_page_scope_navigation_and_json_report_identity(self):
        r=self.client.get(self.path+'?cohort_id=4');self.assertEqual(r.status_code,200)
        body=r.get_data(as_text=True)
        for text in ('Repeated additions','Invented example','not organs','not a treatment recommendation','Superposition requires linear time-invariant equations'):
            self.assertIn(text,body)
        self.assertEqual(body.count('aria-current="page"'),1)
        self.assertIn('/landscape/patient-lab/transit-demo?cohort_id=4',body)
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        report=self.client.get(self.path+'?format=json')
        self.assertEqual(report.json,transit_regimen_demo())
        self.assertEqual(report.data,self.client.get(self.path+'?format=json&cohort_id=4').data)
        self.assertIn('generic-transit-regimen-demo.json',report.headers['Content-Disposition'])
        self.assertNotIn('<script',body)

    def test_override_inputs_duplicate_queries_and_post_are_rejected(self):
        for q in ('dose=25','drug=lenalidomide','revision_id=1','interval=8','format=csv',
                  'format=json&format=html','cohort_id=0','cohort_id=x','cohort_id=4&cohort_id=5'):
            self.assertEqual(self.client.get(self.path+'?'+q).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)

    def test_amount_plot_contains_vertical_event_jumps_without_interpolated_ramps(self):
        body=self.client.get(self.path).get_data(as_text=True)
        svgs=[ET.fromstring('<svg '+part.split('</svg>')[0]+'</svg>') for part in body.split('<svg ')[1:]]
        self.assertEqual([len(s.findall('polyline')) for s in svgs],[2,4,2])
        for svg in svgs:
            self.assertIsNotNone(svg.find('title'));self.assertIsNotNone(svg.find('desc'))
        # Cumulative administered line has 241 grid points + 3 before-event points.
        coords=[tuple(map(float,v.split(','))) for v in svgs[1].findall('polyline')[3].attrib['points'].split()]
        self.assertEqual(len(coords),244)
        vertical=[(a,b) for a,b in zip(coords,coords[1:]) if a[0]==b[0] and a[1]!=b[1]]
        self.assertEqual(len(vertical),3)
        self.assertEqual([a[0] for a,b in vertical],[70.0,293.333,516.667])
        self.assertIn('<caption>',body);self.assertIn('scope="col"',body)

    def test_reads_no_patient_database_or_network(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network')), \
             patch('sqlalchemy.engine.Engine.connect',side_effect=AssertionError('DB')), \
             patch('intelligence_store.patient_state_revisions.read_revision',side_effect=AssertionError('Patient')):
            self.assertEqual(self.client.get(self.path).status_code,200)
            self.assertEqual(self.client.get(self.path+'?format=json').status_code,200)


if __name__=='__main__':unittest.main()
