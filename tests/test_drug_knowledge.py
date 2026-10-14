"""Unified references preserve name-count scope and missing knowledge."""
import copy
import unittest
from unittest.mock import patch
import test_saved_scenarios as fixtures
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort,CohortTrial,TrialSnapshot
from intelligence_store.summaries import summarize_cohort
from intelligence_store.drug_knowledge import build_drug_knowledge
from intelligence_store.regulatory import digest

class DrugKnowledgeTests(unittest.TestCase):
    setUp=fixtures.SavedScenarioTests.setUp
    tearDown=fixtures.SavedScenarioTests.tearDown

    def extra(self,nct,names,member=True):
        raw={'protocolSection':{'identificationModule':{'nctId':nct,'briefTitle':'Invented study'},
            'statusModule':{'overallStatus':'RECRUITING'},'designModule':{'studyType':'INTERVENTIONAL'},
            'armsInterventionsModule':{'interventions':[{'type':'DRUG','name':name} for name in names]}}}
        s=TrialSnapshot(nct_id=nct,source_url='https://clinicaltrials.gov/study/'+nct,raw_study=raw)
        db.session.add(s);db.session.flush()
        if member:db.session.add(CohortTrial(cohort_id=1,nct_id=nct,snapshot_id=s.id))
        return s

    def test_alias_union_and_overlapping_unmapped_coverage(self):
        self.extra('NCT00000002',['Revlimid','Lenalidomide','Unknown compound'])
        self.extra('NCT00000003',['Unknown compound'])
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=3;db.session.commit()
        r=build_drug_knowledge(summarize_cohort(1));e=next(e for e in r['entries'] if e['entity_id']=='lenalidomide')
        self.assertEqual(e['count'],2);self.assertEqual(e['recruiting_count'],2)
        self.assertEqual(r['coverage']['mapped_names']['nct_ids'],['NCT00000001','NCT00000002'])
        self.assertEqual(r['coverage']['no_mapped_names']['nct_ids'],['NCT00000003'])
        self.assertEqual(r['coverage']['unmapped_names']['nct_ids'],['NCT00000002','NCT00000003'])
        self.assertEqual(r['coverage']['unmapped_group_count'],1)
        self.assertEqual(len(e['evidence']),2)

    def test_zero_match_entities_keep_reference_context_and_newer_snapshot_is_not_used(self):
        self.extra('NCT00000001',['Bortezomib'],member=False);db.session.commit()
        r=build_drug_knowledge(summarize_cohort(1));e=next(e for e in r['entries'] if e['entity_id']=='bortezomib')
        self.assertEqual(len(r['entries']),9)
        self.assertEqual(e['count'],0);self.assertEqual(e['nct_ids'],[])
        self.assertIsNotNone(e['safety']);self.assertIsNotNone(e['annotation'])
        matched=next(e for e in r['entries'] if e['entity_id']=='lenalidomide')
        self.assertEqual(matched['evidence']['NCT00000001']['snapshot_id'],self.snapshot_id)

    def test_digest_reproducibility_and_summary_copy_isolation(self):
        summary=summarize_cohort(1);original=copy.deepcopy(summary)
        r=build_drug_knowledge(summary);again=build_drug_knowledge(summary)
        self.assertEqual(r,again);body=copy.deepcopy(r);sha=body.pop('report_sha256');self.assertEqual(sha,digest(body))
        r['cohort']['condition']='Changed copy';r['entries'][0]['source']['note']='Changed copy'
        self.assertEqual(summary,original)

    def test_catalog_failure_blocks_combined_view(self):
        with patch('intelligence_store.drug_knowledge.load_safety_catalog',side_effect=ValueError('Incompatible safety catalog')):
            with self.assertRaisesRegex(ValueError,'Incompatible'):build_drug_knowledge(summarize_cohort(1))

    def test_dexamethasone_aliases_union_without_inferred_formulations(self):
        self.extra('NCT00000002',['dexamethasone','Hemady','Dexamethasone sodium phosphate'])
        self.extra('NCT00000003',['HEMADY'])
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=3;db.session.commit()
        r=build_drug_knowledge(summarize_cohort(1))
        e=next(e for e in r['entries'] if e['entity_id']=='dexamethasone')
        self.assertEqual(e['nct_ids'],['NCT00000002','NCT00000003'])
        self.assertEqual(e['count'],2)
        self.assertEqual(r['coverage']['unmapped_names']['nct_ids'],['NCT00000002'])
        self.assertIsNone(e['annotation']['fields']['target'])
        self.assertIn('unknown',e['annotation']['fields']['mechanism']['label'])
        self.assertEqual(e['source']['label_version'],6)
        self.assertEqual(e['source']['retrieved_xml_sha256'],'46f06c72fba8040cffebbe7c52bcd1865b9d5cefb705eb2b7b46aeffe9d905b4')
        self.assertTrue(all(rule['kind']=='class_reference' and rule['partner_name'] is None
                            for rule in e['interactions']['references']))

    def test_new_patient_reference_does_not_enable_pk_or_infer_class_partners(self):
        from intelligence_store.patient_scenarios import summarize_scenario
        from intelligence_store.pharmacokinetics import pk_availability,simulate_pk,PKValidationError
        profile=copy.deepcopy(self.profile)
        profile.update(selected_drug='dexamethasone',medications=['Itraconazole'],dose_value=20,dose_unit='mg')
        report=summarize_scenario(summarize_cohort(1),profile)
        self.assertEqual(report['selected_drug']['entity_id'],'dexamethasone')
        self.assertEqual(report['medications'][0]['status'],'unassessed')
        self.assertNotEqual(pk_availability(profile)['status'],'available')
        with self.assertRaises(PKValidationError):simulate_pk('dexamethasone',20)

    def test_cyclophosphamide_case_variants_union_but_brands_and_products_stay_unmapped(self):
        self.extra('NCT00000002',['Cyclophosphamide','cyclophosphamide','Cytoxan'])
        self.extra('NCT00000003',['CYCLOPHOSPHAMIDE','Cyclophosphamide monohydrate'])
        self.extra('NCT00000003',['Lenalidomide'],member=False)
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=3;db.session.commit()
        r=build_drug_knowledge(summarize_cohort(1))
        e=next(e for e in r['entries'] if e['entity_id']=='cyclophosphamide')
        self.assertEqual(e['nct_ids'],['NCT00000002','NCT00000003'])
        self.assertEqual(e['count'],2)
        self.assertEqual(r['coverage']['mapped_names']['count'],3)
        self.assertEqual(r['coverage']['unmapped_names']['nct_ids'],['NCT00000002','NCT00000003'])
        self.assertEqual(r['coverage']['unmapped_group_count'],2)
        self.assertEqual(e['curated_aliases'],['Cyclophosphamide'])
        self.assertIn('proposed',e['annotation']['fields']['target']['label'])
        self.assertIn('incompletely',e['annotation']['fields']['mechanism']['label'])
        self.assertEqual(e['source']['label_version'],5)
        self.assertEqual(e['source']['retrieved_xml_sha256'],'12b64be6a34da9a305f803f0541edc2469359f7b4795567b64366f21cc7465b6')

    def test_cyclophosphamide_reference_stays_class_scoped_and_has_no_pk_model(self):
        from intelligence_store.patient_scenarios import summarize_scenario
        from intelligence_store.pharmacokinetics import pk_availability,simulate_pk,PKValidationError
        self.extra('NCT00000002',['Cyclophosphamide','Doxorubicin'])
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=2;db.session.commit()
        summary=summarize_cohort(1)
        e=next(e for e in build_drug_knowledge(summary)['entries'] if e['entity_id']=='cyclophosphamide')
        self.assertTrue(all(rule['kind']=='class_reference' and rule['pair_count'] is None
                            and rule['pair_nct_ids'] is None for rule in e['interactions']['references']))
        profile=copy.deepcopy(self.profile)
        profile.update(selected_drug='cyclophosphamide',medications=['Doxorubicin'],dose_value=20,dose_unit='mg')
        report=summarize_scenario(summary,profile)
        self.assertEqual(report['reference_trials']['count'],1)
        self.assertEqual(report['medications'][0]['status'],'unassessed')
        self.assertEqual(pk_availability(profile)['status'],'unsupported_drug')
        with self.assertRaises(PKValidationError):simulate_pk('cyclophosphamide',20)

    def test_previous_dependent_catalogs_are_rejected_after_alias_upgrade(self):
        import json
        import tempfile
        from pathlib import Path
        from intelligence_store.drug_aliases import reconcile_drug_aliases
        from intelligence_store.mechanisms import load_annotation_catalog,ANNOTATION_PATH as ANNOTATIONS
        from intelligence_store.safety import load_safety_catalog,CATALOG_PATH as SAFETY
        from intelligence_store.interactions import load_interaction_catalog,CATALOG_PATH as INTERACTIONS
        aliases=reconcile_drug_aliases(summarize_cohort(1))
        with tempfile.TemporaryDirectory() as tmp:
            for loader,source in [(load_annotation_catalog,ANNOTATIONS),(load_safety_catalog,SAFETY),
                                  (load_interaction_catalog,INTERACTIONS)]:
                old=json.loads(source.read_text())
                old['alias_catalog_version']='myeloma-seed-v1.2'
                old['alias_catalog_sha256']='c3bb20d4c7cef33859e2a00933117355125097ff87685a824aa0ab616136ef60'
                p=Path(tmp)/source.name;p.write_text(json.dumps(old))
                with self.subTest(catalog=source.name),self.assertRaisesRegex(ValueError,'incompatible'):
                    loader(aliases,path=p)

    def test_new_reference_aliases_union_without_unsupported_brands(self):
        self.extra('NCT00000002',['Melphalan','EVOMELA','Alkeran'])
        self.extra('NCT00000003',['Fludarabine','Fludarabine phosphate','Fludara'])
        self.extra('NCT00000003',['Melphalan'],member=False)
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=3;db.session.commit()
        r=build_drug_knowledge(summarize_cohort(1));index={e['entity_id']:e for e in r['entries']}
        self.assertEqual(index['melphalan']['nct_ids'],['NCT00000002'])
        self.assertEqual(index['fludarabine']['nct_ids'],['NCT00000003'])
        self.assertEqual(r['coverage']['unmapped_group_count'],2)
        self.assertTrue(index['melphalan']['safety']['boxed_warning']['present'])
        self.assertFalse(index['fludarabine']['safety']['boxed_warning']['present'])
        self.assertEqual(index['melphalan']['source']['label_version'],8)
        self.assertEqual(index['fludarabine']['source']['label_version'],7)
        self.assertIn('CLL',index['fludarabine']['safety']['reference_product'])
        self.assertEqual(index['melphalan']['source']['retrieved_xml_sha256'],
                         '49f6c181e1d1db2bb5f3a212dc89b8a5342eb5164190e5b4607fede02fc52641')
        self.assertEqual(index['fludarabine']['source']['retrieved_xml_sha256'],
                         '8e629988197768e2769fc7f823219500c3e1b90f25c0a3f0427be6682a91d5eb')

    def test_new_exact_partner_reference_counts_and_unsupported_pk(self):
        from intelligence_store.patient_scenarios import summarize_scenario
        from intelligence_store.pharmacokinetics import pk_availability,simulate_pk,PKValidationError
        self.extra('NCT00000002',['Melphalan','Evomela','Cyclosporine'])
        self.extra('NCT00000003',['Fludarabine phosphate','Pentostatin'])
        self.extra('NCT00000004',['Fludarabine','Nipent'])
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=4;db.session.commit()
        summary=summarize_cohort(1);index={e['entity_id']:e for e in build_drug_knowledge(summary)['entries']}
        for entity,partner,expected in [('melphalan','Cyclosporine','NCT00000002'),
                                        ('fludarabine','Pentostatin','NCT00000003')]:
            with self.subTest(entity=entity):
                rule=index[entity]['interactions']['references'][0]
                self.assertEqual(rule['pair_count'],1);self.assertEqual(rule['pair_nct_ids'],[expected])
                profile=copy.deepcopy(self.profile)
                profile.update(selected_drug=entity,medications=[partner,'Uncurated brand'],dose_value=20,dose_unit='mg')
                report=summarize_scenario(summary,profile)
                self.assertEqual(report['medications'][0]['status'],'selected_reference')
                self.assertEqual(report['medications'][1]['status'],'unassessed')
                self.assertEqual(pk_availability(profile)['status'],'unsupported_drug')
                with self.assertRaises(PKValidationError):simulate_pk(entity,20)

    def test_whole_interaction_section_seven_is_accepted_but_invalid_sections_rejected(self):
        import json
        import tempfile
        from pathlib import Path
        from intelligence_store.drug_aliases import reconcile_drug_aliases
        from intelligence_store.interactions import load_interaction_catalog,CATALOG_PATH
        aliases=reconcile_drug_aliases(summarize_cohort(1));catalog=load_interaction_catalog(aliases)
        self.assertEqual(catalog['rule_index']['melphalan-cyclosporine']['sections'],['7'])
        with tempfile.TemporaryDirectory() as tmp:
            for section in ['7.0','7.01','7.1.2','12','70','7<script>']:
                raw=json.loads(CATALOG_PATH.read_text())
                entry=next(e for e in raw['entries'] if e['entity_id']=='melphalan')
                entry['references'][0]['sections']=[section]
                p=Path(tmp)/'invalid.json';p.write_text(json.dumps(raw))
                with self.subTest(section=section),self.assertRaisesRegex(ValueError,'invalid'):
                    load_interaction_catalog(aliases,path=p)

