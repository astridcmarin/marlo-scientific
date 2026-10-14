"""Source-checked research-tool registry. Inventory does not execute models."""
import hashlib
from .bortezomib_proteasome import load_reference as load_pd,REFERENCE_SHA256
from .bortezomib_timecourse import load_reference as load_pk,REFERENCE_HASH
from .bortezomib_evidence_review import DATA_PATH as SUMMARY_PATH,DATA_SHA256 as SUMMARY_SHA
from .bortezomib_figure_review import DATA_PATH as FIGURE_PATH,DATA_SHA256 as FIGURE_SHA
from .bortezomib_platelet_evidence import EXTRACT_PATH as PLT_EXTRACT_PATH,EXTRACT_SHA256 as PLT_EXTRACT_SHA,OBSERVED_PATH as PLT_OBS_PATH,OBSERVED_SHA256 as PLT_OBS_SHA
from .bortezomib_platelets import PLAN_PATH as PLT_PLAN_PATH,PLAN_SHA256 as PLT_PLAN_SHA

def _pinned(path,sha):
    try:return hashlib.sha256(path.read_bytes()).hexdigest()==sha
    except OSError:return False

def research_tool_registry():
    valid={};hashes={'pd':REFERENCE_SHA256,'pk':REFERENCE_HASH,'summary':SUMMARY_SHA,'figures':FIGURE_SHA,'platelet_model':PLT_EXTRACT_SHA,'platelet_observed':PLT_OBS_SHA,'platelet_plan':PLT_PLAN_SHA}
    for key,loader in [('pd',load_pd),('pk',load_pk)]:
        try:loader();valid[key]=True
        except (ValueError,OSError):valid[key]=False
    valid['summary']=_pinned(SUMMARY_PATH,SUMMARY_SHA);valid['figures']=_pinned(FIGURE_PATH,FIGURE_SHA)
    valid['platelet_model']=_pinned(PLT_EXTRACT_PATH,PLT_EXTRACT_SHA);valid['platelet_observed']=_pinned(PLT_OBS_PATH,PLT_OBS_SHA);valid['platelet_plan']=_pinned(PLT_PLAN_PATH,PLT_PLAN_SHA)
    specs=[
        ('bortezomib-pd-equation','target_activity','Proteasome activity equation','bortezomib_proteasome_demo',('pd',),
         'Hypothetical concentration input; direct target-activity calculation.', ['peak_inhibition_discrepancy','patient_applicability_not_established']),
        ('bortezomib-timecourse-candidate','research_timecourse','Study-regimen time-course candidate','bortezomib_timecourse',('pd','pk'),
         'Fixed study regimen and assumed mean BSA; source reproduction unconfirmed.', ['elimination_timescale_unresolved','peak_inhibition_discrepancy','patient_applicability_not_established']),
        ('bortezomib-assumption-experiment','assumption_experiment','Elimination-assumption comparison','bortezomib_assumptions',('pd','pk'),
         'Three analyst-selected rates; not confidence limits or source estimates.', ['elimination_timescale_unresolved','not_statistical_uncertainty']),
        ('bortezomib-observed-review','evidence_review','Observed peak-evidence review','bortezomib_evidence_review',('pd','summary'),
         'Group summary bounds review; no matched individual concentration-response data.', ['not_independent_validation']),
        ('bortezomib-figure-review','evidence_review','Provisional figure readings','bortezomib_figure_review',('pd','figures'),
         'Two approximate aggregate points; independent digitization review pending.', ['marker_overlap','not_independent_validation']),
        ('bortezomib-platelet-timecourse','drug_effect_timecourse','Platelet time course (Lignet 2022)','bortezomib_platelets',('platelet_model','platelet_observed','platelet_plan'),
         'Typical platelet curves for the studied regimen from a model fitted to mean data; both mechanism variants shown.', ['mechanism_unresolved','effect_term_negative_after_doses','first_dose_exposure_overstated','not_independent_validation'])]
    sources={'bortezomib-platelet-timecourse':'https://doi.org/10.1002/psp4.12743'}
    tools=[]
    for ident,kind,title,endpoint,dependencies,scope,issues in specs:
        ok=all(valid[d] for d in dependencies)
        tools.append({'tool_id':ident,'drug_id':'bortezomib','kind':kind,'title':title,
            'endpoint':'landscape.'+endpoint if ok else None,'availability':'available' if ok else 'unavailable',
            'scientific_status':'review_required','scope':scope,'open_issues':issues,
            'required_source_sha256':{k:hashes[k] for k in dependencies},
            'availability_basis':'Reference integrity checked; no solver execution or patient applicability review.',
            'source_url':sources.get(ident,'https://pmc.ncbi.nlm.nih.gov/articles/PMC6495529/'),
            'clinical_prediction_validated':False,'ready_for_patient_simulation':False})
    return {'bortezomib':tools}
