"""Digital human 1.0, step 1.4: the observed-data context shown beside the lenalidomide body map.

What the renal-impairment study actually observed (CC-5013-PK-001), next to what the pathway model shows, plus the
label's renal dose steps. Nothing here is a new calculation of the model: the model numbers are copied from the
body-map view, and the observed values are copied from pinned extracts. The one evaluated formula is the EMA 2013
regression of renal clearance on measured creatinine clearance, shown as context only, because it was fitted to the
same subjects as the model's calibration and so cannot check it.

Group values describe subjects whose measured creatinine clearance fell in a band; they are not values at the exact
creatinine clearance chosen on the page.

Plan: docs/DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md, "What it shows", item 4 (approved 31 October 2026).
"""
import hashlib
import json
from pathlib import Path

from .lenalidomide_label import EXTRACT_SHA256 as LABEL_SHA256, load_label_extract
from .lenalidomide_renal_pathways import EVIDENCE_SHA256, load_evidence
from .patient_state import digest

SCHEMA_VERSION = 'body-map-context-v1'
EMA_2013_PATH = Path(__file__).parent / 'data' / 'lenalidomide_renal_pk_ema_2013_v1.json'
EMA_2013_SHA256 = '04f2e629ded43713062e0d68d668939a4a2cecd5a9db7ce349874e81529f6501'

# Body-map band -> group key in each source.
GROUP_2008 = {'normal': 'normal', 'mild': 'mild', 'moderate': 'moderate', 'severe': 'severe_without_dialysis'}
GROUP_2013 = {'normal': 'normal', 'mild': 'mild', 'moderate': 'moderate', 'severe': 'severe'}
BAND_LABEL = {'normal': 'Normal (> 80 mL/min)', 'mild': 'Mild (50-80 mL/min)', 'moderate': 'Moderate (30 to < 50 mL/min)',
              'severe': 'Severe, not on dialysis (< 30 mL/min)'}
REGRESSION_NOTE = ('Fitted by the EMA to the same subjects the pathway model was calibrated on, so it cannot check the '
                   'model; shown as context only. Its x-axis is creatinine clearance measured from urine.')
GROUP_NOTE = ('Observed values are group summaries for 5-7 subjects whose measured creatinine clearance fell in the band, '
              'not values at the exact creatinine clearance shown on the map.')


class BodyMapContextError(ValueError):
    pass


