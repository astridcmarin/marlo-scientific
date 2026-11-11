"""Model analysis reports in the section order of ICH M15 Appendix 2 (reviewer's checklist M3, 5 November 2026).

A report is assembled, not written by hand, except for four narrative sections kept in a pinned text file per model
(executive summary, introduction, objectives, discussion and conclusions). Everything else is read from pinned sources:
- Data and methods: the credibility record (question of interest, context of use, assumptions), the locked plans with
  their checksums, and the dataset ledger's role for every dataset the model has used;
- Results: one table per locked check, read from the check's report file, and the check's line on the findings page
  with its blindness;
- Appendices: the plans (the Model Analysis Plans, as M15 asks), the reports and the reviews.
Nothing is computed scientifically. First model: the lenalidomide kidney pathway model.
"""
import hashlib
import json
from pathlib import Path

from .patient_state import digest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / 'data'
SCHEMA_VERSION = 'model-analysis-report-v1'
TEXTS = {
    'lenalidomide_renal_pathways_2026': ('model_analysis_report_text_lenalidomide_renal_pathways_v1.json',
                                         '65c9c7f918cfe1a8666620875e6bdeb2761e9374f0cbb7c1e33fa9d67b85a324'),
    'lenalidomide_hughes_2019': ('model_analysis_report_text_lenalidomide_hughes_2019_v2.json',
                                 '1ca9bd802c28f3a3e9e3687222c90bba12d923a3f9992516e98d99a9ab7faba0'),
    'lenalidomide_exposure_safety_2016': ('model_analysis_report_text_lenalidomide_exposure_safety_2016_v2.json',
                                          'faa587574a7fcd6309d7d8915453d41be0a41fa036daf699b9f12d33f9ce2a59'),
    'lenalidomide_kim_2026': ('model_analysis_report_text_lenalidomide_kim_2026_v2.json',
                              'b101d24ce78ea8fa1a52bf9a492ac884474d4d513c327f06cd2b3c24d816402d'),
}
# Superseded narrative texts, kept unchanged and pinned for traceability (file name -> SHA-256).
SUPERSEDED_TEXTS = {
    'model_analysis_report_text_lenalidomide_exposure_safety_2016_v1.json': '42b9544f80580534f267b48f4fc6893bbf1c146c42ed09a589b2e8d5187040f9',
    'model_analysis_report_text_lenalidomide_kim_2026_v1.json': '691ddbddf03d4e47b83a036202fcc8c7491a18d88ec1e9e0d4c66d1fa5d62f69',
    'model_analysis_report_text_lenalidomide_hughes_2019_v1.json': '30bc917397eb3e949067af584a1ce5394a8d16de656c8a9da848be159822e53a',
}
REPORT_FILES = {
    'pathways_2_0a': ('docs/verification/lenalidomide_renal_pathways_check_v1.json', '163b5ca1a95a7f3d745c8e25a93ef58d4bedd0e1e48d6e4bfdfb4a25457a93d5'),
    'pathways_esrd': ('docs/verification/lenalidomide_esrd_dialysis_check_v1.json', 'f82caa14d665e4f3d4aeefffef6030da7f3cbd5ced495e0e342bcc86108eed52'),
    'pathways_2_0d': ('docs/verification/lenalidomide_renal_pathways_check_v2.json', '277108de99726588a04c11468e7004f93068d6fa0ca3372ae5c564dbe756dbdd'),
    'pathways_2_0e': ('docs/verification/lenalidomide_renal_pathways_check_v3.json', 'a60437cc58e174c88b79434a6eee104455995bf64cd0f935f8c39f4877615533'),
    'hughes_cc5013': ('docs/verification/hughes_renal_group_check_v1.json', '70cae05e8dca498bc3e9774177dd4fc406c9508f419ad1f8a64be80c84c0c159'),
    'kim_cc5013': ('docs/verification/kim_renal_group_check_v1.json', 'e53f62db6506346a3d5027388b0c9165de51b8fab0c5f9efc1ad7b29d34da4bb'),
    'renal_recheck': ('docs/verification/lenalidomide_renal_recheck_v1.json', 'c98e29919cd9e90981439a37d03883a8cfd834f397b8c0383e723b1f923e2991'),
    'bridoux_hughes_kim': ('docs/verification/lenalidomide_bridoux_check_v1.json', 'febf0e3b6ea090dd44172bc44b4cedf30e820b2227a07cea4ea7eed4fa3daccb'),
}
REVIEWS = {'lenalidomide_renal_pathways_2026': ['docs/reviews/2026-11-04_ai_review_renal_pathways.md']}
CLASS = {'consistent': 'consistent', 'model_under_predicts': 'model under-predicts', 'model_over_predicts': 'model over-predicts'}
GROUP = {'mild': 'Mild', 'moderate': 'Moderate', 'severe_without_dialysis': 'Severe, not on dialysis'}


