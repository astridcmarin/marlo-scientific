"""Build drug catalogue v2 (names, mechanism, safety, interactions) adding ixazomib, and dataset ledger v15.

Run once on 18 November 2026 from the repo root. Sources: the NINLARO DailyMed SPL, set 038f2461-834b-4488-9ebd-863c83eef5a7,
version 18 (XML SHA-256 2292dfec…), read in sections 5, 7, 11, 12.1 and the drug-interaction part of 12.3. The summaries are
AI-written from that text. Rerunning reproduces the pinned files byte for byte; a change needs new versions instead.
"""
import copy, hashlib, json
from pathlib import Path
D = Path('intelligence_store/data')
def load(n): return json.loads((D / n).read_text())
def dump(n, obj, indent=2):
    raw = (json.dumps(obj, indent=indent, ensure_ascii=False) + '\n').encode()
    (D / n).write_bytes(raw); return hashlib.sha256(raw).hexdigest()

SOURCE = {
    "publisher": "DailyMed, U.S. National Library of Medicine",
    "title": "Ninlaro / ixazomib product label",
    "url": "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=038f2461-834b-4488-9ebd-863c83eef5a7&version=18",
    "set_id": "038f2461-834b-4488-9ebd-863c83eef5a7",
    "label_version": 18,
    "label_effective_date": "20260811",
    "verified_on": "2026-11-18",
    "retrieved_xml_sha256": "2292dfec663f940ba661c067346ed3ad88142029dbe6f2a3bbfde18619cb40e8",
    "note": "The product label identifies Ninlaro as an ixazomib product. The capsule contains ixazomib citrate, a prodrug that hydrolyzes to ixazomib; name mapping does not equate doses or salt forms.",
}
REF = "Ninlaro oral capsule reference"

a = load('drug_aliases_v1.json')
a2 = copy.deepcopy(a)
a2['catalog_version'] = 'myeloma-seed-v1.4'
src = dict(SOURCE)
a2['entries'].append({"id": "ixazomib", "canonical_name": "Ixazomib", "aliases": ["Ixazomib", "Ninlaro"], "source": src})
# key order like the existing entries
a2['entries'][-1] = {k: a2['entries'][-1][k] for k in a['entries'][0]}
alias_sha = dump('drug_aliases_v2.json', a2)

def bump(name, new_version, entry):
    c = load(name + '_v1.json'); c2 = copy.deepcopy(c)
    c2['catalog_version'] = new_version
    c2['alias_catalog_version'] = a2['catalog_version']; c2['alias_catalog_sha256'] = alias_sha
    c2['entries'].append({k: entry[k] for k in c['entries'][0]})
    return dump(name + '_v2.json', c2)

safety_sha = bump('drug_safety', 'myeloma-safety-v1.4', {
    "entity_id": "ixazomib", "source": dict(SOURCE), "reference_product": REF,
    "boxed_warning": {"present": False, "basis": "No boxed-warning section is present in the verified SPL version.", "sections": []},
    "selected_warnings": [
        {"topic": "Low platelet counts", "basis": "The label describes thrombocytopenia with nadirs during each cycle and recovery by the next, and advises monthly platelet monitoring.", "sections": ["5.1"], "interpretation": "curated_summary"},
        {"topic": "Gastrointestinal toxicity", "basis": "The label describes diarrhea, constipation, nausea and vomiting, sometimes needing supportive medication.", "sections": ["5.2"], "interpretation": "curated_summary"},
        {"topic": "Peripheral neuropathy", "basis": "The label describes mostly sensory neuropathy, largely Grade 1 or 2.", "sections": ["5.3"], "interpretation": "curated_summary"},
        {"topic": "Thrombotic microangiopathy", "basis": "The label describes cases, sometimes fatal, including TTP/HUS.", "sections": ["5.6"], "interpretation": "curated_summary"},
        {"topic": "Hepatotoxicity", "basis": "The label describes drug-induced liver injury and advises regular monitoring of liver enzymes.", "sections": ["5.7"], "interpretation": "curated_summary"},
        {"topic": "Increased mortality in maintenance use", "basis": "The label reports more deaths with ixazomib in two randomized maintenance-setting trials and does not recommend that use outside controlled trials.", "sections": ["5.9"], "interpretation": "curated_summary"},
    ]})