def load_ema_2013(path=EMA_2013_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != EMA_2013_SHA256:
        raise BodyMapContextError('EMA 2013 renal PK extract is missing or changed; the context panel was not built.')
    data = json.loads(raw)
    if data.get('schema_version') != 'renal-pk-group-summary-v1':
        raise BodyMapContextError('Unsupported EMA 2013 extract schema.')
    return data


def _label_row(rows, crcl):
    """The label Table 3 row (not on dialysis) whose creatinine-clearance range contains `crcl`, or None."""
    for i, row in enumerate(rows):
        lo, hi = row['crcl_ml_min']
        if row['dialysis']:
            continue
        if lo is None and crcl < hi:
            return i
        if lo is not None and lo <= crcl <= hi:
            return i
    return None


def body_map_context(view):
    """Observed context for a completed body-map view (explorer or record mode)."""
    if view.get('status') != 'completed':
        raise BodyMapContextError('The context panel needs a completed body-map view.')
    ema08, ema13, label = load_evidence(), load_ema_2013(), load_label_extract()
    band = view['band']['id']
    crcl = view['crcl_ml_min']
    groups08 = {g['group']: g for g in ema08['groups']}
    t3, t4 = ema13['table_3_geometric_means'], ema13['table_4_geometric_mean_ratios']
    normal08, here08 = groups08['normal'], groups08[GROUP_2008[band]]
    g13 = GROUP_2013[band]
    flows = {f['kind']: f for f in view['flows']}
    totals = view['totals']

    comparison = [
        {'quantity': 'Exposure at the same dose, relative to normal function',
         'model': totals['relative_exposure_same_dose'], 'model_note': 'typical value at this creatinine clearance',
         'observed': [{'statistic': 'ratio of arithmetic mean AUC to the normal group (EMA 2008)',
                       'value': here08['auc_ng_h_ml'][0] / normal08['auc_ng_h_ml'][0], 'derived': True},
                      {'statistic': 'ratio of geometric mean AUCinf to the normal group (EMA 2013)',
                       'value': t3['auc_infinity'][g13]['geometric_mean'] / t3['auc_infinity']['normal']['geometric_mean'],
                       'derived': True}],
         'unit': 'ratio'},
        {'quantity': 'Dose leaving unchanged in urine',
         'model': 100 * totals['fraction_excreted_unchanged'], 'model_note': 'typical value at this creatinine clearance',
         'observed': [{'statistic': 'arithmetic mean (EMA 2008)', 'value': here08['fe_percent'], 'derived': False},
                      {'statistic': f"geometric mean, CV {t3['urine_excretion_pct_dose'][g13]['cv_pct']}% (EMA 2013)",
                       'value': t3['urine_excretion_pct_dose'][g13]['geometric_mean'], 'derived': False}],
         'unit': '% of dose'},
        {'quantity': 'Renal clearance',
         'model': flows['renal_excretion']['value'], 'model_note': 'filtration + secretion at this creatinine clearance',
         'observed': [{'statistic': f"geometric mean, CV {t3['renal_clearance'][g13]['cv_pct']}% (EMA 2013)",
                       'value': t3['renal_clearance'][g13]['geometric_mean'], 'derived': False}],
         'unit': 'mL/min'},
        {'quantity': 'Total apparent clearance (CL/F)',
         'model': totals['total_ml_min'], 'model_note': 'renal + non-renal at this creatinine clearance (bioavailability taken as 1)',
         'observed': [{'statistic': f"arithmetic mean, SD {here08['cl_f_ml_min'][1]} (EMA 2008)",
                       'value': here08['cl_f_ml_min'][0], 'derived': False},
                      {'statistic': f"geometric mean, CV {t3['cl_f'][g13]['cv_pct']}% (EMA 2013)",
                       'value': t3['cl_f'][g13]['geometric_mean'], 'derived': False}],
         'unit': 'mL/min'},
    ]

    ratios = None
    if band in ('moderate', 'severe'):
        gmr, cmax = t4['auc_infinity'][g13], t4['cmax'][g13]
        ratios = {'definition': t4['definition'], 'location': t4['location'],
                  'auc_infinity_pct': {'ratio': gmr[0], 'ci90': [gmr[1], gmr[2]]},
                  'cmax_pct': {'ratio': cmax[0], 'ci90': [cmax[1], cmax[2]]},
                  'note': 'The reference group pools normal and mild subjects, so these ratios differ from the '
                          'normal-only ratios above.'}

    reg = ema13['figure_1_regressions']['renal_clearance']
    regression = {'equation': reg['equation'], 'r_squared': reg['r_squared'], 'location': ema13['figure_1_regressions']['location'],
                  'value_at_crcl_ml_min': reg['intercept'] + reg['slope'] * crcl,
                  'model_value_ml_min': flows['renal_excretion']['value'], 'note': REGRESSION_NOTE}

    rd = label['renal_dose_adjustments']
    match = _label_row(rd['rows'], crcl)
    label_rows = [{'crcl_ml_min': r['crcl_ml_min'], 'dialysis': r['dialysis'], 'mm_combination': r['mm_combination'],
                   'mm_maintenance_and_mds': r['mm_maintenance_and_mds'], 'matches': i == match}
                  for i, r in enumerate(rd['rows'])]

    context = {
        'schema_version': SCHEMA_VERSION, 'drug': 'lenalidomide', 'crcl_ml_min': crcl, 'band': band,
        'band_label': BAND_LABEL[band], 'band_status': view['band']['status'], 'view_sha256': view['view_sha256'],
        'study': {'id': 'CC-5013-PK-001', 'design': 'single 25 mg oral dose, fasting; groups by measured creatinine clearance',
                  'n': {'2008': here08['n'], '2013': ema13['groups'][g13]['n']}},
        'comparison': comparison, 'group_note': GROUP_NOTE, 'geometric_mean_ratios': ratios, 'regression': regression,
        'label': {'table': rd['table'], 'rows': label_rows, 'matched_row': match,
                  'no_row_note': None if match is not None else 'The label table has no row for this creatinine clearance.',
                  'threshold_note': rd['upper_bound_note'],
                  'statement': 'Quoted from the prescribing information (revision 3/2023). The platform proposes no dose.'},
        'sources': [
            {'label': 'EMA 2008 withdrawal assessment report (arithmetic means)', 'reference': ema08['source']['document_reference'],
             'pages': ema08['source']['pages'], 'sha256': EVIDENCE_SHA256},
            {'label': 'EMA 2013 variation assessment report (geometric means, ratios, regressions)',
             'reference': ema13['source']['document_reference'], 'pages': ema13['source']['pages'], 'sha256': EMA_2013_SHA256},
            {'label': 'REVLIMID prescribing information, revision 3/2023 (Table 3)', 'reference': label['source']['document'][:80],
             'pages': 'Section 2.6', 'sha256': LABEL_SHA256}],
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
    }
    context['context_sha256'] = digest(context)
    return context
