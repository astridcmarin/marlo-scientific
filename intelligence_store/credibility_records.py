"""Phase 6.1: model credibility records in the structure of ICH M15 (General Principles for Model-Informed Drug
Development; ICH Step 4, January 2026).

One record per model, assembled from pinned sources only:
- the M15 assessment elements (question of interest, context of use, model influence, consequence of a wrong decision,
  model risk, model impact), the assumptions and the rejected alternatives: model_credibility_context_v1.json (pinned);
- verification and validation: the model evidence status file (pinned; the same one every run record cites) or, for
  label-based curves, their locked reports;
- the Model Analysis Plans: the locked plan files, each with its checksum and whether code pins it;
- applicability and limitations: copied from the pinned model extracts and plans, not rewritten.
The record computes nothing scientific. It is exported as JSON with its own checksum.
"""
import hashlib
import json
import re
from pathlib import Path

from .covariate_estimation import _load_pinned
from .model_scorecards import LAYER_LABELS, NOT_ESTABLISHED, STATUS_LABELS
from .patient_state import digest
from .run_record import EVIDENCE_SHA256, LAYER_ORDER, load_evidence_status

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
CONTEXT_PATH = DATA / 'model_credibility_context_v1.json'
CONTEXT_SHA256 = '740f68767f4a6d384b7e746b5b0bd3e0ee53c728d84d3a4d456b801f8ade15a6'
SCHEMA_VERSION = 'model-credibility-record-v1'
LEVEL_LABELS = {'low': 'Low', 'medium': 'Medium', 'high': 'High', 'low_within_intended_use': 'Low (within the intended use)',
                'not_applicable': 'Not applicable'}


def load_context(path=CONTEXT_PATH):
    return _load_pinned(path, CONTEXT_SHA256, 'model-credibility-context-v1', 'Model credibility context')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pinned_in_code(sha):
    """True if some module under intelligence_store pins this checksum (i.e. the file cannot change silently)."""
    for module in (ROOT / 'intelligence_store').glob('*.py'):
        if sha in module.read_text(encoding='utf-8'):
            return True
    return False


def _plan(name):
    path = DATA / name
    plan = json.loads(path.read_text(encoding='utf-8'))
    sha = _sha(path)
    return {'file': f'intelligence_store/data/{name}', 'plan_version': plan.get('plan_version'), 'recorded_on': plan.get('recorded_on'),
            'status': plan.get('status'), 'question': plan.get('question'), 'sha256': sha, 'pinned_in_code': _pinned_in_code(sha)}


def _report_ref(path):
    file = ROOT / path
    report = json.loads(file.read_text(encoding='utf-8'))
    decision = report.get('decision')
    return {'file': path, 'sha256': _sha(file), 'report_sha256': report.get('report_sha256'),
            'plan_version': report.get('plan_version'), 'decision': decision}


def _excerpt(name, key):
    data = json.loads((DATA / name).read_text(encoding='utf-8'))
    return {'source': f'intelligence_store/data/{name}', 'field': key, 'content': data.get(key)}


def _validation_from_evidence(model_id, evidence):
    entry = evidence['models'][model_id]
    layers = []
    for name in LAYER_ORDER:
        layer = entry['layers'][name]
        reports = [{'file': layer['evidence_report'], 'sha256': layer['evidence_report_file_sha256']}] if layer.get('evidence_report') else []
        reports += [{'file': r['evidence_report'], 'sha256': r['evidence_report_file_sha256'], 'summary': r.get('summary')}
                    for r in layer.get('further_reports', [])]
        layers.append({'layer': name, 'label': LAYER_LABELS[name], 'status': layer['status'],
                       'status_label': STATUS_LABELS.get(layer['status'], (layer['status'], ''))[0],
                       'summary': layer['summary'], 'classification': layer.get('classification'), 'reports': reports})
    return {'source': f'intelligence_store/data/model_evidence_status_v6.json (sha256 {EVIDENCE_SHA256})', 'layers': layers,
            'name': entry['name'], 'citation': entry['citation'], 'doi': entry.get('doi')}


def _validation_from_reports(ctx):
    reports = [_report_ref(p) for p in ctx['sources'].get('reports', [])]
    layers = [{'layer': 'software_verification', 'label': LAYER_LABELS['software_verification'], 'status': 'done',
               'status_label': 'Done', 'summary': 'Numerical solution checked against closed forms (superposition, AUC, Tmax) in the locked consistency report, section numerical_checks.',
               'reports': reports[:1]},
              {'layer': 'transcription_verification', 'label': LAYER_LABELS['transcription_verification'], 'status': 'partial',
               'status_label': 'Partly', 'summary': 'Label values extracted with the sentence they come from; independent review pending.', 'reports': []},
              {'layer': 'reproduction', 'label': 'Reproduces the label it was built from', 'status': 'done', 'status_label': 'Done',
               'summary': 'Locked internal-consistency check against the label (see report).', 'reports': reports[:1]},
              {'layer': 'external_consistency', 'label': LAYER_LABELS['external_consistency'], 'status': 'done_exploratory',
               'status_label': 'Exploratory', 'summary': ctx.get('external_consistency_summary', 'Locked outside check (see report).'),
               'reports': reports[1:]}]
    return {'source': 'locked label-exposure reports', 'layers': layers}


def record(model_id, context=None, evidence=None):
    context = context or load_context()
    if model_id not in context['models']:
        raise KeyError(model_id)
    ctx = context['models'][model_id]
    evidence = evidence or load_evidence_status()
    validation = _validation_from_evidence(model_id, evidence) if model_id in evidence['models'] else _validation_from_reports(ctx)
    rejected = []
    for alt in ctx.get('alternatives_rejected', []):
        rejected.append(dict(alt, plan=_plan(alt['plan']), report=_report_ref(alt['report'])))
    rec = {
        'schema_version': SCHEMA_VERSION, 'model_id': model_id, 'drug': ctx['drug'], 'kind': ctx['kind'],
        'name': validation.get('name') or f"{ctx['drug'].capitalize()} label-based exposure curve",
        'citation': validation.get('citation'), 'doi': validation.get('doi'),
        'framework': context['framework'],
        'assessment': {
            'question_of_interest': ctx['question_of_interest'],
            'context_of_use': ctx['context_of_use'],
            'model_influence': ctx['model_influence'],
            'consequence_of_wrong_decision': ctx['consequence_of_wrong_decision'],
            'model_risk': ctx['model_risk'],
            'model_impact': ctx['model_impact'],
        },
        'model_analysis_plans': [_plan(p) for p in ctx['sources']['plans']],
        'evaluation': {'verification_and_validation': validation['layers'], 'source': validation['source']},
        'applicability': [_excerpt(*a) for a in ctx['applicability_from']],
        'assumptions': ctx['assumptions'],
        'limitations': [_excerpt(*l) for l in ctx['limitations_from']],
        'alternatives_considered_and_rejected': rejected,
        'source_extracts': [{'file': f'intelligence_store/data/{e}', 'sha256': _sha(DATA / e), 'pinned_in_code': _pinned_in_code(_sha(DATA / e))}
                            for e in ctx['sources']['extracts']],
        'never_established': NOT_ESTABLISHED,
        'clinical_prediction_validated': False,
        'context_sha256': CONTEXT_SHA256,
    }
    rec['record_sha256'] = digest(rec)
    return rec


def all_records():
    context = load_context()
    evidence = load_evidence_status()
    return [record(m, context, evidence) for m in context['models']]


def model_ids():
    return list(load_context()['models'])


def level_label(level):
    return LEVEL_LABELS.get(level, re.sub('_', ' ', level))
