"""Read-only qualitative evidence projection; no solver or storage operations."""
import hashlib
import json
from pathlib import Path

PLAN_PATH=Path(__file__).resolve().parent/'data/lenalidomide_mechanism_evidence_plan_v1.json'
PLAN_SHA256 = 'd505cd79baa0293555a110db9654807423fe976b1f50b7d143d212b7569c656e'


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate evidence-plan key.')
        result[key]=value
    return result


def build_mechanism_map():
    raw=PLAN_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError('File differs from its pinned checksum (lenalidomide_mechanism_evidence_plan_v1.json)')
    if len(raw)>100_000:raise ValueError('Evidence plan is too large.')
    def reject_constant(value):raise ValueError('Nonfinite JSON values are not supported.')
    plan=json.loads(raw,object_pairs_hook=_unique,parse_constant=reject_constant)
    try:
        if plan['schema_version']!='mechanism-evidence-plan-v1' or plan['entity_id']!='lenalidomide':
            raise ValueError('Unsupported evidence plan.')
        if plan['clinical_prediction_validated'] is not False or plan['ready_for_patient_simulation'] is not False:
            raise ValueError('This qualitative map requires false readiness flags.')
        if not plan['quantitative_inputs'] or any(v is not None for v in plan['quantitative_inputs'].values()):
            raise ValueError('This projection does not accept quantitative parameters.')
        source=plan['source']
        if source['source_id']!='lu-science-1244917' or source['url']!='https://pmc.ncbi.nlm.nih.gov/articles/PMC4070318/':
            raise ValueError('Unrecognized mechanism source.')
        claims=plan['claims'];ids=[c['claim_id'] for c in claims]
        if len(set(ids))!=len(ids) or set(ids)!={'substrate-recruitment','protein-degradation','cell-context'}:
            raise ValueError('Missing, duplicate or unsupported mechanism claims.')
        if any(c['source_id']!=source['source_id'] or not c['locator'] or not c['context'] or not c['statement'] for c in claims):
            raise ValueError('A claim needs a source, locator, context and statement.')
        if not isinstance(plan['missing_evidence'],list) or not all(isinstance(s,str) and s for s in plan['missing_evidence']):
            raise ValueError('Missing-evidence entries must be text.')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Evidence-plan structure is incomplete.') from exc
    stages=[
        {'stage_id':'drug-crbn','label':'Lenalidomide-associated cereblon',
         'description':'Drug-modified substrate recognition in the cereblon-containing ligase system.',
         'claim_ids':['substrate-recruitment']},
        {'stage_id':'recruitment','label':'IKZF1 / IKZF3 recruitment',
         'description':'Association of these substrate proteins with the ligase system.',
         'claim_ids':['substrate-recruitment']},
        {'stage_id':'ubiquitination','label':'Ubiquitination',
         'description':'Substrate proteins acquire ubiquitin modifications.',
         'claim_ids':['protein-degradation']},
        {'stage_id':'degradation','label':'Proteasomal degradation',
         'description':'The reported cellular process reduces substrate protein abundance.',
         'claim_ids':['protein-degradation']}]
    report={'schema_version':'qualitative-mechanism-map-v1','method_version':'lenalidomide-mechanism-projection-v1.0',
        'purpose':'research_education','entity_id':'lenalidomide','evidence_plan':plan,
        'evidence_plan_sha256':hashlib.sha256(raw).hexdigest(),'stages':stages,
        'relationships':[{'from':a['stage_id'],'to':b['stage_id'],'interpretation':'curated_qualitative_sequence',
            'claim_ids':list(dict.fromkeys(a['claim_ids']+b['claim_ids']))} for a,b in zip(stages,stages[1:])],
        'patient_revision_id':None,'pk_run_id':None,'simulation_status':'not_run',
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'limitation':'Curated schematic of selected reported cellular mechanisms. Arrows show a qualitative sequence, not fitted rates, probabilities, stoichiometry or a complete mechanism. No patient response is predicted.',
        'review_scope':'Structural checks only. Claims and source-review metadata are curated declarations, not independently verified evidence.'}
    report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return report
