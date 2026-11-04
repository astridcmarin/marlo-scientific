"""Digital human 1.0, step 1.2: the lenalidomide elimination body map as data (body-map-view-v1).

Where lenalidomide leaves the body at a given creatinine clearance: kidney filtration, kidney tubular secretion and
non-renal routes. No new model: the numbers come from the Simulation 2.0a pathway model under the intact-nephron
reading, exactly as on the 2.0b patient page (same calibration, reading and unbound fraction), plus the alternative
filtration/secretion split recorded in lenalidomide_pathway_unbound_fraction_assessment_v1.json (the owner's decision:
show both; exposure is the same under both). Each flow carries the evidence status of its kidney-function band, read
from the locked 2.0a report, so the map cannot look more certain than the check.

Nodes carry UBERON anatomy IDs so later drugs and organs reuse one vocabulary. The arrows are clearance flows, not
amounts or concentrations in organs: no source gives lenalidomide tissue concentrations.

Plan: docs/DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md (approved 31 October 2026).

Digital human 1.1, step 1.1b (body-map-view-v2): adds reference renal blood flow (ICRP 89 reference male, not
adjusted for kidney function) and the share of drug reaching the kidneys that leaves in urine in one pass (renal
extraction). Extraction = renal blood clearance / renal blood flow, where renal blood clearance = renal plasma
clearance / blood-to-plasma ratio (0.931, Chen 2012, assumed). It inherits the band's evidence status. Plan:
docs/DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md (approved 3 November 2026).
"""
import hashlib
import json
import math
from pathlib import Path

from .lenalidomide_renal_pathways import (EVIDENCE_SHA256, METHOD_VERSION as PATHWAY_METHOD, REPORT_PATH,
                                          calibrate, load_evidence, pathways)
from .patient_renal_pathways import CALIBRATION_CRCL, FU, READING
from .patient_state import digest
from .reference_physiology import CHEN_SHA256, ICRP_SHA256, load_blood_plasma, renal_flows

DATA = Path(__file__).parent / 'data'
SCHEMA_VERSION = 'body-map-view-v2'
METHOD_VERSION = 'lenalidomide-body-map-v1.1'
DRUG = 'lenalidomide'
RANGE = (10.0, 140.0)

PATHWAY_REPORT_SHA256 = '163b5ca1a95a7f3d745c8e25a93ef58d4bedd0e1e48d6e4bfdfb4a25457a93d5'
# Simulation 2.0d report: its comparator (the current model, k = 1) against two myeloma studies not used to fit it.
MYELOMA_REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'lenalidomide_renal_pathways_check_v2.json'
MYELOMA_REPORT_SHA256 = '277108de99726588a04c11468e7004f93068d6fa0ca3372ae5c564dbe756dbdd'
# Simulation 2.0e report: the 2.0a comparison across bioavailability F (plan v3). It decides the moderate and severe band status.
F_REPORT_PATH = Path(__file__).resolve().parent.parent / 'docs' / 'verification' / 'lenalidomide_renal_pathways_check_v3.json'
F_REPORT_SHA256 = 'a60437cc58e174c88b79434a6eee104455995bf64cd0f935f8c39f4877615533'
F_BANDS = {'moderate': 'moderate', 'severe': 'severe'}
MYELOMA_GROUPS = {'moderate': {'bridoux': 'moderate', 'kim': 'moderate'}, 'severe': {'bridoux': 'severe', 'kim': 'severe'}}
FU_RECORD_PATH = DATA / 'lenalidomide_pathway_unbound_fraction_assessment_v1.json'
FU_RECORD_SHA256 = '8796799193207c3fffb9001e6a6d1cd6ad45f165c94a5986c944cf47a2faa7df'

# Anatomy vocabulary (UBERON IDs checked against the ontology on 31 October 2026).
NODES = [
    {'id': 'gut', 'label': 'Digestive tract (oral dose)', 'uberon_id': 'UBERON:0001555'},
    {'id': 'plasma', 'label': 'Blood plasma', 'uberon_id': 'UBERON:0001969'},
    {'id': 'kidney', 'label': 'Kidney', 'uberon_id': 'UBERON:0002113'},
    {'id': 'glomerulus', 'label': 'Glomerulus (filtration)', 'uberon_id': 'UBERON:0000074', 'parent': 'kidney'},
    {'id': 'tubule', 'label': 'Renal tubule (secretion)', 'uberon_id': 'UBERON:0009773', 'parent': 'kidney'},
    {'id': 'urine', 'label': 'Urine (unchanged drug)', 'uberon_id': 'UBERON:0001088'},
    {'id': 'non_renal', 'label': 'Non-renal routes', 'uberon_id': None,
     'note': 'Everything that is not unchanged drug in urine; the source does not identify the routes (not via cytochrome P450).'},
]

