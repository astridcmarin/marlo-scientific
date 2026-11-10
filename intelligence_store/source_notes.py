"""Source notes: facts about the sources behind pinned files that the files do not record (AI review of 10 November 2026).

Each note points at a pinned file, its SHA-256 and a JSON pointer; none changes a value. Carried into each file's next
version when that file is next revised.
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / 'data'
NOTES_PATH = DATA / 'lenalidomide_source_notes_v1.json'
NOTES_SHA256 = 'cebb14af7d94d917f781c967d640402e1ed1a2574346246a2e17aca893dfd3b2'


def load_source_notes(path=NOTES_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != NOTES_SHA256:
        raise ValueError('Source notes file is missing or changed; a change needs a new version.')
    data = json.loads(raw)
    if data.get('schema_version') != 'source-notes-v1':
        raise ValueError('Unsupported source notes schema.')
    return data
