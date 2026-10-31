"""Pinned extract of the NINLARO (ixazomib) prescribing information, revision 7/2024 (identical text checked in the 11/2015 initial-approval label): starting
dose, hepatic and renal dose actions, and the special-population statements in sections 8.5-8.7 and 12.3. Quoted for
display; the platform proposes no dose.
"""
import hashlib
import json
from pathlib import Path

EXTRACT_PATH = Path(__file__).parent / 'data' / 'ixazomib_label_2024_v1.json'
EXTRACT_SHA256 = '013d5b20a8d1c049bed39d23b44f57110a5f691408f4e50f8423e8f29735dd06'


def load_label_extract(path=EXTRACT_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXTRACT_SHA256:
        raise ValueError('Ixazomib label extract is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'drug-label-extract-v1':
        raise ValueError('Unsupported label extract schema.')
    return data