# Kidney-function bands as the study defined its groups (creatinine clearance, mL/min): normal > 80, mild 50-80
# (both ends included), moderate 30 to < 50, severe < 30 not on dialysis. Outer ends are the map's drawn range.
BANDS = [
    {'id': 'normal', 'range': [80.0, RANGE[1]], 'lower_inclusive': False, 'upper_inclusive': True, 'report_group': None},
    {'id': 'mild', 'range': [50.0, 80.0], 'lower_inclusive': True, 'upper_inclusive': True, 'report_group': 'mild'},
    {'id': 'moderate', 'range': [30.0, 50.0], 'lower_inclusive': True, 'upper_inclusive': False, 'report_group': 'moderate'},
    {'id': 'severe', 'range': [RANGE[0], 30.0], 'lower_inclusive': True, 'upper_inclusive': False,
     'report_group': 'severe_without_dialysis'},
]
STATUS_TEXT = {
    'calibrated': 'Calibrated: the model was fitted to the normal-function group.',
    'checked_consistent': 'Checked: consistent with the observed group in every scenario of the locked check.',
    'consistent_primary_only': 'Consistent with the observed group in the primary scenario only; not in every scenario of the locked check.',
    'check_disagrees': ('Source study disagrees: in this band of CC-5013-PK-001 (the study the model was calibrated on, whose '
                        'impaired groups were not used for fitting) the model predicts less exposure than observed.'),
    'depends_on_bioavailability': ('The result in this band depends on how much of the dose is absorbed, which was not measured.'),
}


class BodyMapError(ValueError):
    pass


def _pinned(path, sha256, label):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise BodyMapError(f'{label} is missing or changed; the map was not built.')
    return json.loads(raw)


def load_fu_record():
    return _pinned(FU_RECORD_PATH, FU_RECORD_SHA256, 'Unbound-fraction decision record')


def load_pathway_report():
    return _pinned(REPORT_PATH, PATHWAY_REPORT_SHA256, 'Simulation 2.0a pathway report')


def band_for(crcl):
    """The study band for a creatinine clearance (the study's own boundary conventions)."""
    for band in BANDS:
        lo, hi = band['range']
        above = crcl >= lo if band['lower_inclusive'] else crcl > lo
        below = crcl <= hi if band['upper_inclusive'] else crcl < hi
        if above and below:
            return band
    return None


def myeloma_note(band_id):
    """For the moderate and severe bands: how the current model compares with Bridoux 2016 and Kim 2026 (Simulation 2.0d
    comparator, pre-specified). Read from the pinned report; None for other bands."""
    groups = MYELOMA_GROUPS.get(band_id)
    if groups is None:
        return None
    raw = MYELOMA_REPORT_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MYELOMA_REPORT_SHA256:
        raise BodyMapError('The renal pathways v2 report is missing or changed; the map was not built.')
    report = json.loads(raw)
    cls = {study: report['primary'][study]['v1'][group]['classification'] for study, group in groups.items()}
    sens = {name: {study: s[study]['v1'][group]['classification'] for study, group in groups.items()}
            for name, s in report['sensitivity'].items()}
    if set(cls.values()) == {'consistent'}:
        finding = ('In two studies of myeloma patients never used to fit it, the model is consistent with the observed values '
                   'in this band in the main scenario (Bridoux 2016: exposure, AUC24; Kim 2026: clearance, CL/F).')
    else:
        finding = ('In two studies of myeloma patients never used to fit it, main scenario: Bridoux 2016 ' +
                   cls['bridoux'].replace('_', ' ') + ', Kim 2026 ' + cls['kim'].replace('_', ' ') + '.')
    sens_word = {('bridoux', 'model_over_predicts'): 'Bridoux: exposure too high', ('bridoux', 'model_under_predicts'): 'Bridoux: exposure too low',
                 ('kim', 'model_over_predicts'): 'Kim: clearance too high', ('kim', 'model_under_predicts'): 'Kim: clearance too low'}
    off = [sens_word[(study, c)] for s in sens.values() for study, c in s.items() if c != 'consistent']
    robustness = (f' In {sum(1 for s in sens.values() if set(s.values()) != {"consistent"})} of {len(sens)} sensitivity '
                  f'scenarios it is not ({"; ".join(sorted(set(off)))}).' if off else ' The sensitivity scenarios agree.')
    groups_note = (' Kim\'s groups are defined by eGFR; its moderate group (eGFR 30 to 60) is centred near 50 mL/min, the top '
                   'of this band.' if band_id == 'moderate' else '')
    d4 = load_f_report()['decision']['D4_myeloma_note'][band_id]
    word = {('bridoux', 'model_over_predicts'): 'Bridoux: exposure too high', ('bridoux', 'model_under_predicts'): 'Bridoux: exposure too low',
            ('kim', 'model_over_predicts'): 'Kim: clearance too high', ('kim', 'model_under_predicts'): 'Kim: clearance too low'}
    f_note = (' This assumes all of the dose is absorbed; it does not hold at ' + ', '.join(
        f"{float(F) * 100:.0f}% absorbed (" + '; '.join(word[(st, c)] for st, c in d4['by_F'][F].items() if c != 'consistent') + ')'
        for F in d4['not_at']) + '.') if d4['not_at'] else ''
    return {'text': ('That check is CC-5013-PK-001, the study the model was built from, in people without cancer. ' + finding +
                     robustness + f_note + groups_note + ' Both studies had been seen before this comparison, so it is not a blind test; '
                     'why the studies differ is not known.'),
            'classifications': cls, 'sensitivity': sens, 'report': 'docs/verification/lenalidomide_renal_pathways_check_v2.json',
            'report_file_sha256': MYELOMA_REPORT_SHA256}