class ReportError(ValueError):
    pass


def _pinned(rel, sha):
    raw = (ROOT / rel).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ReportError(f'{rel} is missing or changed; the report was not built.')
    return json.loads(raw)


def _c(x):
    return CLASS.get(x, x.replace('_', ' ') if isinstance(x, str) else x)


def _result_2_0a(r, model_id=None):
    primary = next(s for s in r['scenarios'] if s['label'] == 'primary')
    rows = []
    for g in primary['groups']:
        a, b = g['readings']['A_intact_nephron'], g['readings']['B_secretion_preserved']
        rows.append([GROUP[g['group']], g['n'], f"{g['observed_auc_mean']:,.0f} ({g['interval_95'][0]:,.0f}–{g['interval_95'][1]:,.0f})",
                     f"{a['auc_ng_h_ml']:,.0f}: {_c(a['classification'])}", f"{b['auc_ng_h_ml']:,.0f}: {_c(b['classification'])}",
                     f"{a['fe']:.2f} vs {a['fe_observed']:.2f}"])
    cal = primary['calibration']
    return {'title': 'CC-5013-PK-001 impaired groups, primary scenario (2.0a)',
            'columns': ['Group', 'n', 'Observed AUC, mean (95% CI)', 'Reading A, intact nephron', 'Reading B, secretion preserved',
                        'Fraction unchanged in urine, A vs observed'],
            'rows': rows,
            'note': (f"Calibration at {cal['crcl_ml_min']} mL/min, fu {cal['fu']}: filtration {cal['filtration_ml_min']:.1f}, secretion "
                     f"{cal['secretion_ml_min']:.1f}, non-renal {cal['non_renal_ml_min']:.1f} mL/min (bioavailability 1). AUC in h·ng/mL. "
                     f"Other scenarios are in the report.")}


def _result_esrd(r, model_id=None):
    p = r['primary']
    rows = [[f"{s['residual_crcl_ml_min']:g}", f"{s['auc_ng_h_ml']:,.0f}", f"{s['ratio_to_observed']:.2f}", _c(s['classification'])]
            for s in p['scenarios']]
    return {'title': 'End-stage kidney disease, non-dialysis day (2.0c)',
            'columns': ['Residual creatinine clearance (mL/min)', 'Predicted AUC', 'Ratio to observed', 'Classification'],
            'rows': rows,
            'note': f"Observed AUC {p['observed_auc_mean']:,.0f} (95% CI {p['interval_95'][0]:,.0f}–{p['interval_95'][1]:,.0f}), n = {p['n']}. "
                    'Residual function of the subjects was not reported, so the result is inconclusive.'}


def _result_2_0d(r, model_id=None):
    d = r['decision']
    rows = [[k.replace('_', ' ').capitalize(), _c(v)] for k, v in d['deciding_comparisons'].items()]
    return {'title': 'Steeper-secretion candidate against the myeloma studies (2.0d)',
            'columns': ['Deciding comparison', 'Candidate v2'], 'rows': rows,
            'note': f"Fitted k = {d['k']:.2f} (not at a bound). {d['deciding_consistent']} of 4 deciding comparisons consistent; "
                    f"outcome: {d['outcome'].replace('_', ' ')}. Rule: {d['rule']}"}


def _result_2_0e(r, model_id=None):
    d = r['decision']
    rows = []
    for band in ('moderate', 'severe'):
        b, m = d['D1_band_status'][band], d['D4_myeloma_note'][band]
        for f, cls in b['by_F'].items():
            my = m['by_F'][f]
            rows.append([band.capitalize(), f, _c(cls), _c(my['bridoux']), _c(my['kim'])])
        rows.append([band.capitalize(), 'lower bound 0.85', _c(b['at_lower_bound']), '—', '—'])
    lo, hi = d['D3_non_renal']['range_ml_min']
    return {'title': 'Across the bioavailability the data allow (2.0e)',
            'columns': ['Band', 'Bioavailability F', 'CC-5013-PK-001', 'Bridoux 2016', 'Kim 2026'], 'rows': rows,
            'note': (f"Band status: moderate {d['D1_band_status']['moderate']['status'].replace('_', ' ')}, severe "
                     f"{d['D1_band_status']['severe']['status'].replace('_', ' ')}. Renal elimination falling faster than in proportion "
                     f"to creatinine clearance: {d['D2_faster_than_proportional'].replace('_', ' ')}. Non-renal clearance "
                     f"{lo:.1f}–{hi:.1f} mL/min over F 0.90–1.0.")}