if __name__=='__main__':unittest.main()


class ReviewedMappingMergeTests(unittest.TestCase):
    setUp=fixtures.SavedScenarioTests.setUp
    tearDown=fixtures.SavedScenarioTests.tearDown
    extra=DrugKnowledgeTests.extra

    def test_reviewed_code_joins_catalog_drug_and_is_not_unmapped(self):
        # PS-341 is a reviewed mapping to bortezomib, which also has label-sourced aliases.
        self.extra('NCT00000002',['PS-341'])
        self.extra('NCT00000003',['Velcade'])
        self.extra('NCT00000004',['Thalidomide','Unknown compound'])
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=4;db.session.commit()
        r=build_drug_knowledge(summarize_cohort(1))
        b=next(e for e in r['entries'] if e['entity_id']=='bortezomib')
        self.assertEqual(b['nct_ids'],['NCT00000002','NCT00000003'])
        unmapped_labels={g['label'] for g in r['unmapped_groups']}
        self.assertEqual(unmapped_labels,{'Unknown compound'})
        self.assertEqual([g['label'] for g in r['reviewed_mapping_groups']],['thalidomide'])
        self.assertEqual(r['coverage']['reviewed_mapping_names']['nct_ids'],['NCT00000004'])
        from intelligence_store.drug_aliases import reconcile_drug_aliases
        rows={row['key']:row for row in reconcile_drug_aliases(summarize_cohort(1))['groups']}
        self.assertEqual(rows['catalog:bortezomib']['mapping_status'],'source-backed')
        self.assertEqual(rows['catalog:bortezomib']['reviewed_mapping_keys'],['ps-341'])
        self.assertNotIn('reviewed:bortezomib',rows)

    def test_catalog_drug_found_only_through_review_is_labelled_reviewed(self):
        self.extra('NCT00000002',['CC-4047'])
        cohort=db.session.get(AnalysisCohort,1);cohort.expected_count=cohort.retrieved_count=2;db.session.commit()
        from intelligence_store.drug_aliases import reconcile_drug_aliases
        rows={row['key']:row for row in reconcile_drug_aliases(summarize_cohort(1))['groups']}
        self.assertEqual(rows['catalog:pomalidomide']['mapping_status'],'reviewed-mapping')
        self.assertEqual(rows['catalog:pomalidomide']['catalog_entry']['id'],'pomalidomide')
        r=build_drug_knowledge(summarize_cohort(1))
        self.assertEqual(next(e for e in r['entries'] if e['entity_id']=='pomalidomide')['nct_ids'],['NCT00000002'])
