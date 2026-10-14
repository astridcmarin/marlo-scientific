"""Patient Lab 2.1e: simulated daily exposure as a ratio to a measured reference exposure.

The reference is the mean AUC measured after the approved 25 mg starting dose in subjects with
normal renal function (CC-5013-PK-001). The ratio is context for reading a simulated curve; it
carries no target, limit, toxicity prediction or dose recommendation.
"""
import math
from pathlib import Path

from .covariate_estimation import _load_pinned

REFERENCE_PATH = Path(__file__).parent / 'data' / 'lenalidomide_reference_exposure_v1.json'
REFERENCE_SHA256 = 'd49358f519956fd6b1fce52798d74424a753d4e669773324c18e471f82a180e1'
EVENT_INTERVAL_H = 24.0


def load_reference_exposure(path=REFERENCE_PATH):
    return _load_pinned(path, REFERENCE_SHA256, 'reference-exposure-v1', 'Lenalidomide reference exposure')


def average_daily_dose(canonical_request):
    """Mean amount per 24 h event of a validated request (events are at exact 24 h intervals)."""
    amounts = [e['amount']['value'] for e in canonical_request['events']]
    return math.fsum(amounts) / len(amounts)


def compare_to_reference(daily_dose_mg, total_clearance_l_h):
    """Typical daily AUC for this dose and clearance, as a ratio to the measured reference mean."""
    if not (math.isfinite(daily_dose_mg) and daily_dose_mg > 0 and math.isfinite(total_clearance_l_h)
            and total_clearance_l_h > 0):
        raise ValueError('Daily dose and clearance must be finite positive numbers.')
    data = load_reference_exposure()
    ref = data['reference']
    daily_auc = 1000.0 * daily_dose_mg / total_clearance_l_h
    return {'daily_dose_mg': daily_dose_mg, 'typical_daily_auc_ng_h_ml': daily_auc,
            'reference_auc_ng_h_ml': ref['value'], 'reference_sd_ng_h_ml': ref['sd'], 'reference_n': ref['n'],
            'reference_dose_mg': ref['dose_mg'], 'ratio_to_reference': daily_auc / ref['value'],
            'reference_version': data['reference_version'], 'reference_sha256': REFERENCE_SHA256,
            'meaning': ('Typical simulated daily AUC divided by the mean AUC measured after a single 25 mg dose in '
                        'subjects with normal renal function (n = 7). Context only: not a target, limit, toxicity '
                        'prediction or dose recommendation.')}