BANDS = {'mild': 'Mild', 'moderate': 'Moderate', 'severe': 'Severe'}
GROUP_TITLES = {
    'hughes_cc5013': ('CC-5013-PK-001 kidney-function groups (2.0g)', 'Single 25 mg dose; observed group mean AUCinf against simulated group means (primary endpoint).'),
    'kim_cc5013': ('CC-5013-PK-001 kidney-function groups (2.1c)', 'Single 25 mg dose; observed group mean AUCinf against simulated group means (primary endpoint).'),
    'renal_recheck': ('Recheck with virtual subjects matched to CC-5013-PK-001 (2.1e)', 'Each group simulated with the study\'s own demographics; AUCinf as before.'),
    'bridoux_hughes_kim': ('Myeloma patients on reduced doses, Bridoux 2016 (2.1h)', 'Steady-state AUC24 by kidney-function group, in myeloma patients on the doses they received; the first blind check of a published population model.'),
}


def _result_groups(r, model_id):
    """Group classifications for a published population model, from either report layout."""
    if 'result_by_model' in r:
        block = r['result_by_model'][model_id]
        primary, across = block['primary'], block['across_scenarios']
    else:
        primary, across = r['primary_endpoint_by_group'], r['classification_across_scenarios']
    columns = ['Kidney-function group', 'Primary scenario', 'Across all scenarios']
    rows = []
    for g in ('mild', 'moderate', 'severe'):
        row = [BANDS[g], _c(primary[g]), ', '.join(sorted({_c(x) for x in across[g]}))]
        if 'result_by_model' in r and 'change_from_v1' in r['result_by_model'][model_id]:
            row.append(r['result_by_model'][model_id]['change_from_v1'][g])
        rows.append(row)
    if rows and len(rows[0]) == 4:
        columns.append('Change from the first check')
    return columns, rows


def _group_result(finding_id):
    def build_result(r, model_id):
        columns, rows = _result_groups(r, model_id)
        title, note = GROUP_TITLES[finding_id]
        if r.get('deviation_recorded_at_stage_1'):
            note += ' Recorded deviation: ' + r['deviation_recorded_at_stage_1']
        return {'title': title, 'columns': columns, 'rows': rows,
                'note': note + ' Classification (locked plan): consistent when the observed value lies within the 5th-95th '
                               'percentile of simulated values; otherwise the direction of the difference.'}
    return build_result


RESULTS = {'pathways_2_0a': _result_2_0a, 'pathways_esrd': _result_esrd, 'pathways_2_0d': _result_2_0d, 'pathways_2_0e': _result_2_0e,
           'hughes_cc5013': _group_result('hughes_cc5013'), 'kim_cc5013': _group_result('kim_cc5013'),
           'renal_recheck': _group_result('renal_recheck'), 'bridoux_hughes_kim': _group_result('bridoux_hughes_kim')}


def _exposure_safety_results():
    """For a model with no locked check: the published estimates as implemented, what the implemented formula gives at
    example exposure ratios (computed by the platform's own module), and what has not been checked."""
    from .lenalidomide_relative_odds import ENDPOINTS, EVIDENCE_PATH, EVIDENCE_SHA256, load_evidence, relative_odds
    ev = load_evidence()
    ors = ev['odds_ratios_multiple_myeloma']
    names = {'grade_3_4_thrombocytopenia': 'Grade 3/4 thrombocytopenia', 'grade_3_4_neutropenia': 'Grade 3/4 neutropenia'}
    estimates = [[names[e], f"{ors[e]['odds_ratio_per_unit_ln_auc']:.3f} ({ors[e]['ci95'][0]:.3f}–{ors[e]['ci95'][1]:.3f})",
                  ors[e]['adjusted_for'], 'yes' if ors[e]['statistically_significant'] else 'no'] for e in ENDPOINTS]
    chen = ev['second_source']['quotes']['thrombocytopenia']
    ratios = (0.5, 1.5, 2.0, 3.0)
    illustration = []
    for e in ENDPOINTS:
        row = [names[e]]
        for r in ratios:
            ro = relative_odds(r, ors[e]['odds_ratio_per_unit_ln_auc'], ors[e]['ci95'])
            row.append(f"{ro['relative_odds']:.2f} ({ro['ci95'][0]:.2f}–{ro['ci95'][1]:.2f})")
        illustration.append(row)
    rel = str(EVIDENCE_PATH.relative_to(ROOT))
    blank = {'id': None, 'step': None, 'date': None, 'question': None, 'outcome': None, 'outcome_label': None, 'headline': None,
             'blind': False, 'blindness_label': 'No locked check'}
    return [
        {'title': 'Published estimates as implemented (multiple myeloma)', 'columns': ['Endpoint', 'Odds ratio per unit ln AUC (95% CI)', 'Adjusted for', 'Significant'],
         'rows': estimates,
         'note': 'TGA AusPAR, February 2016, section 4.2.4.1 (sponsor analysis CC-5013-MCL-001-PK). The same analysis, pooled across '
                 'diseases and adjusted for disease, gives the thrombocytopenia odds ratio as reported by Chen 2017: "' + chen + '". '
                 'Not reported by the source: ' + '; '.join(ev['not_reported']) + '.',
         'finding': dict(blank, question='What the platform takes from the source.'), 'report_file': rel, 'report_sha256': EVIDENCE_SHA256},
        {'title': 'What the implemented formula gives (illustration)', 'columns': ['Endpoint'] + [f'Exposure {r:g}× reference' for r in ratios],
         'rows': illustration,
         'note': 'Relative odds = (AUC / AUC_reference) ** ln(OR), with the 95% CI carried through the same formula; computed by '
                 'lenalidomide_relative_odds.relative_odds, the function the pages use. Relative odds only: no probability for a '
                 'patient, because the intercept and baseline-count coefficients were not published. The odds ratios describe all '
                 'cycles up to one year, not cycle 1.',
         'finding': dict(blank, question='How the published odds ratios translate to relative odds at example exposures.'),
         'report_file': rel, 'report_sha256': EVIDENCE_SHA256},
    ]


