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
