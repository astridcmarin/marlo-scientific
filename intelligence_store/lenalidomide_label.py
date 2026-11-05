"""Pinned extract of the REVLIMID (lenalidomide) prescribing information, revision 3/2023 (DailyMed set ID
5fa97bf5-28a2-48f1-8955-f56012d296be): multiple myeloma dosing, Table 3 renal dose adjustments, and the
special-population statements in sections 8.5, 8.6 and 12.3. Quoted for display; the platform proposes no dose.
"""
import hashlib
import json
from pathlib import Path

EXTRACT_PATH = Path(__file__).parent / 'data' / 'lenalidomide_label_2023_v1.json'
EXTRACT_SHA256 = 'd4b02134613dc45d6b039999b37d9c94ccbc047cc0b7e811b77278c868e47a9a'


def load_label_extract(path=EXTRACT_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXTRACT_SHA256:
        raise ValueError('Lenalidomide label extract is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'drug-label-extract-v1':
        raise ValueError('Unsupported label extract schema.')
    return data



PK_EXTRACT_PATH = Path(__file__).parent / 'data' / 'lenalidomide_label_2023_pk_v1.json'
PK_EXTRACT_SHA256 = '821673b5f99364ef1c88ff952c3670d01006ccb6b3bf06a3b3cebeebceda8283'


def load_label_pk_extract(path=PK_EXTRACT_PATH):
    """The rest of section 12.3 (absorption, food, distribution, elimination, dialysis, interaction studies) and
    section 7 of the same label file, extracted 5 November 2026; not yet reviewed by the owner (round 3)."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PK_EXTRACT_SHA256:
        raise ValueError('Lenalidomide label pharmacokinetics extract is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'label-section-extract-v1':
        raise ValueError('Unsupported label section extract schema.')
    return data


RECONCILIATION_PATH = Path(__file__).parent / 'data' / 'lenalidomide_renal_source_reconciliation_v3.json'
RECONCILIATION_SHA256 = '8d076dfbb4d50ed940064c1cab798b8a3b8eca684d6ac5b383e8487d847f5292'
# Superseded, kept unchanged for traceability: lenalidomide_renal_source_reconciliation_v2.json
RECONCILIATION_V2_SHA256 = '799d35e0966a57b697e8c1a955a5b40e9f04b2e92e62ceabe6fbf2e963e36da1'
# Superseded, kept unchanged for traceability: lenalidomide_renal_source_reconciliation_v1.json
RECONCILIATION_V1_SHA256 = '79b7aa02273a2c34e23190450b092a26baf7e27826591036d70e563bea9fb3d5'


def load_renal_reconciliation(path=RECONCILIATION_PATH):
    """Reconciliation of the renal-study sources (EMA table, label, reference note); see the file's items."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECONCILIATION_SHA256:
        raise ValueError('Lenalidomide renal source reconciliation is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'source-reconciliation-v1':
        raise ValueError('Unsupported reconciliation schema.')
    return data


# ---------------------------------------------------------------- label pharmacokinetics and interactions, for display
PK_VIEW_SECTIONS = (
    ('absorption', 'Absorption and food', (('absorption', 'tmax', 'Time to peak'), ('absorption', 'accumulation', 'Repeated doses'),
                                           ('absorption', 'food_effect', 'High-fat meal'), ('absorption', 'administration', 'Food in the trials'))),
    ('elimination', 'Distribution and elimination', (('distribution', 'semen', 'Semen'), ('elimination', 'half_life', 'Half-life'), ('elimination', 'metabolism', 'Metabolism'),
                                                     ('elimination', 'excretion', 'Excretion'), ('renal_dialysis', None, 'Haemodialysis'))),
    ('interactions', 'Drug interactions', (('drug_interactions_7', 'digoxin', 'Digoxin (section 7.1)'),
                                           ('drug_interactions_7', 'thrombosis', 'Agents that raise thrombosis risk (section 7.2)'),
                                           ('drug_interactions_7', 'warfarin', 'Warfarin (section 7.3)'),
                                           ('drug_interactions_12_3', 'dexamethasone', 'Dexamethasone (study)'),
                                           ('drug_interactions_12_3', 'quinidine', 'Quinidine, a P-gp inhibitor (study)'),
                                           ('drug_interactions_12_3', 'temsirolimus', 'Temsirolimus (study)'),
                                           ('drug_interactions_12_3', 'transporters', 'Transporters (in vitro)'),
                                           ('drug_interactions_12_3', 'cyp_and_ugt', 'CYP450 and UGT1A1 (in vitro)'))),
)


def label_pk_view(data=None):
    """The section 12.3 and section 7 quotes grouped for a page, each with its location. Nothing is computed."""
    data = data or load_label_pk_extract()
    sections = []
    for sid, title, entries in PK_VIEW_SECTIONS:
        items = []
        for block, key, label in entries:
            node = data[block] if key is None else data[block][key]
            location = node.get('location') or data[block].get('location')
            quotes = [node[k] for k in ('quote', 'not_substrate_quote', 'not_inhibitor_quote') if k in node]
            items.append({'label': label, 'quotes': quotes, 'location': location})
        sections.append({'id': sid, 'title': title, 'items': items})
    return {'extract_version': data['extract_version'], 'sha256': PK_EXTRACT_SHA256, 'document': data['source']['document'],
            'extraction': data['source']['extraction'], 'sections': sections,
            'not_stated': data['absorption']['bioavailability']['note'], 'clinical_prediction_validated': False}
