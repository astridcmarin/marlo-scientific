import unittest
from datetime import datetime
from unittest.mock import patch
from flask import Flask
from sqlalchemy.exc import OperationalError
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from landscape_ui import register_landscape


class DiseaseLibraryTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.config.update(TESTING=True,SQLALCHEMY_DATABASE_URI='sqlite://')
        self.app.add_url_rule('/','home',lambda:'Home')
        register_landscape(self.app)
        db.init_app(self.app)
        self.context=self.app.app_context();self.context.push()
        db.create_all()
        self.client=self.app.test_client()
        self.path='/landscape/diseases'

    def tearDown(self):
        db.session.remove();db.drop_all();self.context.pop()

    def cohort(self,identifier,condition='Multiple Myeloma',status='COMPLETE',expected=1,recorded=1,member=True):
        c=AnalysisCohort(id=identifier,condition=condition,api_url='https://clinicaltrials.gov/api/v2/studies',
             query_params={'query.cond':condition},query_version='test-v1',normalization_version='test-v1',
             scope='all-studies',max_pages=1,status=status,expected_count=expected,retrieved_count=recorded,
             pages_fetched=1,page_log=[],finished_at_utc=datetime(2026,10,7))
        db.session.add(c)
        if member:
            nct=f'NCT{identifier:08d}'
            s=TrialSnapshot(nct_id=nct,source_url='https://clinicaltrials.gov/study/'+nct,raw_study={})
            db.session.add(s);db.session.flush()
            db.session.add(CohortTrial(cohort_id=identifier,nct_id=nct,snapshot_id=s.id))
        db.session.commit()

    def test_complete_runs_remain_distinct_and_links_preserve_cohort(self):
        self.cohort(1);self.cohort(2)
        with patch('requests.get',side_effect=AssertionError('No network')):
            response=self.client.get(self.path)
        body=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200)
        self.assertIn('2 matching saved query runs',body)
        for identifier in (1,2):
            self.assertIn('/landscape/drugs?cohort_id='+str(identifier),body)
            self.assertIn('/landscape/patient-lab/workspace?cohort_id='+str(identifier),body)
        self.assertEqual(body.count('class="nav-item active"'),1)
        self.assertIn('aria-current="page"><span aria-hidden="true">▤</span> Disease library',body)
        self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_partial_and_inconsistent_counts_withhold_analysis_links(self):
        self.cohort(1,status='PARTIAL');self.cohort(2,expected=2);self.cohort(3,member=False)
        data=self.client.get(self.path+'?status=ALL&format=json').json
        self.assertTrue(all(not row['open_analysis'] for row in data['entries']))
        self.assertFalse(data['entries'][0]['record_counts_consistent'])
        self.assertEqual(data['entries'][0]['membership_count'],0)
        body=self.client.get(self.path+'?status=ALL').get_data(as_text=True)
        self.assertNotIn('Open trial landscape</a>',body)
        self.assertIn('Analysis links withheld',body)
        self.assertEqual(self.client.get(self.path+'?format=json').json['matching_cohort_runs'],2)

    def test_search_is_literal_and_query_is_escaped(self):
        self.cohort(1,condition='100% example');self.cohort(2,condition='Other');self.cohort(3,condition='<script>x</script>')
        data=self.client.get(self.path,query_string={'q':'%','format':'json'}).json
        self.assertEqual([r['cohort_id'] for r in data['entries']],[1])
        body=self.client.get(self.path,query_string={'q':'<script>'}).get_data(as_text=True)
        self.assertNotIn('<script>x</script>',body)
        self.assertIn('&lt;script&gt;',body)

    def test_pagination_and_export_are_page_scoped(self):
        for identifier in range(1,22):self.cohort(identifier)
        first=self.client.get(self.path+'?format=json').json
        second=self.client.get(self.path+'?page=2&format=json').json
        self.assertEqual(len(first['entries']),20)
        self.assertEqual([r['cohort_id'] for r in second['entries']],[1])
        self.assertEqual(first['matching_cohort_runs'],21)
        self.assertEqual(first['entries'][0]['finished_at_utc'],'2026-10-07T00:00:00Z')
        self.assertEqual(self.client.get(self.path+'?page=3').status_code,404)

    def test_empty_state_and_strict_requests(self):
        self.assertIn('No matching saved cohorts',self.client.get(self.path).get_data(as_text=True))
        for query in ('page=0','page=-1','page=1.5','page=1000000','status=complete','format=csv','q=a&q=b','patient_id=1','q='+'a'*121):
            self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)
        self.assertEqual(self.client.post(self.path).status_code,405)

    def test_storage_error_is_actionable(self):
        with patch.object(db.session,'scalar',side_effect=OperationalError('query',{},Exception('db'))):
            response=self.client.get(self.path)
        self.assertEqual(response.status_code,503)
        self.assertIn('local storage installation',response.get_data(as_text=True))


if __name__=='__main__':unittest.main()
