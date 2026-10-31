"""Digital human 1.0, step 1.2: the lenalidomide elimination body map as data (body-map-view-v1).

Where lenalidomide leaves the body at a given creatinine clearance: kidney filtration, kidney tubular secretion and
non-renal routes. No new model: the numbers come from the Simulation 2.0a pathway model under the intact-nephron
reading, exactly as on the 2.0b patient page (same calibration, reading and unbound fraction), plus the alternative
filtration/secretion split recorded in lenalidomide_pathway_unbound_fraction_assessment_v1.json (the owner's decision:
show both; exposure is the same under both). Each flow carries the evidence status of its kidney-function band, read
from the locked 2.0a report, so the map cannot look more certain than the check.

Nodes carry UBERON anatomy IDs so later drugs and organs reuse one vocabulary. The arrows are clearance flows, not
amounts or concentrations in organs: no source gives lenalidomide tissue concentrations.

Plan: docs/DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md (approved 31 October 2026).
"""
import hashlib
import json
import math
from pathlib import Path

from .lenalidomide_renal_pathways import (EVIDENCE_SHA256, METHOD_VERSION as PATHWAY_METHOD, REPORT_PATH,
                                          calibrate, load_evidence, pathways)
from .patient_renal_pathways import CALIBRATION_CRCL, FU, READING
from .patient_state import digest

DATA = Path(__file__).parent / 'data'
SCHEMA_VERSION = 'body-map-view-v1'
METHOD_VERSION = 'lenalidomide-body-map-v1.0'
DRUG = 'lenalidomide'
RANGE = (10.0, 140.0)

PATHWAY_REPORT_SHA256 = '163b5ca1a95a7f3d745c8e25a93ef58d4bedd0e1e48d6e4bfdfb4a25457a93d5'
FU_RECORD_PATH = DATA / 'lenalidomide_pathway_unbound_fraction_assessment_v1.json'
FU_RECORD_SHA256 = '8796799193207c3fffb9001e6a6d1cd6ad45f165c94a5986c944cf47a2faa7df'

# Anatomy vocabulary (UBERON IDs checked against the ontology on 31 October 2026).
NODES = [
    {'id': 'gut', 'label': 'Digestive tract (oral dose)', 'uberon_id': 'UBERON:0001555'},
    {'id': 'plasma', 'label': 'Blood plasma', 'uberon_id': 'UBERON:0001969'},
    {'id': 'kidney', 'label': 'Kidney', 'uberon_id': 'UBERON:0002113'},
    {'id': 'glomerulus', 'label': 'Glomerulus (filtration)', 'uberon_id': 'UBERON:0000074', 'parent': 'kidney'},
    {'id': 'tubule', 'label': 'Renal tubule (secretion)', 'uberon_id': 'UBERON:0009773', 'parent': 'kidney'},
    {'id': 'urine', 'label': 'Urine (unchanged drug)', 'uberon_id': 'UBERON:0001088'},
    {'id': 'non_renal', 'label': 'Non-renal routes', 'uberon_id': None,
     'note': 'Everything that is not unchanged drug in urine; the source does not identify the routes (not via cytochrome P450).'},
]

# Kidney-function bands as the study defined its groups (creatinine clearance, mL/min): normal > 80, mild 50-80
# (both ends included), moderate 30 to < 50, severe < 30 not on dialysis. Outer ends are the map's drawn range.
BANDS = [
    {'id': 'normal', 'range': [80.0, RANGE[1]], 'lower_inclusive': False, 'upper_inclusive': True, 'report_group': None},
    {'id': 'mild', 'range': [50.0, 80.0], 'lower_inclusive': True, 'upper_inclusive': True, 'report_group': 'mild'},
    {'id': 'moderate', 'range': [30.0, 50.0], 'lower_inclusive': True, 'upper_inclusive': False, 'report_group': 'moderate'},
    {'id': 'severe', 'range': [RANGE[0], 30.0], 'lower_inclusive': True, 'upper_inclusive': False,
     'report_group': 'severe_without_dialysis'},
]
STATUS_TEXT = {
    'calibrated': 'Calibrated: the model was fitted to the normal-function group.',
    'checked_consistent': 'Checked: consistent with the observed group in every scenario of the locked check.',
    'consistent_primary_only': 'Consistent with the observed group in the primary scenario only; not in every scenario of the locked check.',
    'check_disagrees': ('Outside check disagrees: the model under-predicts exposure here; renal elimination is probably lower, '
                        'and exposure higher, than shown.'),
}


