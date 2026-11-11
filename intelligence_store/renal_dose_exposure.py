"""Label kidney doses beside reported exposure, from three sources (reviewer's checklist R9, 5 November 2026). Not a judgement
of the label's doses.

Descriptive only. Three pinned sources answer it in different ways, and none is a new model run:
- Bridoux 2016: myeloma patients already on reduced doses, day 5 AUC24 by group (observed; reference: normal function,
  25 mg). Ratio = group geometric mean / normal geometric mean.
- CC-5013-PK-001 (EMA 2013 Table 4): single 25 mg dose, AUCinf ratio to normal + mild. Scaled to the label's average daily
  dose by linear, time-invariant kinetics (the label states AUC rises in proportion to dose), under which steady-state
  AUC over a dosing interval equals single-dose AUCinf whatever the accumulation, so ratio x dose / 25 is the expected
  steady-state ratio on the label dose. Derived by the platform; the 90% interval is scaled the same way.
- The sponsor's simulation (EMA 2013 Table 7): steady-state average daily AUC on candidate regimens, by superposition of
  CC-5013-PK-001 data. A model prediction, not an observation.

The platform sets no threshold for "restores" and proposes no dose: the ratios are shown with their reference groups,
populations and measures, which differ between sources.
"""
import hashlib
import json
import math
from pathlib import Path

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = 'intelligence_store/data/'
VIEW_VERSION = 'renal-dose-exposure-v1.0'
SOURCES = {
    'bridoux': (DATA + 'lenalidomide_bridoux_observed_v2.json', 'cc8c41123d6305dd3ab783ae53e87d0ab8c15f32f04b21cc45d4c9a2bc4de8ee',
                'Bridoux et al. 2016, Table 2 (myeloma patients, day 5)'),
    'bridoux_design': (DATA + 'lenalidomide_bridoux_design_v1.json', '1af2d005528a18088382225482a3eaa32ac3c68f4f6529c5ee7958e8c1605eac',
                       'Bridoux et al. 2016, study design'),
    'ema_2013': (DATA + 'lenalidomide_renal_pk_ema_2013_v1.json', '04f2e629ded43713062e0d68d668939a4a2cecd5a9db7ce349874e81529f6501',
                 'EMA 2013 assessment report (EMA/297642/2013), Tables 4 and 7'),
    'label': (DATA + 'lenalidomide_label_2023_v1.json', 'd4b02134613dc45d6b039999b37d9c94ccbc047cc0b7e811b77278c868e47a9a',
              'REVLIMID prescribing information, revision 3/2023, Table 3'),
}
REFERENCE_DOSE_MG = 25
# Label Table 3 row (0-based) -> Bridoux group and EMA 2013 Table 4 group that received or describe that band.
BANDS = (
    {'id': 'moderate', 'label_row': 0, 'bridoux': 'moderate', 'ema': 'moderate', 'sponsor': None},
    {'id': 'severe', 'label_row': 1, 'bridoux': 'severe', 'ema': 'severe', 'sponsor': 'severe, not on dialysis'},
    {'id': 'dialysis', 'label_row': 2, 'bridoux': 'esrd', 'ema': 'esrd_off_dialysis', 'sponsor': None},
)
def ratio_interval(gm_a, gcv_a, n_a, gm_b, gcv_b, n_b, level=0.90):
    """Approximate interval for a ratio of two independent geometric means (a / b), from each group's geometric CV and
    n, assuming log-normal values: log SD = sqrt(ln(1 + GCV^2)), Welch standard error and degrees of freedom, t quantile.
    Derived by the platform from published summaries, not reported by the source."""
    from scipy.stats import t as student_t
    s2a, s2b = math.log(1 + (gcv_a / 100) ** 2), math.log(1 + (gcv_b / 100) ** 2)
    va, vb = s2a / n_a, s2b / n_b
    se = math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (n_a - 1) + vb ** 2 / (n_b - 1))
    q = student_t.ppf(0.5 + level / 2, df)
    centre = math.log(gm_a / gm_b)
    return {'lower': math.exp(centre - q * se), 'upper': math.exp(centre + q * se), 'level': level, 'df': df}


NOTES = {
    'threshold': "Bridoux's first dose reduction was at 50 mL/min, as in the renal study's publication (Chen 2007): its mild "
                 "group (50-80) received 25 mg, while the current US label's first reduction starts at 60 mL/min. Its moderate "
                 "group is 30 to < 50 mL/min. The same applies to the CC-5013-PK-001 column: its moderate group is 30 to < 50 "
                 "mL/min by measured clearance, against the label band of 30 to 60 by Cockcroft-Gault, and its reference pool "
                 "(normal + mild, 50 mL/min and above) contains subjects the label would dose-reduce.",
    'scaling': 'Scaled by linear, time-invariant kinetics: the label states that AUC rises in proportion to dose, and under '
               'linear kinetics steady-state AUC over one dosing interval equals single-dose AUCinf whatever the accumulation '
               '(which is real in impaired kidney function: about 1.5-fold on daily dosing at the end-stage half-life). So a '
               'single-dose AUCinf ratio times dose / 25 mg is the expected steady-state ratio on that dose. Derived by the '
               'platform; not an observation.',
    'dialysis': 'The CC-5013-PK-001 ratio for end-stage disease was measured off dialysis. Whether Bridoux sampled its '
                'dialysis patients on a dialysis day is not recorded in the platform\'s design extract. Dialysis removes about 30% '
                'of the drug in a 4-hour session (label).',
    'interval': 'Bridoux intervals are approximate 90% intervals derived by the platform from each group\'s geometric mean, '
                'geometric CV and n (log-normal values, Welch t interval); the paper reports no interval for these ratios. '
                'They describe the group means, not the spread between patients.',
    'no_threshold': 'The platform sets no threshold for "restores" and proposes no dose. The sources differ in population '
                    '(myeloma patients, non-malignant renal impairment), reference group, kidney-function measure and timing.',
}


