"""Read-only protocol extraction review. No conversion, inference, fit or solver."""
import hashlib
import json
import math
from pathlib import Path

REVIEW_PATH=Path(__file__).resolve().parent/'data/lenalidomide_assay_extraction_v1.json'


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate extraction key.')
        result[key]=value
    return result


def build_assay_review():
    raw=REVIEW_PATH.read_bytes()
    if len(raw)>100_000:raise ValueError('Extraction packet is too large.')
    def reject(value):raise ValueError('Nonfinite JSON value.')
    packet=json.loads(raw,object_pairs_hook=_unique,parse_constant=reject)
    expected={'lenalidomide_nominal_medium_concentration':'umol/L',
              'lenalidomide_pretreatment_duration':'h','chx_medium_concentration':'ug/mL'}
    try:
        if packet['schema_version']!='assay-extraction-review-v1' or packet['entity_id']!='lenalidomide':raise ValueError('Unsupported assay extraction.')
        if packet['clinical_prediction_validated'] is not False or packet['ready_for_patient_simulation'] is not False:raise ValueError('Unexpected readiness promotion.')
        assay=packet['assay'];assessment=packet['model_assessment']
        if assay['assay_id']!='lu-fig2d-mm1s-chase':raise ValueError('Unsupported assay.')
        conditions=assay['conditions']
        if len(conditions)!=3 or {c['field'] for c in conditions}!=set(expected):raise ValueError('Incomplete or duplicate conditions.')
        for condition in conditions:
            value=condition['value']
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError('Condition values must be finite nonnegative numbers.')
            if condition['unit']!=expected[condition['field']] or not condition['source_locator'] or not condition['scope']:
                raise ValueError('Conditions need explicit supported units and provenance.')
        if assay['protein_measurements']!=[] or assay['sampling_times_h'] is not None:
            raise ValueError('This protocol-only review does not accept measurement data.')
        if assessment['data_ready_for_fitting'] is not False or assessment['accepted_model_parameters']!={} or assessment['parameter_fitting_status']!='not_run':
            raise ValueError('This review does not accept fitted parameters or fitting readiness.')
        if assessment['patient_revision_id'] is not None or assessment['pk_run_id'] is not None:raise ValueError('No patient or PK associations are supported.')
    except (KeyError,TypeError,AttributeError) as exc:raise ValueError('Incomplete extraction packet.') from exc
    report={'schema_version':'assay-review-report-v1','packet_sha256':hashlib.sha256(raw).hexdigest(),
        'assay_extraction':packet,'simulation_status':'not_run','clinical_prediction_validated':False,
        'ready_for_patient_simulation':False,
        'validation_scope':'Structural checks of a protocol-only extraction, not independent source verification or numerical data acceptance.'}
    report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return report