class BodyMapError(ValueError):
    pass


def _pinned(path, sha256, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise BodyMapError(f'{label} is missing or changed; the map was not built.')
    return json.loads(raw)


def load_fu_record():
    return _pinned(FU_RECORD_PATH, FU_RECORD_SHA256, 'Unbound-fraction decision record')


def load_pathway_report():
    return _pinned(REPORT_PATH, PATHWAY_REPORT_SHA256, 'Simulation 2.0a pathway report')


def band_for(crcl):
    """The study band for a creatinine clearance (the study's own boundary conventions)."""
    for band in BANDS:
        lo, hi = band['range']
        above = crcl >= lo if band['lower_inclusive'] else crcl > lo
        below = crcl <= hi if band['upper_inclusive'] else crcl < hi
        if above and below:
            return band
    return None


def band_status(band, report=None):
    """Evidence status of a band, read from the locked 2.0a report (reading A)."""
    if band['report_group'] is None:
        return 'calibrated'
    report = report or load_pathway_report()
    scenarios = report['decision']['classification_by_scenario']
    primary = scenarios['primary'][band['report_group']][READING]
    every = {s[band['report_group']][READING] for s in scenarios.values()}
    if primary == 'consistent':
        return 'checked_consistent' if every == {'consistent'} else 'consistent_primary_only'
    return 'check_disagrees'


def _split(cal, crcl):
    p = pathways(cal, crcl, READING)
    return {k: p[k] for k in ('filtration_ml_min', 'secretion_ml_min', 'renal_ml_min', 'non_renal_ml_min', 'total_ml_min', 'fe')}


def build_map(crcl, mode, record=None):
    """The map for one creatinine clearance. `mode` is 'explorer' or 'record'; `record` adds the source revision."""
    if isinstance(crcl, bool) or not isinstance(crcl, (int, float)) or not math.isfinite(crcl):
        raise BodyMapError('Creatinine clearance must be a finite number.')
    crcl = float(crcl)
    fu_record = load_fu_record()
    view = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'drug': DRUG, 'mode': mode,
            'crcl_ml_min': crcl, 'range_ml_min': list(RANGE),
            'model': {'pathway_method_version': PATHWAY_METHOD, 'reading': READING, 'calibration_crcl_ml_min': CALIBRATION_CRCL,
                      'evidence_sha256': EVIDENCE_SHA256, 'report_file_sha256': PATHWAY_REPORT_SHA256,
                      'fu_record_version': fu_record['assessment_version'], 'fu_record_sha256': FU_RECORD_SHA256},
            'nodes': NODES, 'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    if record:
        view['record'] = record
    if not RANGE[0] <= crcl <= RANGE[1]:
        view.update(status='outside_range',
                    message=(f'Creatinine clearance {crcl:.0f} mL/min is outside {RANGE[0]:g}-{RANGE[1]:g} mL/min, the range the '
                             'pathway check covered; the map is not drawn.'))
        view['view_sha256'] = digest(view)
        return view
    evidence = load_evidence()
    fu_alt = next(v['fu'] for v in fu_record['values'] if v['id'] == 'ex_vivo_study_subjects')
    cal, cal_alt = calibrate(evidence, CALIBRATION_CRCL, FU), calibrate(evidence, CALIBRATION_CRCL, fu_alt)
    p, alt = _split(cal, crcl), _split(cal_alt, crcl)
    normal = _split(cal, CALIBRATION_CRCL)
    band = band_for(crcl)
    status = band_status(band)
    total = p['total_ml_min']
    renal_status = status
    flows = [
        {'from': 'gut', 'to': 'plasma', 'kind': 'absorption', 'value': None, 'unit': None,
         'note': 'Oral dose; bioavailability taken as 1 (urinary recovery implies at least about 0.85).'},
        {'from': 'plasma', 'to': 'glomerulus', 'kind': 'filtration', 'value': p['filtration_ml_min'], 'unit': 'mL/min',
         'alternative_value': alt['filtration_ml_min'], 'share_of_elimination': p['filtration_ml_min'] / total,
         'alternative_share': alt['filtration_ml_min'] / total, 'status': renal_status,
         'basis': f'unbound fraction x creatinine clearance; fu {FU} (in vitro) and, as alternative, {fu_alt} (ex vivo)'},
        {'from': 'plasma', 'to': 'tubule', 'kind': 'tubular_secretion', 'value': p['secretion_ml_min'], 'unit': 'mL/min',
         'alternative_value': alt['secretion_ml_min'], 'share_of_elimination': p['secretion_ml_min'] / total,
         'alternative_share': alt['secretion_ml_min'] / total, 'status': renal_status,
         'basis': 'renal clearance minus filtration in the normal group, scaled with creatinine clearance (intact-nephron reading)'},
        {'from': 'kidney', 'to': 'urine', 'kind': 'renal_excretion', 'value': p['renal_ml_min'], 'unit': 'mL/min',
         'share_of_elimination': p['renal_ml_min'] / total, 'status': renal_status,
         'basis': 'filtration + secretion; the same under both unbound fractions'},
        {'from': 'plasma', 'to': 'non_renal', 'kind': 'non_renal', 'value': p['non_renal_ml_min'], 'unit': 'mL/min',
         'share_of_elimination': p['non_renal_ml_min'] / total, 'status': 'calibrated',
         'basis': 'total minus renal clearance in the normal group; held constant'},
    ]
    view.update(
        status='completed',
        band={'id': band['id'], 'range_ml_min': band['range'], 'status': status, 'status_text': STATUS_TEXT[status]},
        flows=flows,
        totals={'total_ml_min': total, 'renal_ml_min': p['renal_ml_min'], 'fraction_excreted_unchanged': p['fe'],
                'relative_exposure_same_dose': normal['total_ml_min'] / total},
        normal_reference={'crcl_ml_min': CALIBRATION_CRCL, 'total_ml_min': normal['total_ml_min'], 'fraction_excreted_unchanged': normal['fe']},
        drawing_scale={'max_flow_ml_min': normal['total_ml_min'],
                       'rule': 'Arrow width is proportional to clearance on one fixed scale (the normal total), so maps can be compared.'},
        limitations=[
            'Typical values from group means of 5-7 subjects per kidney-function group; real patients vary widely.',
            'Arrows are clearance flows, not amounts or concentrations in organs.',
            'Creatinine clearance stands in for GFR and overestimates it.',
            'The filtration/secretion split depends on the unbound fraction, which the data do not pin down; both values are shown. '
            'Total renal clearance and exposure are the same under both.',
            'Non-renal clearance is held constant; the moderate group of the check suggests it may not be.',
            'Not a measurement of kidney function, an exposure prediction for a patient, or a dose recommendation.'])
    view['view_sha256'] = digest(view)
    return view


def explorer_map(crcl):
    return build_map(crcl, 'explorer')


def record_map(revision_id, weight_basis=None):
    """The map for a saved synthetic record, from the same estimate the 2.0b patient page uses."""
    from .patient_renal_pathways import patient_renal_pathways
    pv = patient_renal_pathways(revision_id, weight_basis)
    record = {'revision_id': pv['revision_id'], 'pathways_view_sha256': pv['report_sha256'],
              'covariate_estimate_status': pv['covariate_estimate']['status']}
    if pv['status'] != 'completed':
        view = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'drug': DRUG, 'mode': 'record',
                'record': record, 'status': pv['status'], 'message': pv.get('message'), 'nodes': NODES,
                'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
        view['view_sha256'] = digest(view)
        return view
    return build_map(pv['crcl_ml_min'], 'record', record)
