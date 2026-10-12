"""One-at-a-time assumption experiment; not statistical uncertainty."""
import hashlib,json
from .bortezomib_timecourse import build_timecourse
RATES=(0.1,1.0,10.0)
SELECTED_TIMES=(1/12,1.,24.,48.,240+1/12,241.,264.,288.)

def build_assumption_sensitivity():
    runs=[build_timecourse(relaxation_rate_per_h=rate) for rate in RATES]
    base=runs[1]['points'];summaries=[]
    for rate,run in zip(RATES,runs):
        rows=run['points']
        if [(r['time_h'],r['phase']) for r in rows]!=[(r['time_h'],r['phase']) for r in base]:
            raise ValueError('Sample alignment mismatch.')
        diffs={key:max(abs(r[key]-b[key]) for r,b in zip(rows,base)) for key in ['concentration_nm','activity_percent']}
        summaries.append({'assumed_relaxation_rate_per_h':rate,'rate_origin':'analyst_selected_not_estimated',
            'maximum_sampled_absolute_difference_from_1_per_h':diffs,
            'maximum_mass_balance_error_mg':run['maximum_mass_balance_error_mg'],'run':run})
    selected=[]
    for t in SELECTED_TIMES:
        values=[]
        for rate,run in zip(RATES,runs):
            row=next(r for r in run['points'] if abs(r['time_h']-t)<1e-9 and r['phase']!='pre_dose')
            values.append({'rate_per_h':rate,'concentration_nm':row['concentration_nm'],'activity_percent':row['activity_percent']})
        selected.append({'time_h':t,'values':values})
    report={'schema_version':'bortezomib-assumption-sensitivity-v1','status':'review_required','scenarios':summaries,
        'selected_times':selected,'selection':'Fixed analyst-selected rates 0.1, 1 and 10 per hour; not plausible bounds inferred from data.',
        'interpretation':'Differences measure dependence on the assumed rate. They are not confidence intervals, evidence of accuracy, or a reason to select the best-looking curve.',
        'scope':'Only the elimination relaxation rate changes. Doses, BSA, distribution rates, PD parameters and elapsed-time clock are fixed.',
        'empirical_validation':False,'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'equation_4_resolved':False,'probability_weights':None,'confidence_interval':None,'fitting_performed':False}
    report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return report