def load_f_report():
    raw = F_REPORT_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != F_REPORT_SHA256:
        raise BodyMapError('The 2.0e bioavailability report is missing or changed; the map was not built.')
    return json.loads(raw)


_WORD = {'model_under_predicts': 'predicts too little exposure', 'model_over_predicts': 'predicts too much exposure',
         'consistent': 'is consistent'}


def bioavailability_text(band_id, f_report=None):
    """Plain text of the 2.0e result for a band (decision D1), or None if the band's status does not depend on F."""
    if band_id not in F_BANDS:
        return None
    d = (f_report or load_f_report())['decision']
    d1 = d['D1_band_status'][band_id]
    if d1['status'] != 'depends_on_bioavailability':
        return None
    short = {'model_under_predicts': 'too little exposure', 'model_over_predicts': 'too much exposure', 'consistent': 'consistent'}
    parts = [f"{float(F) * 100:.0f}%: {short[c]}" for F, c in d1['by_F'].items()]
    full = d1['by_F'][max(d1['by_F'], key=float)]
    tail = ('Lower absorption fits this group better but fits the myeloma studies and the end-stage prediction worse.'
            if full != 'consistent' else
            'Full absorption fits this group and the myeloma studies; lower absorption fits all of them worse.')
    return ('In CC-5013-PK-001, the study the model was calibrated on, the result in this band depends on how much of the dose is '
            'absorbed, which was not measured; the mass-balance study shows at least about 90%. Model with the dose absorbed at '
            + '; '.join(parts) + f" (lower bound 85%: {short[d1['at_lower_bound']]}). No single value fits every study. " + tail +
            ' (Simulation 2.0e.)')


def band_status(band, report=None):
    """Evidence status of a band: the locked 2.0a report (reading A), replaced for the moderate and severe bands by
    the 2.0e decision when the result depends on bioavailability."""
    if band['report_group'] is None:
        return 'calibrated'
    if band['id'] in F_BANDS and load_f_report()['decision']['D1_band_status'][band['id']]['status'] == 'depends_on_bioavailability':
        return 'depends_on_bioavailability'
    report = report or load_pathway_report()
    scenarios = report['decision']['classification_by_scenario']
    primary = scenarios['primary'][band['report_group']][READING]
    every = {s[band['report_group']][READING] for s in scenarios.values()}
    if primary == 'consistent':
        return 'checked_consistent' if every == {'consistent'} else 'consistent_primary_only'
    return 'check_disagrees'


def _split(cal, crcl):
    p = pathways(cal, crcl, READING)
    return {k: p[k] for k in ('filtration_ml_min', 'secretion_ml_min', 'renal_ml_min', 'non_renal_ml_min', 'total_ml_min', 'fe')}


