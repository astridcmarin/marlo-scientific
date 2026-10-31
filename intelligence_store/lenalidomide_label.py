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


RECONCILIATION_PATH = Path(__file__).parent / 'data' / 'lenalidomide_renal_source_reconciliation_v3.json'
RECONCILIATION_SHA256 = 'ab27598359ca3b399004821a3454348a7395ce4322a837d4af663ad99d693c5c'
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
