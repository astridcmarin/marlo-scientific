"""Phase 1.1: public model scorecards.

One page per registered model, saying in plain words what the model is, where the platform uses it, and what has
and has not been checked about it, including recorded failures. Every check status, summary and report reference is
copied from the pinned model evidence status file (the same one every run record cites). This module adds only
plain-language labels and the description of where each model is used; it computes nothing.
"""
import hashlib
from pathlib import Path

from .run_record import EVIDENCE_SHA256, LAYER_ORDER, load_evidence_status

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = 'docs/verification/'
NOT_ESTABLISHED = 'No model on the platform is validated for clinical prediction. Passing every check supports research use only.'

LAYER_LABELS = {
    'software_verification': 'Code computes the intended equations',
    'transcription_verification': 'Values checked against the source',
    'reproduction': 'Reproduces the data it was built on',
    'external_consistency': 'Compared with outside data',
}

# status in the evidence file -> (plain label, tone used for colour: ok | part | gap | neutral)
STATUS_LABELS = {
    'done': ('Done', 'ok'),
    'done_with_open_question': ('Done, with an open question', 'part'),
    'done_exploratory': ('Exploratory', 'part'),
    'partial': ('Partly', 'part'),
    'by_design': ('By design, not evidence', 'neutral'),
    'not_done': ('Not done', 'gap'),
}

# Structured outside-data results already recorded in the evidence file.
OUTCOME_LABELS = {'consistent': ('Consistent', 'ok'), 'model_over_predicts': ('Model too high', 'gap'),
                  'model_under_predicts': ('Model too low', 'gap')}
RESULT_ITEMS = {
    'mild': 'Mild kidney impairment', 'moderate': 'Moderate kidney impairment', 'severe': 'Severe kidney impairment',
    'auc_day1': 'Day 1 exposure (AUC), 1.3 mg/m², Ogawa 2008', 'auc_day11': 'Day 11 exposure (AUC), 1.3 mg/m², Ogawa 2008',
    'auc_ratio_day11_over_day1': 'Rise in exposure from day 1 to day 11, 1.3 mg/m², Ogawa 2008',
    'can1004_auc_last_day1': 'Day 1 exposure (AUC to 72 h), 1.3 mg/m², CAN-1004',
    'can1004_auc_last_day11': 'Day 11 exposure (AUC to 72 h), 1.3 mg/m², CAN-1004',
    'mmy3021_auc_last_day11': 'Day 11 exposure (AUC to 72 h), 1.3 mg/m², MMY-3021 (not robust to the AUC rule)',
    'mmy3021_cmax_day11': 'Day 11 peak concentration, 1.3 mg/m², MMY-3021',
}
RESULT_ITEMS.update({
    'renal.normal.auc_last': 'Exposure (AUC), MM with normal kidney function, 3 mg',
    'renal.severe_ri.auc_last': 'Exposure (AUC), severe kidney impairment, 3 mg',
    'renal.esrd.auc_last': 'Exposure (AUC), kidney failure on dialysis, 3 mg',
    'hepatic.normal.auc_last': 'Exposure (AUC), solid tumours with normal liver function, 4 mg',
    'hepatic.moderate.auc_last': 'Exposure (AUC), moderate liver impairment, 2.3 mg',
    'hepatic.severe.auc_last': 'Exposure (AUC), severe liver impairment, 1.5 mg',
    'peak_concentration_five_of_six_groups': 'Peak concentration (five of six groups)',
    'sirius_8.cmax': 'Peak after the first infusion, 8 mg/kg, SIRIUS',
    'sirius_8.auc_inf': 'Exposure (AUC to infinity), 8 mg/kg, SIRIUS',
    'gen501_16.cmax': 'Peak after the first infusion, 16 mg/kg, GEN501',
    'gen501_16.auc_0_7d': 'First-week exposure, 16 mg/kg, GEN501',
})
RESULT_ITEMS.update({'v2.' + k: v + ' (with study demographics)' for k, v in list(RESULT_ITEMS.items())
                     if k.startswith(('sirius_8.', 'gen501_16.'))})
