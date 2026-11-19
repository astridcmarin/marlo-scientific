"""Corrected versions of the two FDA guidance extracts after the owner's Track B review (19 November 2026).

- fda_hepatic_impairment_guidance_2026_draft_v2.json: every location now gives the printed page of the September 2026
  draft PDF in the owner's folder (SHA-256 414cb360...). The owner's review found five entries one page off (three location fields); the
  assistant then checked every quote's page by script against the same PDF and found four more (three quotes, Table 2). Sections are
  unchanged (the groups sentence is in IV.A.1, which begins on printed page 5, line 160). No quote or value changes.
- fda_renal_impairment_guidance_2024_v3.json: v2 already corrected the two quotes the review found wrong (16 November);
  v3 only records the PDF it was checked against (SHA-256 47b59f97...) and the review, so the page stops saying the
  source is not on file. No quote or value changes.
Run once from the repo root; rerunning reproduces both files byte for byte.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'intelligence_store' / 'data'
HEP_PDF = ('supplemental-information/articles/FDA 2026 - PK in patients with impaired hepatic function, draft guidance '
           'for industry, September 2026 [Draft Guidance PK in Patients with Impaired Hepatic Function].pdf')
HEP_PDF_SHA = '414cb3609f8ad887be5a19b352df506b7a56625986b696447f9afc96e7e3298f'
REN_PDF = ('supplemental-information/articles/FDA 2024 - PK in patients with impaired renal function, guidance for '
           'industry, March 2024 [guidance-on-renal-Impairment-PKstudies].pdf')
REN_PDF_SHA = '47b59f9713a259641280c79ee5a200e8e5b9e9976de0c29b7965b846596a0c0e'
RECORD = 'intelligence_store/data/extraction_review_record_2026-11-19_round3_track_b_v1.json'

# pointer -> (new location, found by)
HEP_FIXES = {
    '/recommendations/child_pugh/location': ('page 4, section IV.A, line 145', 'owner review'),
    '/recommendations/nci_in_cancer/location': ('page 4, section IV.A', 'assistant, by script'),
    '/recommendations/cp_groups/location': ('page 5, section IV.A.1, lines 164-165', 'owner review'),
    '/recommendations/nci_components/location': ('page 6, section IV.A.2', 'assistant, by script'),
    '/recommendations/other_systems/location': ('page 6', 'assistant, by script'),
    '/child_pugh_table_1/location': ('page 5, Table 1', 'owner review'),
    '/nci_odwg_table_2/location': ('page 6, Table 2', 'assistant, by script'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(name, obj):
    raw = (json.dumps(obj, indent=1, ensure_ascii=False) + '\n').encode()
    (D / name).write_bytes(raw)
    return sha(raw)


def _get(doc, pointer):
    node = doc
    for t in pointer.strip('/').split('/'):
        node = node[t]
    return node


def _set(doc, pointer, value):
    *head, last = pointer.strip('/').split('/')
    node = doc
    for t in head:
        node = node[t]
    node[last] = value


def hepatic():
    raw = (D / 'fda_hepatic_impairment_guidance_2026_draft_v1.json').read_bytes()
    v1 = json.loads(raw)
    v2 = copy.deepcopy(v1)
    v2['extract_version'] = 'fda-hepatic-impairment-guidance-2026-draft-v2.0'
    v2['recorded_on'] = '2026-11-19'
    corrections = []
    for pointer, (new, who) in HEP_FIXES.items():
        corrections.append({'field': pointer, 'was': _get(v1, pointer), 'now': new, 'found_by': who})
        _set(v2, pointer, new)
    v2['child_pugh_table_1']['reading'] = (
        'Five components, each in three columns headed 1, 2 and 3 points (the headers are printed in the PDF; the web '
        'text of 5 November had lost them). The groups and total scores are not printed in the table; they are '
        'taken from the sentence directly above it (lines 164-165).')
    corrections.append({'field': '/child_pugh_table_1/reading', 'was': v1['child_pugh_table_1']['reading'],
                        'now': v2['child_pugh_table_1']['reading'], 'found_by': 'assistant, from the PDF'})
    v2['source'] = dict(v1['source'], local_file=HEP_PDF, local_file_sha256=HEP_PDF_SHA, extraction=(
        "AI-assisted, 5 November 2026, from the web text of the PDF at the URL above. Reviewed by the platform owner "
        "against the PDF in the owner's folder on 19 November 2026 (Track B): 9 of 14 values matched and 5 locations "
        "were one printed page off; this version corrects them and 4 more the assistant then found by script (three quotes and Table 2). Pages are "
        "printed page numbers of the September 2026 draft."))
    v2['supersedes'] = {'file': 'intelligence_store/data/fda_hepatic_impairment_guidance_2026_draft_v1.json',
                        'sha256': sha(raw), 'review_record': RECORD,
                        'change': 'Locations corrected to printed pages of the PDF; table 1 reading updated. No quote or value changed.',
                        'corrections': corrections}
    return dump('fda_hepatic_impairment_guidance_2026_draft_v2.json', v2)


def renal():
    raw = (D / 'fda_renal_impairment_guidance_2024_v2.json').read_bytes()
    v2 = json.loads(raw)
    v3 = copy.deepcopy(v2)
    v3['extract_version'] = 'fda-renal-impairment-guidance-2024-v3.0'
    v3['source'] = dict(v2['source'], local_file=REN_PDF, local_file_sha256=REN_PDF_SHA, extraction=(
        "AI-assisted, 5 November 2026, from the web text of the PDF at the URL above; two quotes corrected against the "
        "PDF in the owner's folder on 16 November (v2). Reviewed by the platform owner on 19 November 2026 (Track B): "
        "5 of 7 values matched, and the 2 found wrong are the two quotes v2 had already corrected. The text layer lost "
        "the word 'to' in the ranges of Table 1 (printed '60 < 90')."))
    v3['supersedes'] = {'file': 'intelligence_store/data/fda_renal_impairment_guidance_2024_v2.json', 'sha256': sha(raw),
                        'review_record': RECORD,
                        'change': 'Records the PDF the quotes were checked against and the owner review. No quote or value changed.',
                        'previous': v2['supersedes']}
    return dump('fda_renal_impairment_guidance_2024_v3.json', v3)


if __name__ == '__main__':
    print('hepatic v2', hepatic())
    print('renal v3', renal())
