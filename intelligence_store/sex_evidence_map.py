"""Track I: where the evidence on sex comes from, per myeloma drug, and where it is missing (plan
docs/EVIDENCE_CONNECTIONS_PLAN.md, update 4).

Descriptive only, from pinned data, and adding nothing to any model:
- what each drug's special-population summary already states about sex (label, popPK or study text, with its source);
- where biological sex enters the platform's own calculations (the published equations in the covariate registry);
- what the trial corpus records: the eligibility "sex" field of each registered trial. Enrolment by sex is reported only
  in posted results on ClinicalTrials.gov, which the platform has not retrieved, so it is shown as not available.
"""
import re
from collections import Counter

from . import covariate_estimation as ce
from . import special_populations as sp
from .eligibility_corpus import CORPUS_SHA256, load_corpus

MAP_VERSION = 'sex-evidence-map-v1.0'
SEX_WORDS = re.compile(r'\b(sex|gender|female|females|women|male|males|men)\b', re.I)


def _mentions_sex(statement):
    return bool(SEX_WORDS.search(' '.join(str(statement.get(k, '')) for k in ('text', 'value', 'kind'))))


def by_drug():
    out = []
    for drug in sorted(sp.SUMMARIES):
        summary = sp.load_summary(drug)
        name, sha = sp.SUMMARIES[drug]
        statements = []
        for domain, items in summary['domains'].items():
            for i, st in enumerate(items):
                if _mentions_sex(st):
                    src = st.get('source', {})
                    ref = summary['sources'].get(src.get('ref'), {}) if isinstance(src, dict) else {}
                    statements.append({'domain': domain, 'index': i, 'kind': st.get('kind'), 'text': st.get('text'),
                                       'value': st.get('value'), 'source_title': ref.get('title'),
                                       'source_file': ref.get('file'), 'pointer': src.get('pointer') if isinstance(src, dict) else None})
        extracted = [s for s in statements if s['kind'] != 'gap']
        out.append({'drug': drug, 'summary_file': f'intelligence_store/data/{name}', 'summary_sha256': sha,
                    'statements': statements,
                    'status': 'stated' if extracted else ('gap_recorded' if statements else 'nothing_on_sex_extracted')})
    return out


def platform_equations():
    registry = ce.load_formula_registry()
    return [{'formula': key, 'equation': f['equation'], 'citation': f['source'].get('citation'), 'doi': f['source'].get('doi')}
            for key, f in registry['formulas'].items() if 'biological_sex' in f['inputs']]


def trial_eligibility():
    corpus = load_corpus()
    counts = Counter(t['eligibility'].get('sex') or 'not recorded' for t in corpus['trials'])
    return {'trials': len(corpus['trials']), 'eligibility_sex': dict(sorted(counts.items())), 'corpus_sha256': CORPUS_SHA256,
            'cohort': corpus.get('cohort'),
            'enrolment_by_sex': ('Not available: ClinicalTrials.gov reports enrolment by sex only in posted results '
                                 '(baseline characteristics), which the platform has not retrieved.')}


def build():
    return {'map_version': MAP_VERSION, 'drugs': by_drug(), 'platform_equations': platform_equations(),
            'trial_eligibility': trial_eligibility(),
            'reading': ('This describes the evidence and predicts nothing. Sex enters the platform only through the published '
                        'equations listed; no sex adjustment has been added to any model.'),
            'clinical_prediction_validated': False}
