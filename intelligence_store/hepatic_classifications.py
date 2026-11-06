"""Hepatic-function classifications compared (reviewer's checklist H2, 5 November 2026).

The REVLIMID label defines mild hepatic impairment by total bilirubin and AST, as the NCI Organ Dysfunction Working
Group criteria do; the FDA's September 2026 draft hepatic guidance recommends Child-Pugh in cirrhosis and allows the NCI
criteria in patients with cancer. This view sets the guidance's two systems beside the label's definitions, reading
every value from a pinned file. The mapping of the label's wording onto NCI groups is the platform's reading and is
labelled so. Nothing here classifies a patient or proposes a dose.
"""
import hashlib
import json
from pathlib import Path

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = 'intelligence_store/data/'
VIEW_VERSION = 'hepatic-classifications-v1.0'
SOURCES = {
    'fda_2026': (DATA + 'fda_hepatic_impairment_guidance_2026_draft_v1.json',
                 '6f2ff8b9cbb1806a7d7445d6dcd424e9b997ddc29d00be04850d8317dab3c000',
                 'FDA, Pharmacokinetics in Patients with Impaired Hepatic Function, draft guidance, September 2026'),
    'label_2023': (DATA + 'lenalidomide_label_2023_v1.json',
                   'd4b02134613dc45d6b039999b37d9c94ccbc047cc0b7e811b77278c868e47a9a',
                   'REVLIMID prescribing information, revision 3/2023'),
    'bridoux_design': (DATA + 'lenalidomide_bridoux_design_v1.json',
                       '1af2d005528a18088382225482a3eaa32ac3c68f4f6529c5ee7958e8c1605eac',
                       'Bridoux 2016 study design extract'),
}
# The label statement -> NCI groups it corresponds to (platform reading of the label's wording).
LABEL_TO_NCI = (
    ('mild', ('B1', 'B2'), 'The label\'s "total bilirubin > 1 to 1.5 times ULN or any AST greater than ULN" is NCI group B: '
                           'B2 (bilirubin > 1 to 1.5 x ULN, any AST) or B1 (bilirubin within ULN, AST above it).'),
    ('moderate_severe', ('C', 'D'), 'The label\'s "moderate to severe" has no stated definition; read here as NCI groups C and D, '
                                    'for which the label says no pharmacokinetic data exist.'),
)
NOTES = {
    'population': 'The guidance allows the NCI criteria in subjects with cancer and does not recommend them otherwise; '
                  'lenalidomide is studied in haematological cancers, and its label uses NCI-style definitions. No '
                  'lenalidomide data by Child-Pugh group are in the platform\'s sources.',
    'scope': 'For dedicated hepatic impairment studies and labelling. Nothing here classifies a patient or proposes a dose.',
}


class HepaticClassificationError(ValueError):
    pass


def _load():
    docs = {}
    for alias, (path, sha, _t) in SOURCES.items():
        raw = (ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise HepaticClassificationError(f'{path} is missing or changed; the comparison was not built.')
        docs[alias] = json.loads(raw)
    return docs


def build():
    d = _load()
    g, hep = d['fda_2026'], d['label_2023']['pharmacokinetics']['hepatic']
    nci = {x['id']: x for x in g['nci_odwg_table_2']['groups']}
    label_rows = [{'statement': key, 'quote': hep[key]['quote'], 'location': hep[key]['location'],
                   'nci_groups': [dict(nci[i]) for i in ids], 'platform_reading': reading}
                  for key, ids, reading in LABEL_TO_NCI]
    view = {
        'view_version': VIEW_VERSION, 'drug': 'lenalidomide',
        'guidance': {'title': g['source']['title'], 'status': g['source']['status'], 'date': g['source']['date'],
                     'docket': g['source']['docket'], 'url': g['source']['url'], 'extraction': g['source']['extraction'],
                     'recommendations': [dict(v, id=k) for k, v in g['recommendations'].items()]},
        'nci': {'location': g['nci_odwg_table_2']['location'], 'groups': g['nci_odwg_table_2']['groups'],
                'reading': g['nci_odwg_table_2']['reading']},
        'child_pugh': {'location': g['child_pugh_table_1']['location'], 'components': g['child_pugh_table_1']['as_returned'],
                       'groups': g['child_pugh_table_1']['groups'], 'reading': g['child_pugh_table_1']['reading']},
        'label': label_rows,
        'platform_checks': {'bridoux_population': d['bridoux_design']['design']['population']['value']},
        'notes': NOTES,
        'sources': [{'alias': a, 'file': p, 'sha256': s, 'title': t} for a, (p, s, t) in SOURCES.items()],
        'clinical_prediction_validated': False,
    }
    view['view_sha256'] = digest(view)
    return view
