"""The evidence index: connections between pinned files, models and checks, computed from what the files already state
(decision record docs/decisions/0001-evidence-index.md; plan docs/EVIDENCE_CONNECTIONS_PLAN.md, update 2).

Nothing is entered by hand and nothing is stored: every connection is read from a field of a pinned file, the dataset
ledger or the credibility context, and carries that field's location. A reference that does not resolve (missing file, or
a SHA-256 that does not match the file) is a finding, never skipped. Read-only; no database table.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'intelligence_store' / 'data'
VERIFICATION = ROOT / 'docs' / 'verification'
INDEX_VERSION = 'evidence-index-v1.0'
PATH_KEYS = ('file', 'path')


def _rel(path):
    return str(Path(path).resolve().relative_to(ROOT))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _resolve(name, here):
    """A reference as written -> a repository path, trying it as given, then beside the citing file, then in data/."""
    for candidate in (ROOT / name, here.parent / name, DATA / name):
        if candidate.is_file():
            return _rel(candidate)
    return name


def _looks_like_repo_file(ref):
    return ' ' not in ref and ref.endswith(('.json', '.json.gz', '.md', '.py', '.csv')) and not ref.startswith('supplemental-information')


def _walk(node, pointer=''):
    if isinstance(node, dict):
        yield pointer, node
        for k, v in node.items():
            yield from _walk(v, f'{pointer}/{k}')
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f'{pointer}/{i}')


def _documents():
    for folder in (DATA, VERIFICATION):
        for path in sorted(folder.glob('*.json')):
            try:
                yield path, json.loads(path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue


def _source_title(doc):
    src = doc.get('source') if isinstance(doc, dict) else None
    if not isinstance(src, dict):
        return None
    return src.get('document') or src.get('title') or src.get('citation')


@lru_cache(maxsize=1)
def build():
    edges, findings, files = [], [], {}
    for path, doc in _documents():
        rel = _rel(path)
        files[rel] = {'file': rel, 'sha256': _sha(path), 'source_document': _source_title(doc),
                      'kind': 'check_report' if path.parent == VERIFICATION else 'data'}
        for pointer, node in _walk(doc):
            ref = next((node[k] for k in PATH_KEYS if isinstance(node.get(k), str)), None)
            if ref is None or not isinstance(node.get('sha256'), str):
                continue
            target = _resolve(ref, path)
            kind = 'supersedes' if pointer.endswith('/supersedes') or pointer == '/supersedes' else 'cites'
            edge = {'from': rel, 'to': target, 'type': kind, 'field': pointer or '/', 'sha256': node['sha256']}
            if not (ROOT / target).is_file():
                if _looks_like_repo_file(ref):
                    findings.append({**edge, 'problem': 'file not found'})
                else:
                    # A source document (a PDF or an asset kept outside git): recorded with its checksum, not checked here.
                    edges.append({**edge, 'to': f'source:{ref}', 'type': 'extracted_from'})
                continue
            actual = _sha(ROOT / target)
            if actual != node['sha256']:
                findings.append({**edge, 'problem': 'SHA-256 does not match the file', 'actual_sha256': actual})
                continue
            edges.append(edge)
    code = _code_edges(files)
    model = _model_edges(files)
    edges += model + _ledger_edges() + code + _import_edges() + _implementation_edges(model, code)
    return {'index_version': INDEX_VERSION, 'files': files, 'edges': edges, 'findings': findings}


def _code_edges(files):
    """Python modules that name a pinned data file: 'pinned_by_code' when the module also holds the file's current
    SHA-256, otherwise 'read_by_code'."""
    import re
    out = []
    for module in sorted((ROOT / 'intelligence_store').glob('*.py')) + sorted((ROOT / 'landscape_ui').glob('*.py')):
        text = module.read_text(encoding='utf-8')
        for name in sorted(set(re.findall(r"['\"]([A-Za-z0-9_]+\.json(?:\.gz)?)['\"]", text))):
            target = _rel(DATA / name) if (DATA / name).is_file() else None
            if target is None or target not in files:
                continue
            kind = 'pinned_by_code' if files[target]['sha256'] in text else 'read_by_code'
            out.append({'from': f'code:{_rel(module)}', 'to': target, 'type': kind, 'field': _rel(module), 'sha256': files[target]['sha256']})
    return out


def _import_edges():
    """Module A imports module B: A depends on B (relative imports inside intelligence_store only)."""
    import re
    out = []
    pkg = ROOT / 'intelligence_store'
    for module in sorted(pkg.glob('*.py')):
        text = module.read_text(encoding='utf-8')
        names = set(re.findall(r'^\s*from \.(\w+) import', text, re.M))
        for group in re.findall(r'^\s*from \. import ([\w, ]+)', text, re.M):
            names.update(n.strip().split(' as ')[0] for n in group.split(','))
        for name in sorted(names):
            if (pkg / f'{name}.py').is_file() and name != module.stem:
                out.append({'from': f'code:{_rel(module)}', 'to': f'code:intelligence_store/{name}.py', 'type': 'imports',
                            'field': _rel(module), 'sha256': None})
    return out


def _implementation_edges(model_edges, code_edges):
    """A model is implemented by the modules that pin or read one of the extracts the credibility context lists for it."""
    readers = {}
    for e in code_edges:
        readers.setdefault(e['to'], set()).add(e['from'])
    out = []
    for e in model_edges:
        if e['type'] != 'model_uses':
            continue
        for module in sorted(readers.get(e['to'], ())):
            out.append({'from': e['from'], 'to': module, 'type': 'implemented_by', 'field': f"{e['field']} and {module[5:]}",
                        'sha256': None})
    return out


def _model_edges(files):
    from .credibility_records import CONTEXT_PATH, load_context
    out = []
    for model_id, ctx in load_context()['models'].items():
        for group in ('extracts', 'plans'):
            for name in ctx.get('sources', {}).get(group, []):
                target = _resolve(name, CONTEXT_PATH)
                out.append({'from': f'model:{model_id}', 'to': target, 'type': 'model_uses' if group == 'extracts' else 'model_plan',
                            'field': f'{_rel(CONTEXT_PATH)}#/models/{model_id}/sources/{group}', 'sha256': files.get(target, {}).get('sha256')})
        for dep in ctx.get('depends_on_models', []):
            out.append({'from': f'model:{model_id}', 'to': f'model:{dep}', 'type': 'model_depends_on',
                        'field': f'{_rel(CONTEXT_PATH)}#/models/{model_id}/depends_on_models', 'sha256': None})
    return out


def _ledger_edges():
    from .dataset_ledger import LEDGER_PATH, load_ledger
    out = []
    for i, use in enumerate(load_ledger()['uses']):
        field = f'{_rel(LEDGER_PATH)}#/uses/{i}'
        if use.get('report'):
            out.append({'from': use['report'], 'to': f"model:{use['model']}", 'type': 'checks_model', 'field': field, 'sha256': None})
            out.append({'from': use['report'], 'to': f"dataset:{use['dataset']}", 'type': f"dataset_{use['role']}", 'field': field, 'sha256': None})
        out.append({'from': f"model:{use['model']}", 'to': f"dataset:{use['dataset']}", 'type': use['role'], 'field': field, 'sha256': None})
    return out


def uses_of(target):
    """Connections pointing at a file or model (what uses or cites it)."""
    return [e for e in build()['edges'] if e['to'] == target]


def used_by_closure(target):
    """Everything that depends on a file, directly or through other files: files, models and checks."""
    seen, frontier = set(), [target]
    while frontier:
        node = frontier.pop()
        for e in build()['edges']:
            if e['to'] == node and e['type'] not in ('supersedes', 'imports') and e['from'] not in seen:
                seen.add(e['from'])
                frontier.append(e['from'])
    return sorted(seen)


def view(target):
    index = build()
    if target not in index['files']:
        raise KeyError(target)
    out_edges = [e for e in index['edges'] if e['from'] == target]
    in_edges = uses_of(target)
    closure = used_by_closure(target)
    # One step through imports: a module that imports a module reading the file also depends on it (not further, since
    # shared helpers are imported everywhere).
    direct_code = {n for n in closure if n.startswith('code:')}
    importers = {e['from'] for e in index['edges'] if e['type'] == 'imports' and e['to'] in direct_code} - direct_code
    via_import = {e['from'] for e in index['edges'] if e['type'] == 'implemented_by' and e['to'] in importers}
    direct_models = sorted(n[6:] for n in closure if n.startswith('model:'))
    closure = sorted(set(closure) | importers | via_import)
    return {'index_version': INDEX_VERSION, 'file': index['files'][target],
            'cites': [e for e in out_edges if e['type'] == 'cites'],
            'supersedes': [e for e in out_edges if e['type'] == 'supersedes'],
            'superseded_by': [e for e in in_edges if e['type'] == 'supersedes'],
            'used_by': [e for e in in_edges if e['type'] != 'supersedes'],
            'depends_on_it': {'files': [{'file': n, 'superseded': any(e['to'] == n and e['type'] == 'supersedes' for e in index['edges'])}
                                        for n in closure if n in index['files']],
                              'models': direct_models,
                              'models_through_shared_code': sorted(n[6:] for n in closure if n.startswith('model:') and n[6:] not in direct_models),
                              'code': [n[5:] for n in closure if n.startswith('code:')]},
            'findings': [f for f in index['findings'] if target in (f['from'], f['to'])],
            'clinical_prediction_validated': False}
