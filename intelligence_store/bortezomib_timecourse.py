"""Fixed research reproduction candidate. Not a patient-dose simulator."""
import hashlib,json,math
from pathlib import Path
from .bortezomib_proteasome import calculate_proteasome_activity,REFERENCE_SHA256
REFERENCE_PATH=Path(__file__).with_name('data')/'bortezomib_pk_candidate_v1.json'
REFERENCE_HASH='0430e2893230d90cd13d6bce892c8d9f1094df4859c578b9fe7e29d5bfc53b3c'

def load_reference():
    try:raw=REFERENCE_PATH.read_bytes()
    except OSError as exc:raise ValueError('PK reference unavailable.') from exc
    if hashlib.sha256(raw).hexdigest()!=REFERENCE_HASH:raise ValueError('PK reference changed; calculation withheld.')
    return json.loads(raw)

def elimination_rate(t,ref):
    p=ref['parameters']
    return p['k1ss_per_h']+(p['k10_per_h']-p['k1ss_per_h'])*math.exp(-ref['assumed_relaxation_rate_per_h']*t)

def derivative(t,y,ref):
    p=ref['parameters'];a,c,d,_=y;k=elimination_rate(t,ref)
    return (-(k+p['k12_per_h']+p['k13_per_h'])*a+p['k21_per_h']*c+p['k31_per_h']*d,
            p['k12_per_h']*a-p['k21_per_h']*c,p['k13_per_h']*a-p['k31_per_h']*d,k*a)

def rk4(t,y,h,ref):
    a=derivative(t,y,ref)
    b=derivative(t+h/2,tuple(v+h*w/2 for v,w in zip(y,a)),ref)
    c=derivative(t+h/2,tuple(v+h*w/2 for v,w in zip(y,b)),ref)
    d=derivative(t+h,tuple(v+h*w for v,w in zip(y,c)),ref)
    return tuple(v+h*(aa+2*bb+2*cc+dd)/6 for v,aa,bb,cc,dd in zip(y,a,b,c,d))

def build_timecourse(*,max_step_h=0.02,relaxation_rate_per_h=1.0):
    if type(max_step_h) not in (int,float) or not math.isfinite(max_step_h) or not 0.005<=max_step_h<=0.02:
        raise ValueError('Numerical verification step must be 0.005–0.02 h.')
    if type(relaxation_rate_per_h) not in (int,float) or not math.isfinite(relaxation_rate_per_h) or not 0.1<=relaxation_rate_per_h<=10:
        raise ValueError('Assumption sensitivity rate must be finite and within 0.1–10 per hour.')
    source_ref=load_reference()
    ref=dict(source_ref,assumed_relaxation_rate_per_h=float(relaxation_rate_per_h))
    p=ref['parameters'];reg=ref['regimen'];dose=reg['dose_mg_m2']*reg['assumed_mean_bsa_m2']
    doses=set(reg['dose_times_h']);end=reg['end_time_h']
    times=sorted(set(range(end+1)) | {t+dt for t in doses for dt in [0,1/12,0.25,0.5,1,2,4,8,12,24,48] if t+dt<=end})
    y=(0.,0.,0.,0.);t=0.;administered=0.;rows=[]
    def record(phase):
        c=y[0]/p['central_volume_l']*1e6/ref['molecular_weight_g_mol']
        activity=calculate_proteasome_activity(plasma_concentrations_nm=[c])['points'][0]['activity_percent_of_baseline']
        if min(y)<-1e-10 or not all(math.isfinite(v) for v in y):raise ValueError('Invalid numerical state.')
        rows.append(dict(time_h=t,phase=phase,central_mg=y[0],peripheral_2_mg=y[1],peripheral_3_mg=y[2],
            eliminated_mg=y[3],administered_mg=administered,mass_balance_error_mg=sum(y)-administered,
            concentration_nm=c,activity_percent=activity,elimination_rate_per_h=elimination_rate(t,ref)))
    for target in times:
        # Every dose is a target: integration never crosses a bolus discontinuity.
        while target-t>1e-12:
            h=min(max_step_h,target-t);y=rk4(t,y,h,ref);t+=h
        t=float(target)
        if target in doses:
            record('pre_dose');y=(y[0]+dose,*y[1:]);administered+=dose;record('post_dose')
        else:record('sample')
    report=dict(schema_version='bortezomib-timecourse-candidate-v1',status='review_required',reference=source_ref,
        pk_reference_sha256=REFERENCE_HASH,pd_reference_sha256=REFERENCE_SHA256,
        dose_mg=dose,points=rows,solver={'method':'RK4','max_step_h':max_step_h,'dose_handling':'exact bolus boundaries; pre/post states retained'},
        maximum_mass_balance_error_mg=max(abs(r['mass_balance_error_mg']) for r in rows),
        patient_id=None,source_reproduction_established=False,empirical_validation=False,
        clinical_prediction_validated=False,ready_for_patient_simulation=False,
        efficacy_prediction=None,toxicity_prediction=None,
        equation_4_review_required=True,uncertainty_intervals=None)
    if relaxation_rate_per_h != source_ref['assumed_relaxation_rate_per_h']:
        report['assumption_override']={'relaxation_rate_per_h':float(relaxation_rate_per_h),
            'origin':'analyst_selected_sensitivity_scenario_not_published_estimate',
            'source_default_relaxation_rate_per_h':source_ref['assumed_relaxation_rate_per_h']}
    report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return report
