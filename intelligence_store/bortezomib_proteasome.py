"""Isolated published equation component; never a patient-response model."""
import hashlib
import json
import math
from pathlib import Path

REFERENCE_PATH = Path(__file__).with_name('data') / 'bortezomib_proteasome_reference_v1.json'
REFERENCE_SHA256 = 'ac5e3ad9a9cb8156ca019ba0b9bf31956b96c973631e595ebafabdc4166b59be'
METHOD = 'bortezomib-proteasome-equation-component-v1.0'
MAX_POINTS = 1001
MAX_CONCENTRATION_NM = 1e6  # Computational bound, NOT an observed or clinical range.


def load_reference():
    try:
        raw = REFERENCE_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
            raise ValueError('Reference integrity mismatch; calculation unavailable.')
        return json.loads(raw)
    except OSError as exc:
        raise ValueError('Published equation reference is unavailable.') from exc


def calculate_proteasome_activity(*, plasma_concentrations_nm):
    """Independent hypothetical concentration points. No sorting, fitting or PK input."""
    if not isinstance(plasma_concentrations_nm, list) or not 1 <= len(plasma_concentrations_nm) <= MAX_POINTS:
        raise ValueError('Supply 1–1001 plasma concentrations in nM.')
    concentrations = []
    for value in plasma_concentrations_nm:
        if type(value) not in (int, float):
            raise ValueError('Concentrations must be numbers, not strings or Booleans.')
        try:
            number = float(value)
        except (OverflowError, ValueError):
            raise ValueError('Concentration cannot be represented.') from None
        if not math.isfinite(number) or not 0 <= number <= MAX_CONCENTRATION_NM:
            raise ValueError('Concentration must be finite and within 0–1000000 nM (computational limits).')
        concentrations.append(0.0 if number == 0 else number)
    if any(b <= a for a, b in zip(concentrations, concentrations[1:])):
        raise ValueError('Concentrations must be strictly increasing.')
    reference = load_reference()
    p = reference['parameters']
    points = []
    for c in concentrations:
        # Stable Hill evaluation even for positive subnormal inputs.
        if c == 0:
            fraction = 0.0
        else:
            z = p['hill_coefficient'] * (math.log(c) - math.log(p['ic50_nm']))
            if z >= 0:
                fraction = 1 / (1 + math.exp(-z))
            else:
                ez = math.exp(z)
                fraction = ez / (1 + ez)
        inhibition = p['maximum_inhibition_percentage_points'] * fraction
        points.append({'plasma_concentration_nm':c,
                       'activity_percent_of_baseline':p['baseline_percent']-inhibition,
                       'inhibition_percentage_points':inhibition})
    report = {
        'schema_version':'bortezomib-proteasome-calculation-v1', 'method_version':METHOD,
        'status':'published_equation_component_evaluated',
        'input_origin':'hypothetical_concentration_grid_not_observations',
        'concentration_domain_status':'source_observed_range_not_extracted; interpolation_or_extrapolation_not_assessed',
        'reference_sha256':REFERENCE_SHA256, 'reference':reference,
        'points':points, 'pk_coupling_status':'not_connected',
        'time_simulation_status':'not_run', 'patient_id':None,
        'efficacy_prediction':None, 'toxicity_prediction':None,
        'clinical_prediction_validated':False, 'ready_for_patient_simulation':False,
        'uncertainty_status':'not_propagated; outputs_are_not_prediction_intervals',
        'limitation':'Activity is not target occupancy, tumour response, survival or toxicity. '
                     'Source equation transcription and numerical tests do not validate patient predictions.'
    }
    report['report_sha256'] = hashlib.sha256(json.dumps(report,sort_keys=True,
        separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return report


def proteasome_example():
    return calculate_proteasome_activity(plasma_concentrations_nm=[0,0.179,1.79,17.9,179])
