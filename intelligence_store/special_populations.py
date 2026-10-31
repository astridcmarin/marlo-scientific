"""Phase 4.2: special-population evidence summaries (docs/SPECIAL_POPULATIONS.md).

A summary file per drug (schema special-population-summary-v1, pinned here) lists domains (kidney, liver, age, body
size, other covariates) and, in each, statements of one declared kind. Every statement carries its value and a
pointer (RFC 6901 JSON pointer) into a pinned source file. `build` checks each source file's checksum, resolves every
pointer and refuses the whole summary if any stored value differs from its source. Nothing is computed: the page
shows sourced findings side by side, with their kind and the population they come from.
"""
import hashlib
import json
from pathlib import Path

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
SCHEMA_VERSION = 'special-population-summary-v1'
BUILD_VERSION = 'special-population-summary-build-v1.0'
DOMAINS = ('kidney', 'liver', 'age', 'body_size', 'other_covariates')
DOMAIN_LABELS = {'kidney': 'Kidney function', 'liver': 'Liver function', 'age': 'Age', 'body_size': 'Body size',
                 'other_covariates': 'Sex, race and other covariates'}
KINDS = {
    'study_exposure_change': 'Observed in a study',
    'label_statement': 'Label statement',
    'label_action': 'Label action',
    'covariate_effect': 'Population-model covariate (retained)',
    'covariate_not_retained': 'Population-model covariate (tested, not retained)',
    'not_studied': 'Not studied (as stated by the source)',
    'platform_model_scope': "Platform model scope",
    'gap': "Not in the platform's pinned sources",
}
SUMMARIES = {
    'ixazomib': ('special_populations_ixazomib_v1.json', 'cd3b68f8ec285160dadd81140b0d3aae9748971e6176bfef8032564ecc9bf423'),
    'pomalidomide': ('special_populations_pomalidomide_v1.json', '1679f31955b42f86b4246e9a99c236e0800a0007cbd131a6c39e44d36390813f'),
    'lenalidomide': ('special_populations_lenalidomide_v2.json', '7236f8899c71ff7268db5edffe062dd7a3aa49a0499f3436767f10dcca2e84b3'),
    'daratumumab': ('special_populations_daratumumab_v1.json', 'c5fde7d9f8ccd730c1bb5f66aeb8823b00935f914fd1a23bef4cd48d3a46c73d'),
    'dexamethasone': ('special_populations_dexamethasone_v1.json', 'bdf9f6da7204f48f8d10827653c0cecefe038b37f8bc1b0b0d3b14aa818d6d3d'),
    'bortezomib': ('special_populations_bortezomib_v1.json', 'ba438c49bd4f4ab9e7f34f1215ea29376521688821cb41a9c2a9761a226ce388'),
}
# Superseded summaries, kept unchanged for traceability.
SUPERSEDED = {
    'special_populations_lenalidomide_v1.json': '406618748fe544594f44d8b7e6c8cf7c0677138842f4c3715138a0c22ea4e1c8',
}


class SummaryError(ValueError):
    pass


def resolve(document, pointer):
    """RFC 6901 JSON pointer."""
    if pointer == '':
        return document
    if not pointer.startswith('/'):
        raise SummaryError(f'Invalid pointer {pointer!r}.')
    node = document
    for token in pointer[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(node, list):
            node = node[int(token)]
        elif isinstance(node, dict) and token in node:
            node = node[token]
        else:
            raise SummaryError(f'Pointer {pointer!r} does not resolve.')
    return node


def _pinned_json(path, sha256, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise SummaryError(f'{label} is missing or changed; the summary was not built.')
    return json.loads(raw)


def load_summary(drug):
    if drug not in SUMMARIES:
        raise KeyError(drug)
    name, sha = SUMMARIES[drug]
    data = _pinned_json(DATA / name, sha, f'Special-population summary for {drug}')
    if data.get('schema_version') != SCHEMA_VERSION:
        raise SummaryError('Unsupported special-population summary schema.')
    return data


def build(drug):
    summary = load_summary(drug)
    sources = {}
    for alias, ref in summary['sources'].items():
        document = _pinned_json(ROOT / ref['file'], ref['sha256'], f'Source {alias}')
        sources[alias] = {'document': document, 'file': ref['file'], 'sha256': ref['sha256'], 'title': ref['title'],
                          'extraction': ref.get('extraction') or document.get('extraction')
                          or document.get('source', {}).get('extraction', 'not stated')}
    rows = []
    for domain in DOMAINS:
        statements = []
        for st in summary['domains'].get(domain, []):
            if st['kind'] not in KINDS:
                raise SummaryError(f'Unknown statement kind {st["kind"]!r}.')
            if st.get('display') not in (None, 'mean_sd', 'gm_cv', 'range', 'ratio_ci', 'bands'):
                raise SummaryError(f'Unknown display hint {st.get("display")!r}.')
            out = {'kind': st['kind'], 'kind_label': KINDS[st['kind']], 'text': st['text'],
                   'population': st.get('population'), 'link': st.get('link'), 'display': st.get('display')}
            if st['kind'] != 'gap':
                src = st['source']
                if src['ref'] not in sources:
                    raise SummaryError(f'Unknown source {src["ref"]!r}.')
                found = resolve(sources[src['ref']]['document'], src['pointer'])
                if found != st['value']:
                    raise SummaryError(f'{drug} / {domain}: stored value differs from {src["ref"]}{src["pointer"]}.')
                out.update(value=st['value'], source={'ref': src['ref'], 'pointer': src['pointer'],
                                                      'location': src.get('location'), 'file': sources[src['ref']]['file'],
                                                      'title': sources[src['ref']]['title']})
            statements.append(out)
        rows.append({'domain': domain, 'label': DOMAIN_LABELS[domain], 'statements': statements})
    result = {'schema_version': 'special-population-summary-view-v1', 'build_version': BUILD_VERSION,
              'drug': summary['drug'], 'label': summary['label'], 'summary_version': summary['summary_version'],
              'recorded_on': summary['recorded_on'], 'intro': summary['intro'], 'rows': rows,
              'sources': [{'ref': a, 'title': s['title'], 'file': s['file'], 'sha256': s['sha256'], 'extraction': s['extraction']}
                          for a, s in sources.items()],
              'not_this': summary['not_this'], 'summary_sha256': SUMMARIES[drug][1], 'clinical_prediction_validated': False}
    result['view_sha256'] = digest(result)
    return result


def available():
    return list(SUMMARIES)
