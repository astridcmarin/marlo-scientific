"""What is known about lenalidomide in dialysis (reviewer's checklist R7, 6 November 2026).

Gathered from pinned sources, side by side; nothing is modelled. Dialysis is not part of any platform model: the
pathway model's end-stage check (2.0c) was inconclusive because residual kidney function was not reported, and
neither population model has a dialysis process. Ratios marked derived are the platform's arithmetic on reported means.
"""
import hashlib
import json
from pathlib import Path

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = 'intelligence_store/data/'
VIEW_VERSION = 'dialysis-evidence-v1.0'
SOURCES = {
    'esrd': (DATA + 'lenalidomide_esrd_dialysis_evidence_v1.json', '7769bba1cad79392919ba02a36a24617cf2aa7bec2cfebdb2f6bc5d935c1d2b6',
             'EMA 2008 assessment report (EMEA/CHMP/249329/2008), CC-5013-PK-001 end-stage groups'),
    'ema_2013': (DATA + 'lenalidomide_renal_pk_ema_2013_v1.json', '04f2e629ded43713062e0d68d668939a4a2cecd5a9db7ce349874e81529f6501',
                 'EMA 2013 assessment report (EMA/297642/2013), page 18'),
    'label': (DATA + 'lenalidomide_label_2023_v1.json', 'd4b02134613dc45d6b039999b37d9c94ccbc047cc0b7e811b77278c868e47a9a',
              'REVLIMID prescribing information, revision 3/2023, Table 3'),
    'label_pk': (DATA + 'lenalidomide_label_2023_pk_v1.json', '821673b5f99364ef1c88ff952c3670d01006ccb6b3bf06a3b3cebeebceda8283',
                 'REVLIMID prescribing information, revision 3/2023, section 12.3'),
    'bridoux': (DATA + 'lenalidomide_bridoux_observed_v2.json', 'cc8c41123d6305dd3ab783ae53e87d0ab8c15f32f04b21cc45d4c9a2bc4de8ee',
                'Bridoux et al. 2016, Table 2'),
}


class DialysisEvidenceError(ValueError):
    pass


def _load():
    docs = {}
    for alias, (path, sha, _t) in SOURCES.items():
        raw = (ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise DialysisEvidenceError(f'{path} is missing or changed; the dialysis summary was not built.')
        docs[alias] = json.loads(raw)
    return docs


def build():
    d = _load()
    g = {x['group']: x for x in d['esrd']['groups']}
    off, on = g['esrd_off_dialysis'], g['esrd_on_dialysis']
    row = next(r for r in d['label']['renal_dose_adjustments']['rows'] if r['dialysis'])
    b = d['bridoux']['groups']['esrd']
    view = {
        'view_version': VIEW_VERSION, 'drug': 'lenalidomide',
        'cc5013': {
            'design_quote': d['esrd']['study']['esrd_design_quote'], 'location': d['esrd']['study']['location'], 'n': off['n'],
            'paired_note': d['esrd']['notes'][0],
            'rows': [
                {'quantity': 'AUCinf (h·ng/mL), mean (SD)', 'off': off['auc_ng_h_ml'], 'on': on['auc_ng_h_ml'],
                 'ratio_on_to_off': on['auc_ng_h_ml'][0] / off['auc_ng_h_ml'][0]},
                {'quantity': 'CL/F (mL/min), mean (SD)', 'off': off['cl_f_ml_min'], 'on': on['cl_f_ml_min'],
                 'ratio_on_to_off': on['cl_f_ml_min'][0] / off['cl_f_ml_min'][0]},
                {'quantity': 'Cmax (ng/mL), mean (SD)', 'off': off['cmax_ng_ml'], 'on': on['cmax_ng_ml'],
                 'ratio_on_to_off': on['cmax_ng_ml'][0] / off['cmax_ng_ml'][0]},
                {'quantity': 'Terminal half-life (h), mean (SD)', 'off': off['t_half_h'], 'on': on['t_half_h'], 'ratio_on_to_off': None},
            ],
            'not_reported': d['esrd']['not_reported'],
        },
        'removal': [
            {'source': SOURCES['ema_2013'][2], 'text': f"Mean dialysis clearance {d['ema_2013']['dialysis']['mean_dialysis_clearance_ml_min']} mL/min; "
                                                       f"{d['ema_2013']['dialysis']['percent_removed_by_4_hour_haemodialysis']}% removed by a 4-hour haemodialysis."},
            {'source': SOURCES['label_pk'][2], 'text': '“' + d['label_pk']['renal_dialysis']['quote'] + '”'},
        ],
        'myeloma': {'source': SOURCES['bridoux'][2], 'n': b['n'], 'regimen': b['regimen'], 'auc24_gm': b['auc24_gm'],
                    'auc24_gcv_pct': b['auc24_gcv_pct'], 't_half_gm_h': b['t_half_gm_h'], 'note': b['note']},
        'label_row': {'regimen': row['mm_combination'], 'maintenance_and_mds': row['mm_maintenance_and_mds'], 'source': SOURCES['label'][2]},
        'modelling': ('Not modelled. The kidney pathway model\'s end-stage check (2.0c) could not be decided, because the '
                      'subjects\' residual kidney function was not reported; neither published population model has a dialysis '
                      'process.'),
        'derived_note': 'On/off ratios are the platform\'s arithmetic on the reported means of the same six subjects (paired); no '
                        'interval is given because only means and SDs were reported.',
        'sources': [{'alias': a, 'file': p, 'sha256': s, 'title': t} for a, (p, s, t) in SOURCES.items()],
        'clinical_prediction_validated': False,
    }
    view['view_sha256'] = digest(view)
    return view
