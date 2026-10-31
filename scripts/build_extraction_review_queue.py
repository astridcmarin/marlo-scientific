"""Builds intelligence_store/data/extraction_review_queue_v1.json from pinned extracts (run once; the output is pinned)."""
import json, hashlib, re
import os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
SKIP = {'rse_pct', 'rse_percent', 'log_estimate', 'bootstrap_ci95', 'shrinkage_percent', 'representative_crcl', 'fat_free_mass_kg'}
def esc(t): return str(t).replace('~', '~0').replace('/', '~1')
def walk(node, ptr, loc, out, names=()):
    if isinstance(node, dict):
        loc = node.get('location') or node.get('source_location') or loc
        for k, v in node.items():
            if k in SKIP or k in ('location', 'source_location') or k.endswith('_location') or k.endswith('average_daily_mg'): continue
            walk(v, ptr + '/' + esc(k), node.get(k + '_location') or node.get(k.rsplit('_', 1)[0] + '_location') or loc, out, names + (k,))
    elif isinstance(node, list):
        if node and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in node):
            out.append((ptr, node, loc, names))
        else:
            for i, v in enumerate(node):
                nm = (v.get('group') or v.get('id') or (f"CLcr {v['crcl_ml_min'][0] if v['crcl_ml_min'][0] is not None else 'below'}-{v['crcl_ml_min'][1]}{' dialysis' if v.get('dialysis') else ''}" if 'crcl_ml_min' in v else None) or str(i)) if isinstance(v, dict) else str(i)
                walk(v, ptr + f'/{i}', loc, out, names + (nm,))
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append((ptr, node, loc, names))
    elif isinstance(node, str) and ptr.endswith(('/mm_combination', '/mm_maintenance_and_mds')):
        out.append((ptr, node, loc, names))
def resolve(doc, ptr):
    for t in ptr[1:].split('/'):
        t = t.replace('~1', '/').replace('~0', '~')
        doc = doc[int(t)] if isinstance(doc, list) else doc[t]
    return doc
def label(names):
    toks = [t for t in names if t != 'value']
    return ' › '.join(t.replace('_', ' ') for t in toks)
GROUPS = [
 dict(id='lenalidomide_hughes_parameters', priority=1, file='intelligence_store/data/hughes_parameter_extract_v1.json', subtrees=['/parameters'],
      where='Hughes et al. Br J Clin Pharmacol 2019;85:924-934, Table 2 (final model) and Equation 4', used_by='Patient Lab Hughes curves, dose view, scope'),
 dict(id='lenalidomide_hughes_variability', priority=1, file='intelligence_store/data/hughes_variability_extract_v1.json', subtrees=['/random_effects', '/residual_error'],
      where='Hughes 2019 Supplementary Material 2 (final control stream: $OMEGA BLOCK(2), $OMEGA, RUV_PROP) and Table 2', fallback='Supplementary Material 2, final control stream', used_by='Between-patient ranges on the dose view and Patient Lab'),
 dict(id='lenalidomide_kim_parameters', priority=1, file='intelligence_store/data/kim_2026_model_extract_v1.json', subtrees=['/parameters', '/random_effects'],
      where='Kim et al. Drug Des Devel Ther 2026, Table 3', fallback='Table 3', used_by='Patient Lab Kim curves, dose view, scope'),
 dict(id='lenalidomide_renal_groups', priority=1, file='landscape_ui/data/renal_pk/renal_pk_group_evidence_v1.json', subtrees=['/groups'],
      where='EMA withdrawal assessment report EMEA/CHMP/249329/2008 (committed: landscape_ui/data/renal_pk/ema_lenalidomide_2008.pdf), PDF pages 20-21', fallback='PDF page 20, Renal Function Groups', used_by='25 mg reference exposure, Hughes and Kim outside checks, special populations'),
 dict(id='lenalidomide_exposure_safety', priority=1, file='intelligence_store/data/lenalidomide_exposure_safety_v2.json', subtrees=['/odds_ratios_multiple_myeloma'],
      where='TGA AusPAR lenalidomide 2016, Attachment 2 (Clinical Evaluation Report), section 4.2.4.1', fallback='Section 4.2.4.1', used_by='Relative cytopenia odds on the dose view and Patient Lab'),
 dict(id='lenalidomide_label', priority=1, file='intelligence_store/data/lenalidomide_label_2023_v1.json', subtrees=['/multiple_myeloma_dosing', '/renal_dose_adjustments/rows'],
      where='REVLIMID prescribing information, revised 3/2023: sections 2.1, 2.6 (Table 3) and 3', fallback='Section 2.6, Table 3, PDF page 12', used_by='Dose view and special populations (quoted)'),
 dict(id='ixazomib_parameters', priority=1, file='intelligence_store/data/ixazomib_pk_gupta_2017_extract_v1.json', subtrees=['/parameters', '/covariates'],
      where='Gupta et al. Clin Pharmacokinet 2017;56:1355-1368, Table 3', used_by='Ixazomib exposure page'),
 dict(id='pomalidomide_label', priority=1, file='intelligence_store/data/label_pk_pomalidomide_v1.json', subtrees=[''],
      where='POMALYST prescribing information, revised 2/2025: sections 2 and 12.3', used_by='Pomalidomide label-based exposure page'),
 dict(id='dexamethasone_label', priority=1, file='intelligence_store/data/label_pk_dexamethasone_hemady_v1.json', subtrees=[''],
      where='HEMADY prescribing information, revised 1/2026: sections 2 and 12.3', used_by='Dexamethasone label-based exposure page'),
 dict(id='daratumumab_parameters', priority=2, file='intelligence_store/data/daratumumab_pk_luo_2021_extract_v1.json', subtrees=['/parameters'],
      where='Luo et al. J Clin Pharmacol 2021;61:614-627, Supplementary Table S1', used_by='Daratumumab outside checks only; not run on any page'),
]
out = {'schema_version': 'extraction-review-queue-v1', 'queue_version': 'extraction-review-queue-v1.0', 'recorded_on': '2026-10-31',
       'purpose': 'Values that feed a calculation or a quoted dose on the platform, for review against the original source by the platform owner. Each value resolves by JSON pointer into a pinned file.',
       'excluded': 'Values the platform derives itself (for example the average daily dose of an every-other-day regimen) and uncertainty statistics (RSE, bootstrap intervals) are not listed.',
       'decisions': {'matches': 'The value matches the source at the stated location.', 'wrong': 'The value does not match the source (note what the source says).', 'cannot_check': 'The source or location could not be checked.'},
       'groups': []}
n = 0
for g in GROUPS:
    raw = open(ROOT + g['file'], 'rb').read(); doc = json.loads(raw)
    items = []
    for sub in g['subtrees']:
        found = []
        walk(resolve(doc, sub) if sub else doc, sub, None, found)
        for ptr, val, loc, names in found:
            items.append({'id': f"{g['id']}:{ptr}", 'label': label(names), 'pointer': ptr, 'value': val,
                          'location': loc or g.get('fallback') or 'see source note'})
    n += len(items)
    out['groups'].append({'id': g['id'], 'priority': g['priority'], 'file': g['file'], 'sha256': hashlib.sha256(raw).hexdigest(),
                          'where_to_look': g['where'], 'used_by': g['used_by'], 'items': items})
json.dump(out, open(ROOT + 'intelligence_store/data/extraction_review_queue_v1.json', 'w'), indent=1, ensure_ascii=False)
open(ROOT + 'intelligence_store/data/extraction_review_queue_v1.json', 'a').write('\n')
print('items', n)
