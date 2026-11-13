"""Which datasets each model was built from, tuned on or checked against, and whether each check was blind.

The ledger (dataset_ledger_v1.json, pinned here) is the platform's overview of what has been seen. A dataset whose values
anyone working on the platform has read can no longer give a blind check, for any model. `assert_blind_allowed` is the
gate future check plans call before claiming a blind check; `validate_plan_datasets` applies it to a plan that declares
its datasets.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = Path(__file__).parent / 'data' / 'dataset_ledger_v8.json'
LEDGER_SHA256 = '4f10d2d3879b5819bb468a7dba50ba75c210cd95e8d8456e4114884d31f448f8'
# Superseded, kept unchanged for traceability: dataset_ledger_v7.json
LEDGER_V7_SHA256 = '90a8eece3161a3bac678aaaf22b97b5d59aa73c58e983ad758c81e64c22c9230'
# Superseded, kept unchanged for traceability: dataset_ledger_v6.json
LEDGER_V6_SHA256 = '369f47a18a1431bfe5a50a6523d58832783aee2912a6a5f7daf22ffe2d3e06af'
# Superseded, kept unchanged for traceability: dataset_ledger_v5.json
LEDGER_V5_SHA256 = '5041737e9f8139d6a337049578edf5d664037b8f31f361988c0ad7768d65f455'
# Superseded, kept unchanged for traceability: dataset_ledger_v4.json
LEDGER_V4_SHA256 = '0f9216387ca471dda8dc156e1587079c07ef244e96e116b791672f17ea7a2ef4'
# Superseded, kept unchanged for traceability: dataset_ledger_v3.json
LEDGER_V3_SHA256 = '2a2d21e95f0e636a763d86b0246400dd2e4f87467776fe06fa7df24d48cc4ad3'
# Superseded, kept unchanged for traceability: dataset_ledger_v2.json
LEDGER_V2_SHA256 = '2b028a9af4a195e070c83dfaf8da7442652ca9e0f0338a3e08b293ba4aa85846'
# Superseded, kept unchanged for traceability: dataset_ledger_v1.json
LEDGER_V1_SHA256 = '8767ee2ca0f8e6f9078bfb1e2c8451d9bfde04081e74a76482aea5eb4e8ee39f'
SCHEMA_VERSION = 'dataset-ledger-v1'
BLIND_ROLES = ('checked_blind', 'checked_blind_with_deviation')
EXPOSING_ROLES = ('built_from', 'tuned_on', 'reproduction')


class LedgerError(ValueError):
    pass


def load_ledger(path=LEDGER_PATH, sha256=LEDGER_SHA256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise LedgerError('The dataset ledger is missing or changed; a change needs a new version.')
    ledger = json.loads(raw)
    if ledger.get('schema_version') != SCHEMA_VERSION:
        raise LedgerError('Not a dataset ledger.')
    roles, datasets = set(ledger['roles']), ledger['datasets']
    for use in ledger['uses']:
        if use['role'] not in roles:
            raise LedgerError(f"Unknown role {use['role']}.")
        if use['dataset'] not in datasets:
            raise LedgerError(f"Unknown dataset {use['dataset']}.")
    return ledger


def is_seen(dataset_id, ledger=None):
    ledger = ledger or load_ledger()
    if dataset_id not in ledger['datasets']:
        raise LedgerError(f'Dataset {dataset_id} is not in the ledger; add it before planning a check.')
    return ledger['datasets'][dataset_id]['values_first_seen'] is not None


def model_uses(model, ledger=None):
    ledger = ledger or load_ledger()
    return [u for u in ledger['uses'] if u['model'] == model]


def _reserved_before_seen(model, dataset_id, ledger):
    """True when the model holds a reserved_for_blind_check use of the dataset whose plan was recorded on or before the
    day the dataset's values were first seen (12 November 2026: the eligibility v2 sample was scored for extractor v1.1
    after the Track C plan and prompt were locked). The same date test the completed blind checks must pass."""
    from datetime import date
    seen = ledger['datasets'][dataset_id]['values_first_seen']
    for u in model_uses(model, ledger):
        if u['dataset'] == dataset_id and u['role'] == 'reserved_for_blind_check' and u.get('plan'):
            plan = json.loads((Path(__file__).resolve().parent.parent / u['plan']).read_text())
            if date.fromisoformat(plan['recorded_on']) <= date.fromisoformat(seen):
                return True
    return False


def blind_check_problems(model, dataset_id, ledger=None):
    """Reasons a blind check of `model` against `dataset_id` is not possible; empty if it is."""
    ledger = ledger or load_ledger()
    problems = []
    if is_seen(dataset_id, ledger) and not _reserved_before_seen(model, dataset_id, ledger):
        d = ledger['datasets'][dataset_id]
        problems.append(f"{dataset_id} values were first seen on {d['values_first_seen']}: {d['seen_note']}")
    for u in model_uses(model, ledger):
        if u['dataset'] == dataset_id and u['role'] in EXPOSING_ROLES:
            problems.append(f"{model} was {u['role'].replace('_', ' ')} {dataset_id}.")
    return problems


def assert_blind_allowed(model, dataset_id, ledger=None):
    problems = blind_check_problems(model, dataset_id, ledger)
    if problems:
        raise LedgerError('A blind check is not possible: ' + ' '.join(problems))


def validate_plan_datasets(plan, ledger=None):
    """For a plan that declares {'model', 'datasets': [{'id', 'role'}]}: refuse any blind role on a seen dataset."""
    ledger = ledger or load_ledger()
    for d in plan.get('datasets', []):
        if d['role'] not in ledger['roles']:
            raise LedgerError(f"Unknown role {d['role']}.")
        if d['role'] in BLIND_ROLES or d['role'] == 'reserved_for_blind_check':
            assert_blind_allowed(plan['model'], d['id'], ledger)
    return plan


def summary(ledger=None):
    """Per dataset: whether seen, and every model's use of it; per model: its uses. For pages and reports."""
    ledger = ledger or load_ledger()
    datasets = []
    for did, d in ledger['datasets'].items():
        uses = [u for u in ledger['uses'] if u['dataset'] == did]
        datasets.append({'id': did, 'title': d['title'], 'seen': d['values_first_seen'] is not None,
                         'values_first_seen': d['values_first_seen'], 'seen_note': d['seen_note'], 'uses': uses,
                         'available_for_blind_check': d['values_first_seen'] is None})
    blind = [u for u in ledger['uses'] if u['role'] in BLIND_ROLES]
    return {'ledger_version': ledger['ledger_version'], 'ledger_sha256': LEDGER_SHA256, 'datasets': datasets,
            'blind_checks': blind, 'unseen_datasets': [d['id'] for d in datasets if not d['seen']]}
