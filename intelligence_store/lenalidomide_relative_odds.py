"""Simulation 4.0a: relative odds of grade 3/4 cytopenia from a patient's simulated lenalidomide exposure.

Source: the sponsor's exposure-safety analysis CC-5013-MCL-001-PK as reported by the Australian TGA
(lenalidomide_exposure_safety_tga_v1.json). In myeloma, each one-unit increase in ln AUC multiplied the odds of
grade 3/4 thrombocytopenia by 2.972 (95% CI 1.027-8.598), adjusted for baseline platelet count. The intercept
was not published, so absolute risk cannot be computed.

What can be computed: for two patients with the same disease and baseline count, the odds ratio between them is
OR ** (ln AUC_1 - ln AUC_2) = (AUC_1 / AUC_2) ** ln(OR). Only the ratio of exposures enters, so AUC units and any
constant scale factor cancel. Here AUC_1 is the patient's typical daily AUC from a published PK model and AUC_2 the
measured mean after 25 mg in subjects with normal renal function (lenalidomide_reference_exposure_v1.json).
"""
import math
from pathlib import Path

from .covariate_estimation import _load_pinned

EVIDENCE_PATH = Path(__file__).parent / 'data' / 'lenalidomide_exposure_safety_tga_v1.json'
EVIDENCE_SHA256 = '7be5103a41a5c8f5fe2529d524951c1a94db8c4996c81299a364b84c51288b8c'
METHOD_VERSION = 'lenalidomide-relative-odds-v1.0'
ENDPOINTS = ('grade_3_4_thrombocytopenia', 'grade_3_4_neutropenia')
MEANING = ('Relative odds versus the reference exposure (mean AUC after 25 mg with normal renal function), for a patient '
           'with the same disease and baseline count. Not a probability: the same relative odds can mean a small or a '
           'large change in risk, and the baseline risk is not known here.')


def load_evidence(path=EVIDENCE_PATH):
    return _load_pinned(path, EVIDENCE_SHA256, 'exposure-safety-evidence-v1', 'Lenalidomide exposure-safety evidence')


def relative_odds(auc_ratio, odds_ratio, ci95):
    """(auc_ratio) ** ln(OR), with the CI carried through. For ratios below 1 the CI limits swap, so min/max is used."""
    if not (isinstance(auc_ratio, (int, float)) and math.isfinite(auc_ratio) and auc_ratio > 0):
        raise ValueError('Exposure ratio must be a finite positive number.')
    values = [auc_ratio ** math.log(v) for v in (odds_ratio, *ci95)]
    return {'relative_odds': values[0], 'ci95': [min(values[1:]), max(values[1:])], 'exponent': math.log(odds_ratio)}


def relative_odds_for_exposure(ratio_to_reference, evidence=None):
    evidence = evidence or load_evidence()
    out = {'method_version': METHOD_VERSION, 'evidence_version': evidence['evidence_version'],
           'evidence_sha256': EVIDENCE_SHA256, 'ratio_to_reference': ratio_to_reference, 'meaning': MEANING,
           'endpoints': {}, 'clinical_prediction_validated': False}
    for name in ENDPOINTS:
        e = evidence['odds_ratios_multiple_myeloma'][name]
        out['endpoints'][name] = dict(relative_odds(ratio_to_reference, e['odds_ratio_per_unit_ln_auc'], e['ci95']),
                                      odds_ratio_per_unit_ln_auc=e['odds_ratio_per_unit_ln_auc'],
                                      source_ci95=list(e['ci95']), statistically_significant=e['statistically_significant'],
                                      adjusted_for=e['adjusted_for'])
    return out
