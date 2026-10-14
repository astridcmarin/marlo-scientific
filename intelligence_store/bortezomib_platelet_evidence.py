"""Simulation 3.0a: pinned evidence for the bortezomib platelet time-course model (Lignet 2022).

Transcription and observed reference values only; the engine and the locked reproduction check come
next. Nothing here runs a simulation.
"""
from pathlib import Path

from .covariate_estimation import _load_pinned

DATA = Path(__file__).parent / 'data'
EXTRACT_PATH = DATA / 'bortezomib_platelet_model_extract_v1.json'
EXTRACT_SHA256 = '3093fff25dbf44a75aa31b4d41d40d57eabc5cf29ce21c7718276edf8a028e84'
OBSERVED_PATH = DATA / 'bortezomib_platelet_observed_v1.json'
OBSERVED_SHA256 = '7ada11d52455cab9aa9576c68461e7230028979584d468427e95966dec7e6fd6'
PEDIATRIC_BSA_M2 = 1.30
ADULT_BSA_M2 = 1.62
PARAMETER_PAIRS = (('clearance_l_h_m2', 'clearance_l_h'), ('central_volume_l_m2', 'central_volume_l'),
                   ('q2_l_h_m2', 'q2_l_h'), ('peripheral_volume_2_l_m2', 'peripheral_volume_2_l'),
                   ('q3_l_h_m2', 'q3_l_h'), ('peripheral_volume_3_l_m2', 'peripheral_volume_3_l'))


def load_model_extract(path=EXTRACT_PATH):
    return _load_pinned(path, EXTRACT_SHA256, 'pd-model-extract-v1', 'Bortezomib platelet model extract')


def load_observed_summary(path=OBSERVED_PATH):
    return _load_pinned(path, OBSERVED_SHA256, 'observed-summary-v1', 'Bortezomib platelet observed summary')


def check_pk_scaling(extract=None):
    """Recompute each published per-m2 adult parameter from the pediatric value: P/1.30 x (1.62/1.30)."""
    pk = (extract or load_model_extract())['pk_model']
    rows = []
    for adult_key, pediatric_key in PARAMETER_PAIRS:
        published = pk['parameters_per_m2'][adult_key]
        recomputed = pk['pediatric_source_values'][pediatric_key] / PEDIATRIC_BSA_M2 * (ADULT_BSA_M2 / PEDIATRIC_BSA_M2)
        rows.append({'parameter': adult_key, 'published': published, 'recomputed': recomputed,
                     'relative_difference': abs(recomputed - published) / published})
    return rows