inter_sha = bump('drug_interactions', 'myeloma-interactions-v1.4', {
    "entity_id": "ixazomib", "source": dict(SOURCE), "reference_product": REF,
    "references": [
        {"id": "ixazomib-rifampin", "title": "Strong CYP3A inducer example", "basis": "The label describes decreased ixazomib exposure with rifampin and advises avoiding strong CYP3A inducers; rifampin is the studied example. Other class members named in the label are not separate references here.", "sections": ["7.1", "12.3"], "partner_name": "Rifampin", "kind": "drug_pair", "finding": "exposure_change_reported", "interpretation": "curated_summary"},
        {"id": "ixazomib-clarithromycin", "title": "Clarithromycin studied context", "basis": "The label reports no clinically meaningful change in ixazomib exposure with clarithromycin, a strong CYP3A inhibitor. This finding does not establish general regimen compatibility or safety.", "sections": ["12.3"], "partner_name": "Clarithromycin", "kind": "drug_pair", "finding": "no_significant_effect_reported", "interpretation": "curated_summary"},
    ]})

annot_sha = bump('drug_annotations', 'myeloma-annotations-v1.4', {
    "entity_id": "ixazomib", "source": dict(SOURCE),
    "fields": {
        "mechanism": {"label": "Proteasome inhibitor", "basis": "The label describes reversible inhibition of the chymotrypsin-like activity of the beta 5 subunit of the 20S proteasome.", "sections": ["12.1 Mechanism of Action"], "interpretation": "curated_summary"},
        "target": {"label": "Proteasome", "basis": "The label describes reversible inhibition of the chymotrypsin-like activity of the beta 5 subunit of the 20S proteasome. Proteasome is a broad target-family category; subunits and reversibility remain in the source note.", "sections": ["12.1 Mechanism of Action"], "interpretation": "curated_summary"},
        "modality": {"label": "Small molecule", "basis": "Curated as a small molecule from the label’s chemical structure and molecular weight; supplied as the citrate prodrug, which hydrolyzes to ixazomib.", "sections": ["11 Description"], "interpretation": "curated_classification"},
    }})

v14_raw = (D / 'dataset_ledger_v14.json').read_bytes()
v14 = json.loads(v14_raw); v15 = copy.deepcopy(v14)
v15['ledger_version'] = 'dataset-ledger-v15.0'; v15['recorded_on'] = '2026-11-18'
v15['datasets']['ninlaro_label'] = {
    "title": "NINLARO label (ixazomib)",
    "sources": ["NINLARO prescribing information, revised 7/2024 (FDA label file)",
                "NINLARO DailyMed SPL, set 038f2461-834b-4488-9ebd-863c83eef5a7, version 18, effective 11 August 2026"],
    "files": ["intelligence_store/data/ixazomib_label_2024_v1.json", "intelligence_store/data/drug_safety_v2.json",
              "intelligence_store/data/drug_interactions_v2.json", "intelligence_store/data/drug_annotations_v2.json"],
    "values_first_seen": "2026-10-31",
    "seen_note": "The 7/2024 label was read while building ixazomib_label_2024_v1.json (31 October 2026); it was not recorded here until v15. The version 18 SPL (sections 5, 7, 11, 12.1 and the drug-interaction part of 12.3) was read on 18 November 2026 for the drug catalogue entries.",
}
v15['supersedes'] = {"file": "intelligence_store/data/dataset_ledger_v14.json", "sha256": hashlib.sha256(v14_raw).hexdigest(),
    "ledger_version": v14['ledger_version'],
    "change": "Adds the NINLARO label as a seen dataset: the 2024 label behind the ixazomib label extract (read 31 October 2026, not recorded until now) and the DailyMed version 18 SPL read for the drug catalogue. No uses change."}
v15['supersedes'] = {k: v15['supersedes'][k] for k in v14['supersedes']}
ledger_sha = dump('dataset_ledger_v15.json', v15, indent=1)
print(json.dumps({'alias': alias_sha, 'safety': safety_sha, 'interactions': inter_sha, 'annotations': annot_sha, 'ledger': ledger_sha,
                  'ledger_v14': hashlib.sha256(v14_raw).hexdigest()}, indent=1))
