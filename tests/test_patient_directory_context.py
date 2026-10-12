import unittest
from unittest.mock import patch
from flask import Flask
from sqlalchemy import update
from intelligence_store.extensions import db
from intelligence_store.saved_scenarios import SavedPatientScenario, SCHEMA_VERSION
from intelligence_store.patient_state import digest
from landscape_ui import register_landscape


class ResearchContextTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__)
        app.config.update(TESTING=True,SQLALCHEMY_DATABASE_URI='sqlite://')
        app.add_url_rule('/','home',lambda:'Home')
        register_landscape(app);db.init_app(app)
        self.context=app.app_context();self.context.push();db.create_all()
        self.client=app.test_client();self.path='/landscape/patient-lab/workspace'

    def tearDown(self):
        db.session.remove();db.drop_all();self.context.pop()

    def saved(self,identifier,cohort,drug,title=None):
        title=title or f'Study workspace {identifier}'
        payload={'schema_version':SCHEMA_VERSION,'title':title,'inputs':{'cohort_id':cohort},
                 'analysis':{'report':{'selected_drug':{'entity_id':drug,'label':drug.title()},
                                      'cohort':{'id':cohort,'condition':'Frozen condition'}}}}
        row=SavedPatientScenario(id=identifier,title=title,schema_version=SCHEMA_VERSION,
                                payload=payload,payload_sha256=digest(payload),save_key=f'{identifier:064x}')
        db.session.add(row);db.session.commit()
        return row

    def test_cohort_and_drug_intersect_instead_of_showing_other_work(self):
        self.saved(1,4,'lenalidomide');self.saved(2,5,'lenalidomide');self.saved(3,4,'bortezomib')
        body=self.client.get(self.path+'?cohort_id=4&drug=lenalidomide').get_data(as_text=True)
        self.assertIn('Study workspace 1',body)
        self.assertNotIn('Study workspace 2',body);self.assertNotIn('Study workspace 3',body)
        self.assertIn('1 saved scenario rows',body)
        self.assertIn('Source cohort #4',body)
        self.assertIn('name="drug" value="lenalidomide"',body)

    def test_drug_filter_uses_frozen_identity_without_current_catalog(self):
        self.saved(1,4,'retired-reference-drug')
        with patch('intelligence_store.drug_aliases.load_alias_catalog',side_effect=ValueError('catalog offline')):
            page=self.client.get(self.path+'?drug=retired-reference-drug')
        self.assertEqual(page.status_code,200)
        self.assertIn('Study workspace 1',page.get_data(as_text=True))

    def test_filter_pagination_and_title_search_preserve_context(self):
        for identifier in range(1,12):self.saved(identifier,4,'lenalidomide','Match '+str(identifier))
        self.saved(12,5,'lenalidomide','Match unrelated')
        body=self.client.get(self.path+'?cohort_id=4&drug=lenalidomide&q=Match').get_data(as_text=True)
        self.assertIn('11 saved scenario rows',body)
        self.assertIn('cohort_id=4&amp;drug=lenalidomide&amp;page=2',body)
        second=self.client.get(self.path+'?cohort_id=4&drug=lenalidomide&q=Match&page=2').get_data(as_text=True)
        self.assertIn('Match 1</h2>',second);self.assertNotIn('Match unrelated',second)

    def test_corrupted_matching_payload_still_withholds_details(self):
        self.saved(1,4,'lenalidomide')
        db.session.execute(update(SavedPatientScenario).where(SavedPatientScenario.id==1).values(title='Broken'))
        db.session.commit();db.session.expire_all()
        body=self.client.get(self.path+'?drug=lenalidomide').get_data(as_text=True)
        self.assertIn('Details unavailable',body)
        self.assertNotIn('Create baseline patient state',body)

    def test_empty_context_and_invalid_requests(self):
        self.saved(1,4,'lenalidomide')
        body=self.client.get(self.path+'?cohort_id=99').get_data(as_text=True)
        self.assertIn('No matching saved scenarios',body)
        self.assertNotIn('Study workspace 1',body)
        for query in ('drug=','drug=Lenalidomide','drug=a&drug=b','drug=../x','drug='+'a'*101):
            self.assertEqual(self.client.get(self.path+'?'+query).status_code,400)

    def test_library_links_bind_drug_identity(self):
        body=self.client.get('/landscape/patient-lab/model-library').get_data(as_text=True)
        for drug in ('lenalidomide','bortezomib','dexamethasone'):
            self.assertIn('/landscape/patient-lab/workspace?drug='+drug,body)


if __name__=='__main__':unittest.main()
