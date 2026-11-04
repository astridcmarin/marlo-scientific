"""Pinned label extracts of 4 November 2026: carfilzomib, selinexor, thalidomide, isatuximab, elotuzumab (Phase 3.2d).

Built by scripts/build_label_extracts_2026_11.py from the platform owner's DailyMed PDFs, which are not committed. Every
value carries the label sentence it comes from and its section and PDF page; the build refused any quote not found in
the label's text layer. These extracts record what each label says. They run no model: a label-based exposure curve needs
its own locked consistency plan, and an antibody's target-mediated clearance is outside the label engine's scope.
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / 'data'
SCHEMA_VERSION = 'drug-label-extract-v1'
EXTRACTS = {
    'carfilzomib': ('label_extract_carfilzomib_v1.json', '199572222b557c6cd6e4b95b5941408ed3568d942c3b15e612fcc73d0e63491f'),
    'selinexor': ('label_extract_selinexor_v1.json', '1aa94920dee092c95397a356fba023a4f287615d940c56bafacc19af4dc11258'),
    'thalidomide': ('label_extract_thalidomide_v1.json', '855c93238f4bbb0688e34cdcd09ab586a1295f38dfefeaf56535c87b36ad67fd'),
    'isatuximab': ('label_extract_isatuximab_v1.json', '35055872da2698470d44f4d36022d0cc0e4e49774921d4d690ef86200cf1948f'),
    'elotuzumab': ('label_extract_elotuzumab_v1.json', '87dd6ce18b91a2e5a29f0ddd22c892da5edbfec587c35133a3af6b4e06259ae1'),
}
SECTIONS = ('dosing', 'pk', 'special_populations', 'interactions')
LABEL_ENGINE_CANDIDATES = ('selinexor', 'carfilzomib', 'thalidomide')   # small molecules; each needs a locked plan first


class LabelExtractError(ValueError):
    pass


def load_extract(drug):
    if drug not in EXTRACTS:
        raise KeyError(drug)
    name, sha = EXTRACTS[drug]
    raw = (DATA / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise LabelExtractError(f'The {drug} label extract is missing or changed; a change needs a new version.')
    doc = json.loads(raw)
    if doc.get('schema_version') != SCHEMA_VERSION or doc.get('drug') != drug:
        raise LabelExtractError(f'Not the {drug} label extract.')
    return doc


def entries(drug):
    doc = load_extract(drug)
    return [dict(v, section=s, key=k) for s in SECTIONS for k, v in doc[s].items()]
