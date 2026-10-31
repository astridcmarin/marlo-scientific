"""Pinned extract of the NINLARO (ixazomib) prescribing information, revision 11/2015 (initial approval): starting
dose, hepatic and renal dose actions, and the special-population statements in sections 8.5-8.7 and 12.3. Quoted for
display; the platform proposes no dose.
"""
import hashlib
import json
from pathlib import Path

EXTRACT_PATH = Path(__file__).parent / 'data' / 'ixazomib_label_2015_v1.json'
EXTRACT_SHA256 = '38943eeb919d768c4d3a626cfbf96250ad29f14d2dd16c72fae45bd675d226f9'


def load_label_extract(path=EXTRACT_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXTRACT_SHA256:
        raise ValueError('Ixazomib label extract is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'drug-label-extract-v1':
        raise ValueError('Unsupported label extract schema.')
    return data