def _blood_flow():
    f = renal_flows()
    return {'renal_blood_flow_ml_min': f['renal_blood_flow_ml_min'], 'per_kidney_blood_flow_ml_min': f['renal_blood_flow_ml_min'] / 2,
            'renal_plasma_flow_ml_min': f['renal_plasma_flow_ml_min'],
            'status': 'reference_physiology',
            'basis': (f"ICRP Publication 89 reference adult male: cardiac output {f['cardiac_output_l_min']:g} L/min, kidneys "
                      f"{f['kidney_fraction_pct']:g}% of it, red cells {f['red_cell_fraction_pct']:g}% of blood; split equally "
                      'between the two kidneys.'),
            'not_this': 'Reference physiology for a reference man, held at the same value at every creatinine clearance: not '
                        "this patient's blood flow and not adjusted for kidney function.",
            'source_sha256': ICRP_SHA256}


def _extraction(renal_plasma_clearance, status):
    """Share of the drug reaching the kidneys in arterial blood that leaves in urine in one pass."""
    bp = load_blood_plasma()['use_on_platform']['blood_to_plasma_ratio']
    blood_flow = renal_flows()['renal_blood_flow_ml_min']
    blood_clearance = renal_plasma_clearance / bp
    ratio = blood_clearance / blood_flow
    if not 0 <= ratio < 1:
        raise BodyMapError('Renal extraction outside 0-1: the clearance and the reference blood flow are inconsistent.')
    return {'ratio': ratio, 'returned_by_renal_veins': 1 - ratio, 'renal_blood_clearance_ml_min': blood_clearance,
            'blood_to_plasma_ratio': bp, 'blood_to_plasma_status': 'assumed', 'status': status,
            'formula': 'renal plasma clearance / blood-to-plasma ratio / reference renal blood flow',
            'basis': ('Blood-to-plasma ratio 0.931: whole-blood to plasma AUC of total radioactivity after [14C]-lenalidomide '
                      'in 6 healthy men (Chen 2012, Table 2); assumed to apply to lenalidomide and to exchange between red '
                      'cells and plasma within one pass.'),
            'source_sha256': CHEN_SHA256}