class RenalDoseExposureError(ValueError):
    pass


def _load():
    docs = {}
    for alias, (path, sha, _t) in SOURCES.items():
        raw = (ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise RenalDoseExposureError(f'{path} is missing or changed; the comparison was not built.')
        docs[alias] = json.loads(raw)
    return docs


def build():
    d = _load()
    groups = d['bridoux']['groups']
    ref = groups['normal']
    t4 = d['ema_2013']['table_4_geometric_mean_ratios']
    t7 = d['ema_2013']['sponsor_simulation_table_7']['rows']
    sponsor_ref = next(r for r in t7 if r['regimen'].startswith('25 mg q24h'))
    rows = d['label']['renal_dose_adjustments']['rows']
    out = []
    for band in BANDS:
        row = rows[band['label_row']]
        dose = row['mm_combination_average_daily_mg']
        g = groups[band['bridoux']]
        bridoux = {'group': band['bridoux'], 'definition': d['bridoux_design']['design']['groups']['definition'][band['bridoux']],
                   'n': g['n'], 'regimen': g['regimen'], 'dose_mg_per_24h': g['dose_mg_per_24h'],
                   'auc24_gm': g['auc24_gm'], 'auc24_gcv_pct': g['auc24_gcv_pct'],
                   'ratio_to_normal': g['auc24_gm'] / ref['auc24_gm'],
                   'ratio_ci90': ratio_interval(g['auc24_gm'], g['auc24_gcv_pct'], g['n'], ref['auc24_gm'], ref['auc24_gcv_pct'], ref['n']),
                   'same_dose_as_label': g['dose_mg_per_24h'] == dose}
        gmr = t4['auc_infinity'][band['ema']]
        scale = dose / REFERENCE_DOSE_MG
        cc5013 = {'group': band['ema'], 'definition': t4['group_definitions_measured_clcr'][band['ema']],
                  'gmr_25_mg_pct': gmr[0], 'ci90_pct': gmr[1:], 'scale': scale,
                  'scaled_ratio': gmr[0] / 100 * scale, 'scaled_ci90': [gmr[1] / 100 * scale, gmr[2] / 100 * scale]}
        sponsor = None
        if band['sponsor']:
            sponsor = [{'regimen': r['regimen'], 'auc_avg_ss': r['auc_avg_ss_ng_h_ml'], 'ratio': r['auc_avg_ss_ng_h_ml'] / sponsor_ref['auc_avg_ss_ng_h_ml']}
                       for r in t7 if r['renal_function'] == band['sponsor'] and '(MM)' in r['regimen']]
        out.append({'band': band['id'], 'label_range': row['crcl_ml_min'], 'label_dialysis': row['dialysis'],
                    'label_regimen': row['mm_combination'], 'label_average_daily_mg': dose,
                    'bridoux': bridoux, 'cc5013': cc5013, 'sponsor': sponsor})
    view = {
        'view_version': VIEW_VERSION, 'drug': 'lenalidomide', 'bands': out,
        'references': {
            'bridoux': f"normal function (CrCl > 80 mL/min), 25 mg once daily: AUC24 {ref['auc24_gm']} h·ng/mL (geometric mean, n = {ref['n']})",
            'cc5013': t4['definition'],
            'sponsor': f"{sponsor_ref['renal_function']}, {sponsor_ref['regimen']}: {sponsor_ref['auc_avg_ss_ng_h_ml']} h·ng/mL",
        },
        'mild_bridoux': {'n': groups['mild']['n'], 'dose_mg_per_24h': groups['mild']['dose_mg_per_24h'],
                         'ratio_to_normal': groups['mild']['auc24_gm'] / ref['auc24_gm'],
                         'ratio_ci90': ratio_interval(groups['mild']['auc24_gm'], groups['mild']['auc24_gcv_pct'], groups['mild']['n'],
                                                      ref['auc24_gm'], ref['auc24_gcv_pct'], ref['n'])},
        'label_average_dose_note': d['label']['renal_dose_adjustments']['average_daily_dose_note'],
        'sponsor_kind': d['ema_2013']['sponsor_simulation_table_7']['kind'],
        'notes': NOTES,
        'sources': [{'alias': a, 'file': p, 'sha256': s, 'title': t} for a, (p, s, t) in SOURCES.items()],
        'clinical_prediction_validated': False,
    }
    view['view_sha256'] = digest(view)
    return view
