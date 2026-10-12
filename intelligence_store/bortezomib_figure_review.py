"""Provisional aggregate figure comparison; no fitting or patient predictions."""
import hashlib
import json
import math
from pathlib import Path
from .bortezomib_proteasome import calculate_proteasome_activity, REFERENCE_SHA256
DATA_PATH=Path(__file__).with_name('data')/'bortezomib_figure_pairs_preview_v1.json'
DATA_SHA256='349a7c8c7799e0724e23ca10e38d2f2814ee0b4e902cbc5f46bc513ccaa7233d'


def pixel_value(y, figure):
    a,b=figure['y_calibration']
    fraction=(y-a['pixel_y'])/(b['pixel_y']-a['pixel_y'])
    if figure['y_axis_scale']=='log10':
        return 10**(math.log10(a['value'])+fraction*(math.log10(b['value'])-math.log10(a['value'])))
    return a['value']+fraction*(b['value']-a['value'])


def build_figure_review():
    try: raw=DATA_PATH.read_bytes()
    except OSError as exc: raise ValueError('Figure extraction unavailable.') from exc
    if hashlib.sha256(raw).hexdigest()!=DATA_SHA256:
        raise ValueError('Figure extraction altered; review withheld.')
    source=json.loads(raw)
    rows=[]
    tolerance=source['digitization']['y_reading_tolerance_px']
    factor=1000/source['conversion']['molecular_weight_g_per_mol']
    def activity(c):
        return calculate_proteasome_activity(plasma_concentrations_nm=[c])['points'][0]['activity_percent_of_baseline']
    for item in source['rows']:
        pk_y=item['pk_marker_xy'][1];pd_y=item['pd_marker_xy'][1]
        pk=pixel_value(pk_y,source['figures']['pk'])
        pk_bounds=sorted(pixel_value(pk_y+offset,source['figures']['pk']) for offset in [-tolerance,tolerance])
        inhibition=pixel_value(pd_y,source['figures']['pd'])
        obs=100-inhibition
        obs_bounds=sorted(100-pixel_value(pd_y+offset,source['figures']['pd']) for offset in [-tolerance,tolerance])
        predicted=activity(pk*factor)
        prediction_bounds=sorted(activity(c*factor) for c in pk_bounds)
        rows.append(dict(item, approximate_concentration_ng_ml=pk,
            approximate_concentration_nm=pk*factor, concentration_reading_range_ng_ml=pk_bounds,
            approximate_observed_activity_percent=obs, activity_reading_range=obs_bounds,
            equation_activity_at_mean_concentration_percent=predicted,
            equation_activity_reading_range=prediction_bounds,
            descriptive_difference_percentage_points=predicted-obs,
            difference_reading_range=[prediction_bounds[0]-obs_bounds[1],prediction_bounds[1]-obs_bounds[0]]))
    report=dict(schema_version='bortezomib-figure-review-v1',status='review_required',source=source,rows=rows,
        extraction_sha256=DATA_SHA256,model_reference_sha256=REFERENCE_SHA256,
        comparison_type='provisional_time_aligned_aggregate_means',individual_matched_pairs=0,
        rmse=None,mae=None,independent_validation=False,clinical_prediction_validated=False,
        ready_for_patient_simulation=False,refitting_performed=False,
        uncertainty='Reading sensitivity only; not confidence or prediction intervals. Marker identity, calibration, biological and parameter uncertainty are not quantified.',
        interpretation='Two selected late-time aggregate points cannot resolve the peak discrepancy or validate the full model. No efficacy or toxicity inference.')
    report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return report
