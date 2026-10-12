"""Observed summary versus mathematical bound; never a fitted-data validation test."""
import hashlib
import json
from pathlib import Path

DATA_PATH=Path(__file__).with_name('data')/'bortezomib_observed_summary_v1.json'
MODEL_PATH=Path(__file__).with_name('data')/'bortezomib_proteasome_reference_v1.json'
DATA_SHA256='2f077db4f1b44b65bd7e634e067d25b5a703e9563a6a21e91f5c57288bb24ae9'
MODEL_SHA256='ac5e3ad9a9cb8156ca019ba0b9bf31956b96c973631e595ebafabdc4166b59be'


def _read_pinned(path,expected):
    try:raw=path.read_bytes()
    except OSError as exc:raise ValueError('Required source extraction is unavailable.') from exc
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Source extraction integrity mismatch; review withheld.')
    return json.loads(raw)


def build_evidence_review():
    evidence=_read_pinned(DATA_PATH,DATA_SHA256)
    model=_read_pinned(MODEL_PATH,MODEL_SHA256)
    cap=model['parameters']['maximum_inhibition_percentage_points']
    rows=[]
    for original in evidence['rows']:
        row=dict(original)
        row['above_deterministic_inhibition_ceiling']=row['mean_peak_inhibition_percent']>cap
        row['excess_above_ceiling_percentage_points']=round(max(0,row['mean_peak_inhibition_percent']-cap),10)
        row['model_prediction_at_observed_concentration']=None
        row['comparison_kind']='summary_vs_equation_bound_not_prediction_residual'
        rows.append(row)
    flagged=sum(r['above_deterministic_inhibition_ceiling'] for r in rows)
    result={
        'schema_version':'bortezomib-summary-review-v1','method_version':'observed-summary-bound-screen-v1.0',
        'status':'review_required' if flagged else 'no_bound_exceedance_not_validation',
        'evidence_sha256':DATA_SHA256,'model_reference_sha256':MODEL_SHA256,
        'evidence':evidence,'model_source':model['source'],
        'model_bound':{'maximum_inhibition_percentage_points':cap,
            'activity_floor_percent_of_baseline':model['parameters']['baseline_percent']-cap,
            'scope':'deterministic fixed-parameter equation, without observation error or variability'},
        'summary_count':len(rows),'summaries_above_ceiling':flagged,
        'rows':rows,'matched_concentration_response_pairs':0,
        'rmse':None,'mae':None,'fit_status':'not_run','prediction_validation_status':'not_established',
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'interpretation':'Observed summary means above the deterministic ceiling warrant investigation. '
            'They are not paired predictions or a formal goodness-of-fit test. '
            'No p-value, confidence interval, pooled patient count or inferred concentration is computed.',
        'next_evidence_needed':['Check selected source-figure series and normalization against the model.',
            'Extract matched concentration/activity time points with digitization uncertainty.',
            'Distinguish model-development data from genuinely independent test data.']
    }
    result['report_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',', ':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return result
