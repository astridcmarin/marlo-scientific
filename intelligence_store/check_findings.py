"""What the checks found: every locked check on the platform in one line, failures included.

Reads the pinned findings file (one line per check report, written from the reports and scorecard summaries) and joins
the dataset ledger, which says whether each check was blind. Nothing is computed. The view refuses to build if a
findings line points at a report that has changed, or if the ledger lists a report with no findings line.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from .dataset_ledger import BLIND_ROLES, LEDGER_SHA256, load_ledger
from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
FINDINGS_PATH = Path(__file__).parent / 'data' / 'check_findings_v3.json'
FINDINGS_SHA256 = '39cda90c1ebb6afa80d9dbb47a66ddb98acb20dac2f3e5bcf4f4a05ea3f40332'
# Superseded, kept unchanged: check_findings_v2.json (v3 adds 2.0e)
FINDINGS_V2_SHA256 = 'b9beb8a6f1b9d50837fcfae4a96850fa8e006cfed12563d9a43236cdc7f3919b'
# Superseded, kept unchanged for traceability: check_findings_v1.json (two headlines corrected in v2)
FINDINGS_V1_SHA256 = '6f7ecdbfa2991d94a87588711f4eb029dd50d6573a5fd07968738d7014f7b0b8'
TONE = {'consistent': 'ok', 'passed': 'ok', 'mixed': 'warn', 'not_adopted': 'warn', 'inconclusive': 'neutral',
        'disagrees': 'gap', 'failed': 'gap'}
BLINDNESS_LABEL = {'checked_blind': 'Blind', 'checked_blind_with_deviation': 'Blind, with a recorded deviation',
                   'checked_not_blind': 'Not blind: data seen before the plan', 'tuned_on': 'Not blind: data seen before the plan',
                   'built_from': 'Not blind: data seen before the plan',
                   'reproduction': "Reproduction: the model's own source data", 'compared_model_to_model': 'Model to model'}
BLINDNESS_ORDER = ('checked_blind', 'checked_blind_with_deviation', 'compared_model_to_model', 'reproduction',
                   'checked_not_blind', 'tuned_on', 'built_from')


class FindingsError(ValueError):
    pass


def load_findings():
    raw = FINDINGS_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FINDINGS_SHA256:
        raise FindingsError('The findings file is missing or changed; a change needs a new version.')
    return json.loads(raw)


def _blindness(report, ledger):
    roles = {u['role'] for u in ledger['uses'] if u['report'] == report}
    role = next((r for r in BLINDNESS_ORDER if r in roles), None)
    if role is None:
        raise FindingsError(f'{report} is not in the dataset ledger.')
    return role


def findings_view():
    doc, ledger = load_findings(), load_ledger()
    listed = {f['report'] for f in doc['findings']}
    missing = {u['report'] for u in ledger['uses'] if u['report']} - listed
    if missing:
        raise FindingsError(f'Checks in the dataset ledger without a findings line: {sorted(missing)}')
    rows = []
    for f in doc['findings']:
        path = ROOT / f['report']
        intact = path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == f['report_file_sha256']
        if not intact:
            raise FindingsError(f"{f['report']} is missing or changed since its findings line was written.")
        role = _blindness(f['report'], ledger)
        rows.append(dict(f, tone=TONE[f['outcome']], outcome_label=doc['outcomes'][f['outcome']], blindness=role,
                         blindness_label=BLINDNESS_LABEL[role], blind=role in BLIND_ROLES, report_name=Path(f['report']).name))
    areas = []
    for area in dict.fromkeys(r['area'] for r in rows):
        items = sorted((r for r in rows if r['area'] == area), key=lambda r: r['date'])
        areas.append({'area': area, 'rows': items})
    counts = Counter(r['tone'] for r in rows)
    view = {'schema_version': 'check-findings-view-v1', 'findings_version': doc['findings_version'], 'findings_sha256': FINDINGS_SHA256,
            'ledger_sha256': LEDGER_SHA256, 'purpose': doc['purpose'], 'total': len(rows),
            'counts': {'ok': counts['ok'], 'warn': counts['warn'], 'gap': counts['gap'], 'neutral': counts['neutral']},
            'blind': sum(r['blind'] for r in rows), 'areas': areas, 'outcomes': doc['outcomes']}
    view['view_sha256'] = digest(view)
    return view