EXTRA_RESULTS = {'lenalidomide_exposure_safety_2016': _exposure_safety_results}


def available():
    return list(TEXTS)


def build(model_id):
    if model_id not in TEXTS:
        raise KeyError(model_id)
    from .check_findings import findings_view
    from .credibility_records import record as credibility_record
    from .dataset_ledger import load_ledger, model_uses
    text = _pinned('intelligence_store/data/' + TEXTS[model_id][0], TEXTS[model_id][1])
    cred = credibility_record(model_id)
    findings = [f for area in findings_view()['areas'] for f in area['rows'] if model_id in f['subjects']]
    results = []
    for f in findings:
        rel, sha = REPORT_FILES[f['id']]
        if f['report'] != rel:
            raise ReportError(f"Finding {f['id']} cites {f['report']}, not {rel}.")
        report = _pinned(rel, sha)
        results.append(dict(RESULTS[f['id']](report, model_id), finding={k: f.get(k) for k in ('id', 'step', 'date', 'question', 'outcome',
                                                                                         'outcome_label', 'headline', 'blind', 'blindness_label')},
                            report_file=rel, report_sha256=sha))
    if model_id in EXTRA_RESULTS:
        results.extend(EXTRA_RESULTS[model_id]())
    ledger = load_ledger()
    names = {k: d.get('label') or d.get('name') or d.get('title') or k for k, d in ledger['datasets'].items()}
    datasets = {}
    for use in model_uses(model_id, ledger):
        datasets.setdefault(use['dataset'], set()).add(use['role'])
    report = {
        'schema_version': SCHEMA_VERSION, 'model_id': model_id, 'name': cred['name'], 'structure': text['structure'],
        'author': text['author'], 'text_version': text['text_version'], 'text_sha256': TEXTS[model_id][1],
        'executive_summary': text['sections']['executive_summary'],
        'findings_summary': [{'step': f['step'], 'outcome': f.get('outcome_label') or f['outcome'], 'headline': f['headline']} for f in findings],
        'introduction': text['sections']['introduction'],
        'objectives': text['sections']['objectives'],
        'data_and_methods': {
            'question_of_interest': cred['assessment']['question_of_interest'],
            'context_of_use': cred['assessment']['context_of_use'],
            'model_risk': cred['assessment']['model_risk'],
            'datasets': [{'id': k, 'name': names.get(k, k), 'roles': sorted(v)} for k, v in datasets.items()],
            'assumptions': cred['assumptions'],
            'verification_and_validation': [{'label': v['label'], 'status': v['status_label']} for v in cred['evaluation']['verification_and_validation']],
        },
        'results': results,
        'discussion': text['sections']['discussion'],
        'conclusions': text['sections']['conclusions'],
        'appendices': {'model_analysis_plans': cred['model_analysis_plans'],
                       'reports': [{'file': r['report_file'], 'sha256': r['report_sha256']} for r in results if r['finding']['id']],
                       'reviews': REVIEWS.get(model_id, []),
                       'credibility_record_sha256': cred['record_sha256']},
        'not_this': text['not_this'],
        'clinical_prediction_validated': False,
    }
    report['report_sha256'] = digest(report)
    return report