RESULT_KEYS = ('result_by_group', 'result_at_1_3_mg_m2', 'result_by_endpoint')

# What each model is and where the platform uses it. Descriptions only; no scientific values.
PROFILES = {
    'lenalidomide_hughes_2019': {
        'drug': 'Lenalidomide', 'kind': 'Exposure (population PK)',
        'what': 'A published population pharmacokinetic model. Given age, sex, body size and kidney function, it gives the typical concentration curve after a dose.',
        'used_on': [('Patient Lab: educational PK from a patient record, published-model comparison and population band', 'landscape.patient_directory')],
    },
    'lenalidomide_kim_2026': {
        'drug': 'Lenalidomide', 'kind': 'Exposure (population PK)',
        'what': 'A published population pharmacokinetic model fitted in multiple myeloma patients with kidney impairment, using eGFR and body surface area.',
        'used_on': [('Patient Lab: published-model comparison and saved Kim 2026 runs', 'landscape.patient_directory')],
    },
    'lenalidomide_renal_pathways_2026': {
        'drug': 'Lenalidomide', 'kind': 'Elimination pathways',
        'what': 'A platform model that splits clearance into kidney filtration, tubular secretion and non-renal routes, calibrated on people with normal kidney function.',
        'used_on': [('Patient Lab: elimination pathways for a patient record', 'landscape.patient_directory'),
                    ('Published renal PK evidence', 'landscape.renal_pk_evidence')],
    },
    'lenalidomide_exposure_safety_2016': {
        'drug': 'Lenalidomide', 'kind': 'Safety signal (relative odds)',
        'what': 'Published odds ratios linking exposure to grade 3/4 low platelet and neutrophil counts, used to show relative odds at a simulated exposure. Relative, not a probability.',
        'used_on': [('Patient Lab: relative odds in the published-model comparison', 'landscape.patient_directory')],
    },
    'bortezomib_pk_lignet_2022': {
        'drug': 'Bortezomib', 'kind': 'Exposure (PK)',
        'what': 'A three-compartment pharmacokinetic model with a single, constant clearance. It drives the platelet model below.',
        'used_on': [('Simulation Lab: bortezomib platelet course', 'landscape.bortezomib_platelets')],
    },
    'ixazomib_pk_gupta_2017': {
        'drug': 'Ixazomib', 'kind': 'Exposure (population PK)',
        'what': 'A published population pharmacokinetic model of oral ixazomib. The platform uses it only for typical total exposure, inside a declared scope (myeloma, kidney and liver function inside the model\'s data); peak concentrations are not shown.',
        'used_on': [('Ixazomib exposure page (inside the model scope only)', 'landscape.ixazomib_exposure_page')],
    },
    'daratumumab_pk_luo_2021': {
        'drug': 'Daratumumab', 'kind': 'Exposure (population PK)',
        'what': 'A published population pharmacokinetic model of daratumumab with linear and saturable (target-mediated) clearance. Implemented and checked, but not used on any result page yet; its scope records what a future page may show.',
        'used_on': [],
    },
    'bortezomib_platelets_lignet_2022': {
        'drug': 'Bortezomib', 'kind': 'Effect (platelet time course)',
        'what': 'A published model of how platelet counts fall and recover during bortezomib cycles, scaled to a patient\'s starting count.',
        'depends_on': ['bortezomib_pk_lignet_2022'],
        'used_on': [('Simulation Lab: bortezomib platelet course', 'landscape.bortezomib_platelets'),
                    ('Patient Lab: platelet curve for a patient record', 'landscape.patient_directory')],
    },
}


def _matches(raw, sha256):
    return hashlib.sha256(raw).hexdigest() == sha256


def _cited(evidence=None):
    """{file name: (repository path, pinned sha256)} for every report the evidence file cites."""
    evidence = evidence or load_evidence_status()
    cited = {}
    for model in evidence['models'].values():
        for layer in model['layers'].values():
            for ref in [layer] + list(layer.get('further_reports', [])):
                if ref.get('evidence_report'):
                    cited[Path(ref['evidence_report']).name] = (ref['evidence_report'], ref['evidence_report_file_sha256'])
    return cited


