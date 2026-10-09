"""Review-bound educational input copies and immutable source provenance."""
import copy
import json
import unittest
from html.parser import HTMLParser
from unittest.mock import patch
from sqlalchemy import select, update
from werkzeug.datastructures import MultiDict
import test_educational_pk_comparison as fixtures
from intelligence_store.extensions import db
from intelligence_store.educational_pk_runs import EducationalPKRun, export_pk_run, read_pk_run, save_pk_run
from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.pk_model_inputs import model_input_example
from intelligence_store.treatment_requests import treatment_request_example
from intelligence_store.educational_pk_comparison import compare_pk_runs


class FormFields(HTMLParser):
    def __init__(self,text):
        super().__init__();self.values={};self.feed(text)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='input' and attrs.get('type')=='hidden':
            self.values[attrs['name']]=attrs.get('value','')


class PKRunVariationTests(unittest.TestCase):
    setUp=fixtures.EducationalPKComparisonTests.setUp
    tearDown=fixtures.EducationalPKComparisonTests.tearDown
    save_scenario=fixtures.EducationalPKComparisonTests.save_scenario
    baseline=fixtures.EducationalPKComparisonTests.baseline
    save=fixtures.EducationalPKComparisonTests.save
    pair=fixtures.EducationalPKComparisonTests.pair

    def url(self,row):
        return f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs/{row.id}/variation'

    def start(self):
        self.baseline();row=self.save('Source archive')
        response=self.client.get(self.url(row));self.assertEqual(response.status_code,200)
        form=FormFields(response.get_data(as_text=True)).values
        form.update(ffm='55',crcl='45',note='Invented single CrCl comparison',title='Reviewed variation')
        return row,form

    def post(self,row,form,action):
        return self.client.post(self.url(row),data=dict(form,action=action))

    def refresh(self,form,response):
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        form.update(FormFields(response.get_data(as_text=True)).values)

    def tables(self):
        return {t.name:sorted(repr(dict(r)) for r in db.session.execute(select(t)).mappings())
                for t in db.metadata.sorted_tables}

    def test_review_calculate_save_preserve_source_and_record_copy_lineage(self):
        row,form=self.start();source=export_pk_run(row.id);before=self.tables()
        with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver during review')):
            response=self.post(row,form,'review');self.refresh(form,response)
        self.assertIn('One declared covariate value changed',response.get_data(as_text=True))
        self.assertEqual(before,self.tables())
        response=self.post(row,form,'calculate');self.refresh(form,response)
        self.assertIn('Educational calculation completed',response.get_data(as_text=True))
        self.assertEqual(before,self.tables())
        result=self.post(row,form,'save');self.assertEqual(result.status_code,303)
        self.assertIn(f'left={row.id}',result.headers['Location'])
        new=db.session.scalar(select(EducationalPKRun).where(EducationalPKRun.id!=row.id))
        self.assertIsNotNone(new)
        review=new.payload['report']['preflight_review'];original=source['payload']['report']['preflight_review'] if 'payload' in source else row.payload['report']['preflight_review']
        self.assertEqual(review['explicit_model_inputs']['fields']['fat_free_mass'],original['explicit_model_inputs']['fields']['fat_free_mass'])
        field=review['explicit_model_inputs']['fields']['creatinine_clearance']
        self.assertEqual(field['value'],45);self.assertEqual(field['method'],'direct_synthetic_covariate')
        anchor=json.loads(field['source_ref']);self.assertEqual(anchor['source_run_id'],row.id)
        self.assertEqual(anchor['source_payload_sha256'],row.payload_sha256)
        request=review['treatment_request_preview']['request'];old=original['treatment_request_preview']['request']
        self.assertEqual({k:v for k,v in request.items() if k!='source_ref'},{k:v for k,v in old.items() if k!='source_ref'})
        self.assertEqual(json.loads(request['source_ref']),anchor)
        self.assertEqual(export_pk_run(row.id),source)
        self.assertEqual(compare_pk_runs(row.id,new.id,revision_id=self.revision.id)['status'],'compatible_educational_comparison')
        # Retried explicit save resolves to the existing immutable archive.
        self.assertEqual(self.post(row,form,'save').status_code,303)
        self.assertEqual(db.session.query(EducationalPKRun).count(),2)

    def test_unreviewed_edits_and_save_before_calculation_are_rejected_without_solver(self):
        row,form=self.start()
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No unapproved execution')):
            self.assertEqual(self.post(row,form,'calculate').status_code,403)
            self.refresh(form,self.post(row,form,'review'))
            self.assertEqual(self.post(row,form,'save').status_code,403)
            for key,value in [('crcl','50'),('title','Different title'),('note','Different rationale')]:
                edited=dict(form);edited[key]=value
                self.assertEqual(self.post(row,edited,'calculate').status_code,403)
        self.assertEqual(db.session.query(EducationalPKRun).count(),1)

    def test_invalid_values_csrf_query_and_duplicate_fields_are_rejected(self):
        row,form=self.start()
        for value in ('NaN','Infinity','0','-2','x'):
            invalid=dict(form,crcl=value)
            self.assertEqual(self.post(row,invalid,'review').status_code,400)
        self.assertEqual(self.post(row,dict(form,note=''),'review').status_code,400)
        self.assertEqual(self.post(row,dict(form,form_token='wrong'),'review').status_code,403)
        self.refresh(form,self.post(row,form,'review'))
        # Review approvals cannot substitute for a workspace CSRF token.
        self.assertEqual(self.post(row,dict(form,form_token=form['review_token']),'review').status_code,403)
        self.assertEqual(self.client.get(self.url(row)+'?copy=1').status_code,400)
        duplicate=MultiDict(dict(form,action='review'));duplicate.add('crcl','50')
        self.assertEqual(self.client.post(self.url(row),data=duplicate).status_code,400)
        self.assertEqual(self.client.post(self.url(row),data='x'*16001,content_type='application/x-www-form-urlencoded').status_code,413)

    def test_wrong_revision_and_source_audit_or_contract_failure_are_blocked(self):
        row,form=self.start()
        newrev=save_revision(self.scenario.id,self.base,parent_revision_id=self.revision.id,title='Other revision')
        wrong=self.url(row).replace(f'/revisions/{self.revision.id}/',f'/revisions/{newrev.id}/')
        self.assertEqual(self.client.get(wrong).status_code,404)
        with patch('landscape_ui.educational_pk_variation_pages.audit_pk_run',return_value={'status':'mathematical_check_failed'}):
            self.assertEqual(self.client.get(self.url(row)).status_code,409)
        with patch('landscape_ui.educational_pk_variation_pages.CONTRACT_SHA256','0'*64):
            self.assertEqual(self.client.get(self.url(row)).status_code,409)

    def test_blocked_calculation_never_offers_save_or_creates_run(self):
        row,form=self.start();form['crcl']='1000000'
        self.refresh(form,self.post(row,form,'review'))
        with patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No out-of-scope solver')):
            response=self.post(row,form,'calculate');self.refresh(form,response)
            text=response.get_data(as_text=True);self.assertIn('Calculation blocked',text)
            self.assertNotIn('value="save"',text)
            self.assertEqual(self.post(row,form,'save').status_code,403)
        self.assertEqual(db.session.query(EducationalPKRun).count(),1)

    def test_changed_recorded_covariate_becomes_direct_synthetic_and_metadata_is_escaped(self):
        self.baseline();inputs=model_input_example()
        inputs['fields']['creatinine_clearance']['method']='cockcroft_gault_recorded'
        row=save_pk_run(self.revision.id,inputs,treatment_request_example(),'MM',title='<script>source</script>')
        response=self.client.get(self.url(row));self.assertEqual(response.status_code,200)
        self.assertNotIn('<script>source</script>',response.get_data(as_text=True))
        form=FormFields(response.get_data(as_text=True)).values
        form.update(ffm='50',crcl='45',title='Multi covariate',note='<script>note</script>')
        response=self.post(row,form,'review');self.refresh(form,response)
        text=response.get_data(as_text=True)
        self.assertIn('Multiple declared covariate values changed',text)
        self.assertNotIn('<script>note</script>',text)
        self.assertIn('direct_synthetic_covariate',text)
        self.assertEqual(read_pk_run(row.id).payload['report']['preflight_review']['explicit_model_inputs']['fields']['creatinine_clearance']['method'],'cockcroft_gault_recorded')

    def test_expired_or_cross_source_approval_is_rejected(self):
        row,form=self.start();self.refresh(form,self.post(row,form,'review'))
        other=self.save('Other source')
        self.assertEqual(self.post(other,form,'calculate').status_code,403)
        from itsdangerous import SignatureExpired
        # The browser token validator remains intact; only the review-approval load expires.
        with patch('landscape_ui.educational_pk_variation_pages._approval_signer') as signer:
            signer.return_value.loads.side_effect=SignatureExpired('expired')
            self.assertEqual(self.post(row,form,'calculate').status_code,403)

    def test_changed_calculation_result_cannot_be_saved(self):
        row,form=self.start();self.refresh(form,self.post(row,form,'review'))
        self.refresh(form,self.post(row,form,'calculate'))
        from landscape_ui.educational_pk_variation_pages import _proposal
        from intelligence_store.educational_pk import calculate_educational_pk
        proposal=_proposal(row,form)
        changed=calculate_educational_pk(self.revision.id,proposal['inputs'],proposal['treatment'],proposal['disease'])
        changed['report_sha256']='0'*64
        with patch('landscape_ui.educational_pk_variation_pages.calculate_educational_pk',return_value=changed):
            response=self.post(row,form,'save')
        self.assertEqual(response.status_code,400)
        self.assertIn('no new run was saved',response.get_data(as_text=True))
        self.assertEqual(db.session.query(EducationalPKRun).count(),1)


if __name__=='__main__':unittest.main()
