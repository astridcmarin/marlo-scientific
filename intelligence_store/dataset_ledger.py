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
LEDGER_PATH = Path(__file__).parent / 'data' / 'dataset_ledger_v1.json'
LEDGER_SHA256 = '8767ee2ca0f8e6f9078bfb1e2c8451d9bfde04081e74a76482aea5eb4e8ee39f'
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


def blind_check_problems(model, dataset_id, ledger=None):
    """Reasons a blind check of `model` against `dataset_id` is not possible; empty if it is."""
    ledger = ledger or load_ledger()
    problems = []
    if is_seen(dataset_id, ledger):
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