def build_map(crcl, mode, record=None):
    """The map for one creatinine clearance. `mode` is 'explorer' or 'record'; `record` adds the source revision."""
    if isinstance(crcl, bool) or not isinstance(crcl, (int, float)) or not math.isfinite(crcl):
        raise BodyMapError('Creatinine clearance must be a finite number.')
    crcl = float(crcl)
    fu_record = load_fu_record()
    view = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'drug': DRUG, 'mode': mode,
            'crcl_ml_min': crcl, 'range_ml_min': list(RANGE),
            'model': {'pathway_method_version': PATHWAY_METHOD, 'reading': READING, 'calibration_crcl_ml_min': CALIBRATION_CRCL,
                      'evidence_sha256': EVIDENCE_SHA256, 'report_file_sha256': PATHWAY_REPORT_SHA256,
                      'fu_record_version': fu_record['assessment_version'], 'fu_record_sha256': FU_RECORD_SHA256},
            'nodes': NODES, 'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    if record:
        view['record'] = record
    if not RANGE[0] <= crcl <= RANGE[1]:
        view.update(status='outside_range',
                    message=(f'Creatinine clearance {crcl:.0f} mL/min is outside {RANGE[0]:g}-{RANGE[1]:g} mL/min, the range the '
                             'map is drawn for; the map is not drawn.'))
        view['view_sha256'] = digest(view)
        return view
    evidence = load_evidence()
    fu_alt = next(v['fu'] for v in fu_record['values'] if v['id'] == 'ex_vivo_study_subjects')
    cal, cal_alt = calibrate(evidence, CALIBRATION_CRCL, FU), calibrate(evidence, CALIBRATION_CRCL, fu_alt)
    p, alt = _split(cal, crcl), _split(cal_alt, crcl)
    normal = _split(cal, CALIBRATION_CRCL)
    band = band_for(crcl)
    status = band_status(band)
    total = p['total_ml_min']
    renal_status = status
    d3 = load_f_report()['decision']['D3_non_renal']
    non_renal_status = 'depends_on_bioavailability' if d3['status'] == 'depends_on_bioavailability' else 'calibrated'
    non_renal_basis = ('total minus renal clearance in the normal group; held constant. Drawn at full absorption; with 90-100% '
                       f"absorbed it would be {d3['range_ml_min'][0]:.0f}-{d3['range_ml_min'][1]:.0f} mL/min (Simulation 2.0e)")
    flows = [
        {'from': 'gut', 'to': 'plasma', 'kind': 'absorption', 'value': None, 'unit': None,
         'note': 'Oral dose; bioavailability taken as 1 (urinary recovery implies at least about 0.85).'},
        {'from': 'plasma', 'to': 'glomerulus', 'kind': 'filtration', 'value': p['filtration_ml_min'], 'unit': 'mL/min',
         'alternative_value': alt['filtration_ml_min'], 'share_of_elimination': p['filtration_ml_min'] / total,
         'alternative_share': alt['filtration_ml_min'] / total, 'status': renal_status,
         'basis': f'unbound fraction x creatinine clearance; fu {FU} (in vitro) and, as alternative, {fu_alt} (ex vivo)'},
        {'from': 'plasma', 'to': 'tubule', 'kind': 'tubular_secretion', 'value': p['secretion_ml_min'], 'unit': 'mL/min',
         'alternative_value': alt['secretion_ml_min'], 'share_of_elimination': p['secretion_ml_min'] / total,
         'alternative_share': alt['secretion_ml_min'] / total, 'status': renal_status,
         'basis': 'renal clearance minus filtration in the normal group, scaled with creatinine clearance (intact-nephron reading)'},
        {'from': 'kidney', 'to': 'urine', 'kind': 'renal_excretion', 'value': p['renal_ml_min'], 'unit': 'mL/min',
         'share_of_elimination': p['renal_ml_min'] / total, 'status': renal_status,
         'basis': 'filtration + secretion; the same under both unbound fractions'},
        {'from': 'plasma', 'to': 'non_renal', 'kind': 'non_renal', 'value': p['non_renal_ml_min'], 'unit': 'mL/min',
         'share_of_elimination': p['non_renal_ml_min'] / total, 'status': non_renal_status,
         'basis': non_renal_basis},
    ]
    view.update(
        status='completed',
        band={'id': band['id'], 'range_ml_min': band['range'], 'status': status,
              'status_text': bioavailability_text(band['id']) if status == 'depends_on_bioavailability' else STATUS_TEXT[status],
              'myeloma_note': myeloma_note(band['id']),
              'f_report_file_sha256': F_REPORT_SHA256},
        flows=flows,
        totals={'total_ml_min': total, 'renal_ml_min': p['renal_ml_min'], 'fraction_excreted_unchanged': p['fe'],
                'relative_exposure_same_dose': normal['total_ml_min'] / total},
        normal_reference={'crcl_ml_min': CALIBRATION_CRCL, 'total_ml_min': normal['total_ml_min'], 'fraction_excreted_unchanged': normal['fe']},
        blood_flow=_blood_flow(),
        extraction=_extraction(p['renal_ml_min'], status),
        drawing_scale={'max_flow_ml_min': normal['total_ml_min'],
                       'rule': 'Arrow width is proportional to clearance on one fixed scale (the normal total), so maps can be compared.'},
        limitations=[
            'Typical values from group means of 5-7 subjects per kidney-function group; real patients vary widely.',
            'Arrows are clearance flows, not amounts or concentrations in organs.',
            'Creatinine clearance stands in for GFR and overestimates it.',
            'The filtration/secretion split depends on the unbound fraction, which the data do not pin down; both values are shown. '
            'Total renal clearance and exposure are the same under both.',
            'Non-renal clearance is held constant and drawn at full absorption (bioavailability 1). Absorption was at least about '
            '90% in the mass-balance study; at 90% non-renal clearance would be about 10 rather than 29 mL/min, and at the '
            'lower bound of 85% about zero. The moderate and severe band results depend on this (Simulation 2.0e).',
            'The map is drawn from 10 to 140 mL/min; the study\'s groups were centred at about 24 (severe) to 102 (normal) mL/min, '
            'so the ends of the range extrapolate.',
            'Not a measurement of kidney function, an exposure prediction for a patient, or a dose recommendation.'])
    view['view_sha256'] = digest(view)
    return view


def explorer_map(crcl):
    return build_map(crcl, 'explorer')


def record_map(revision_id, weight_basis=None):
    """The map for a saved synthetic record, from the same estimate the 2.0b patient page uses."""
    from .patient_renal_pathways import patient_renal_pathways
    pv = patient_renal_pathways(revision_id, weight_basis)
    record = {'revision_id': pv['revision_id'], 'pathways_view_sha256': pv['report_sha256'],
              'covariate_estimate_status': pv['covariate_estimate']['status']}
    if pv['status'] != 'completed':
        view = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'drug': DRUG, 'mode': 'record',
                'record': record, 'status': pv['status'], 'message': pv.get('message'), 'nodes': NODES,
                'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
        view['view_sha256'] = digest(view)
        return view
    return build_map(pv['crcl_ml_min'], 'record', record)
