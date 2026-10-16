"""Simulation 2.0b: where lenalidomide leaves the body for one synthetic patient.

The patient's creatinine clearance is estimated from the saved record (Cockcroft-Gault, with the documented
weight-basis assumption). The Simulation 2.0a pathway model, calibrated on the normal-renal-function group of study
CC-5013-PK-001, splits clearance into filtration, tubular secretion and non-renal routes under the intact-nephron
reading. The secretion-preserved reading was rejected in 2.0a and is not offered. The intact-nephron reading itself
under-predicted exposure in moderate impairment, so in that range renal elimination is probably lower than shown.

Outputs are typical-value shares and clearances, not a measurement of this patient's kidney function or urine output.
"""
import copy

from .estimated_pk import estimate_for_revision, primary_weight_basis
from .lenalidomide_renal_pathways import EVIDENCE_SHA256, METHOD_VERSION as PATHWAY_METHOD, calibrate, load_evidence, pathways
from .patient_state import digest
from .patient_state_revisions import read_revision

SCHEMA_VERSION = 'patient-renal-pathways-view-v1'
METHOD_VERSION = 'patient-renal-pathways-v1.0'
READING = 'A_intact_nephron'
CALIBRATION_CRCL = 110.0
FU = 0.77
RANGE = (10.0, 140.0)
READING_NOTE = ('Simulation 2.0a: keeping secretion constant was rejected (about 2-fold under-prediction in moderate and '
                'severe impairment). Scaling secretion with creatinine clearance fitted mild and severe impairment but '
                'under-predicted exposure in moderate impairment and over-predicted its urine fraction (67% vs 42% '
                'observed), so renal elimination appears to fall faster than this reading assumes.')


def patient_renal_pathways(revision_id, weight_basis=None):
    revision = read_revision(revision_id)
    if revision is None:
        raise ValueError('Saved patient-state revision does not exist.')
    weight_basis = weight_basis or primary_weight_basis()
    estimate = estimate_for_revision(revision_id, weight_basis)
    evidence = load_evidence()
    cal = calibrate(evidence, CALIBRATION_CRCL, FU)
    view = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'pathway_method_version': PATHWAY_METHOD,
            'revision_id': revision.id, 'reading': READING, 'reading_note': READING_NOTE,
            'evidence_version': evidence['evidence_version'], 'evidence_sha256': EVIDENCE_SHA256,
            'calibration': {k: cal[k] for k in ('crcl_ml_min', 'fu', 'total_ml_min', 'renal_ml_min', 'filtration_ml_min',
                                                 'secretion_ml_min', 'non_renal_ml_min')},
            'covariate_estimate': copy.deepcopy(estimate),
            'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    if estimate['status'] != 'estimated':
        view.update(status='missing_inputs', missing_fields=list(estimate['missing_fields']),
                    message='The record lacks the inputs needed to estimate creatinine clearance; save a new revision with them.')
        view['report_sha256'] = digest(view)
        return view
    crcl = float(estimate['estimates']['creatinine_clearance']['value'])
    p = pathways(cal, crcl, READING)
    normal = pathways(cal, CALIBRATION_CRCL, READING)
    warnings = []
    if crcl < RANGE[0] or crcl > RANGE[1]:
        warnings.append(f'Estimated creatinine clearance {crcl:.0f} mL/min is outside the range the pathway check covered '
                        f'(about {RANGE[0]:g}-{RANGE[1]:g} mL/min); the split is an extrapolation.')
    if 30.0 <= crcl < 50.0:
        warnings.append('In moderate impairment (30-50 mL/min) the check found renal elimination lower than this reading '
                        'predicts: the true renal share is probably smaller and exposure higher than shown.')
    if crcl < 30.0:
        warnings.append('Severe impairment: the reading was consistent with the severe group mean, but that group had only 6 subjects.')
    total = p['total_ml_min']
    view.update(
        status='completed', crcl_ml_min=crcl,
        range_status='within_reported_range' if RANGE[0] <= crcl <= RANGE[1] else 'outside_reported_range',
        pathways_ml_min={k: p[k] for k in ('filtration_ml_min', 'secretion_ml_min', 'non_renal_ml_min', 'renal_ml_min', 'total_ml_min')},
        shares={'filtration': p['filtration_ml_min'] / total, 'secretion': p['secretion_ml_min'] / total,
                'non_renal': p['non_renal_ml_min'] / total},
        fraction_excreted_unchanged=p['fe'],
        normal_reference={'crcl_ml_min': CALIBRATION_CRCL, 'total_ml_min': normal['total_ml_min'], 'fe': normal['fe'],
                          'shares': {'filtration': normal['filtration_ml_min'] / normal['total_ml_min'],
                                     'secretion': normal['secretion_ml_min'] / normal['total_ml_min'],
                                     'non_renal': normal['non_renal_ml_min'] / normal['total_ml_min']}},
        relative_exposure_same_dose=normal['total_ml_min'] / total,
        warnings=warnings,
        limitations=[
            'Typical values from group means of 5-7 subjects per renal-function group; real patients vary widely.',
            'Creatinine clearance is estimated from serum creatinine here; the calibration study measured it from urine.',
            'Non-renal clearance is held constant; the moderate group of the check suggests it may not be.',
            'Bioavailability is taken as 1; the transporters behind secretion are not identified in the source.',
            'Not a measurement of renal function, an exposure prediction for this patient, or a dose recommendation.'])
    view['report_sha256'] = digest(view)
    return view