def cited_report(name, evidence=None):
    """Raw bytes of a cited report, or None if it is not cited, not under docs/verification, or changed."""
    entry = _cited(evidence).get(name)
    if entry is None or not entry[0].startswith(REPORT_DIR) or Path(entry[0]).name != name:
        return None
    path = ROOT / entry[0]
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return raw if _matches(raw, entry[1]) else None


def _report(path, sha256):
    file = ROOT / path
    intact = file.is_file() and _matches(file.read_bytes(), sha256)
    return {'path': path, 'name': Path(path).name, 'sha256': sha256, 'intact': intact}


def _layer(name, entry, descriptions):
    label, tone = STATUS_LABELS.get(entry['status'], (entry['status'].replace('_', ' '), 'neutral'))
    reports = []
    if entry.get('evidence_report'):
        reports.append(dict(_report(entry['evidence_report'], entry['evidence_report_file_sha256']), summary=None))
    for extra in entry.get('further_reports', []):
        reports.append(dict(_report(extra['evidence_report'], extra['evidence_report_file_sha256']), summary=extra['summary']))
    results = []
    recorded = [(item, outcome) for key in RESULT_KEYS for item, outcome in (entry.get(key) or {}).items()]
    recorded += [(item, outcome) for extra in entry.get('further_reports', []) for item, outcome in (extra.get('results') or {}).items()]
    for item, outcome in recorded:
        outcome_label, outcome_tone = OUTCOME_LABELS.get(outcome, (outcome.replace('_', ' '), 'neutral'))
        results.append({'item': RESULT_ITEMS.get(item, item.replace('_', ' ')), 'outcome': outcome,
                        'outcome_label': outcome_label, 'tone': outcome_tone})
    search = entry.get('search')
    return {'id': name, 'label': LAYER_LABELS[name], 'definition': descriptions[name], 'status': entry['status'],
            'status_label': label, 'tone': tone, 'summary': entry['summary'], 'classification': entry.get('classification'),
            'reports': reports, 'results': results,
            'search': ({'searched_on': search.get('searched_on'), 'candidates': search.get('candidates', [])} if search else None)}


def scorecard(model_id, evidence=None):
    evidence = evidence or load_evidence_status()
    if model_id not in evidence['models']:
        raise KeyError(model_id)
    entry = evidence['models'][model_id]
    profile = PROFILES.get(model_id, {'drug': '', 'kind': '', 'what': '', 'used_on': []})
    layers = [_layer(name, entry['layers'][name], evidence['layers']) for name in LAYER_ORDER]
    return {'model_id': model_id, 'name': entry['name'], 'citation': entry['citation'], 'doi': entry['doi'],
            'drug': profile['drug'], 'kind': profile['kind'], 'what': profile['what'], 'used_on': profile['used_on'],
            'layers': layers,
            'outside_data_disagreements': [r for layer in layers for r in layer['results'] if r['tone'] == 'gap'],
            'counts': {tone: sum(1 for layer in layers if layer['tone'] == tone) for tone in ('ok', 'part', 'gap', 'neutral')},
            'depends_on': [{'model_id': d, 'name': evidence['models'][d]['name'],
                            'disagreements': len(scorecard(d, evidence)['outside_data_disagreements'])}
                           for d in profile.get('depends_on', [])],
            'never_established': NOT_ESTABLISHED,
            'clinical_prediction_validated': False}


def all_scorecards():
    evidence = load_evidence_status()
    cards = [scorecard(model_id, evidence) for model_id in evidence['models']]
    cards.sort(key=lambda c: (c['drug'], c['kind'], c['name']))
    return {'cards': cards, 'status_version': evidence['status_version'], 'evidence_sha256': EVIDENCE_SHA256,
            'recorded_on': evidence['recorded_on'], 'layers': [(n, LAYER_LABELS[n], evidence['layers'][n]) for n in LAYER_ORDER],
            'never_established': NOT_ESTABLISHED}
