"""Lenalidomide Hughes 2019 and Kim 2026 against Bridoux 2016 (myeloma with renal impairment): the locked check (2.1h).

Stage 1 (4 November 2026): the observed design, read from the methods and Table 1 only, pinned here before any
exposure value is used. Stage 2 adds the observed exposure values and the virtual trial under the plan locked on
31 October 2026 (lenalidomide_bridoux_check_plan_v1.json). The stage 1 file records one deviation: part of the
Results text was seen while locating Table 1 (see its 'deviation' entry).
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / 'data'
PLAN_PATH = DATA / 'lenalidomide_bridoux_check_plan_v1.json'
DESIGN_PATH = DATA / 'lenalidomide_bridoux_design_v1.json'
DESIGN_SHA256 = '1af2d005528a18088382225482a3eaa32ac3c68f4f6529c5ee7958e8c1605eac'


def load_design(path=DESIGN_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != DESIGN_SHA256:
        raise ValueError('Bridoux observed-design file is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != 'observed-design-v1':
        raise ValueError('Unsupported observed-design schema.')
    return data
