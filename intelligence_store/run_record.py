"""Patient Lab 2.0f: one run record for every Patient Lab result.

Each result page (Hughes educational PK, a saved Kim 2026 run, the bortezomib platelet curve for a patient)
already carries its own report. This module reads those reports and lays the same facts out the same way:
what kind of result it is and is not, which model and source, which patient record and inputs, the
assumptions with their status, how far the patient lies inside the source data, what has been checked about
the model, and the checksums that tie the page to its sources. It adds no new numbers; every value is copied
from the report or from a pinned file.
"""
from pathlib import Path

from .covariate_estimation import _load_pinned
from .patient_state import digest

SCHEMA_VERSION = 'patient-lab-run-record-v1'
EVIDENCE_PATH = Path(__file__).parent / 'data' / 'model_evidence_status_v14.json'
EVIDENCE_SHA256 = '4fdac3a8bb50ead46b0f85633ac1be93ffd0dab393b8009faa502c126ce5d1fb'
# Superseded, kept unchanged for traceability: model_evidence_status_v13.json
EVIDENCE_V13_SHA256 = '943876d68dfe5cbb2ba3636bd106711423fda88f0399a98f87ab41f90d11d524'
# Superseded, kept unchanged for traceability: model_evidence_status_v12.json
EVIDENCE_V12_SHA256 = '94f9b9c857fe33e0a660a2d16135ad6a1d3e98018048480eb6869814675a50be'
# Superseded, kept unchanged for traceability: model_evidence_status_v11.json
EVIDENCE_V11_SHA256 = 'c4eb8b9fba62353e81d7825369d70adeb832d53927ab6dc6944e8401b7a97326'
# Superseded, kept unchanged for traceability: model_evidence_status_v10.json
EVIDENCE_V10_SHA256 = '411d2ac7d76ea4c8fa57f8b7b7b6cff22f3d5c9b65b29c2ec08e0c972ef483f2'
# Superseded, kept unchanged for traceability: model_evidence_status_v9.json
EVIDENCE_V9_SHA256 = '18fc8e280adc74885b18862962c1d98f7fcc30de28b390595d7a379e62aad426'
# Superseded, kept unchanged for traceability: model_evidence_status_v8.json
EVIDENCE_V8_SHA256 = 'd9839f8cf7b98af5e8d37ade805e88d5cc51367a8d04a76535bbfb8d8803ec2e'
# Superseded, kept unchanged for traceability: model_evidence_status_v7.json
EVIDENCE_V7_SHA256 = '4f63e2250e77fd870e515f83b19f7bd7508190e2a97f8e61ec1f604a81ab995c'
# Superseded, kept unchanged for traceability: model_evidence_status_v6.json
EVIDENCE_V6_SHA256 = 'e909d012664396088ad05bf48d9a893a1ade6ae65fc5a9d7e18effd10d13cd10'
# Superseded, kept unchanged for traceability: model_evidence_status_v5.json
EVIDENCE_V5_SHA256 = '41837fefc5252ec16932f58ccb462448a3d6a532e1a5ec2fa46ba2fbb7a2257c'
# Superseded, kept unchanged for traceability: model_evidence_status_v4.json
EVIDENCE_V4_SHA256 = 'e559a4e4f8028ff8bd4c3caa213648c84224dbe0a1e83c60d1cc84a5260a7804'
# Superseded, kept unchanged for traceability: model_evidence_status_v3.json
EVIDENCE_V3_SHA256 = '09d83e0e614246cd4b5eae5b49c1a86329181d449116741bcf4b53198c9ebf92'
# Superseded, kept unchanged for traceability: model_evidence_status_v2.json
EVIDENCE_V2_SHA256 = '550da678fe3388da2e05f56cb87416ee8217c839274809a4f7add170a6703c4e'
# Superseded, kept unchanged for traceability: model_evidence_status_v1.json
EVIDENCE_V1_SHA256 = 'c3a15f216df830e7953ab0bbf1cf9d9046831df99e78bed8ba291fd04aefd121'

RESULT_TYPES = {
    'typical_value_pk': {
        'label': 'Typical-value concentration curve',
        'is': 'What the published model expects for a patient with these covariates, with every random effect at zero.',
        'is_not': ['a prediction of this patient\'s concentrations',
                   'evidence of efficacy, toxicity or a suitable dose',
                   'a substitute for measured drug levels'],
    },
    'hypothetical_typical_pd_curve': {
        'label': 'Hypothetical typical effect curve',
        'is': 'The typical course a published model gives for the studied regimen, scaled to this record\'s starting value.',
        'is_not': ['a prediction of this patient\'s values or grade',
                   'a recommendation to give, hold or change a dose',
                   'an individual risk estimate (the observed incidences shown are the better guide)'],
    },
}
RESULT_TYPES['elimination_pathway_split'] = {
    'label': 'Typical split of elimination between pathways',
    'is': 'How a semi-physiological model divides lenalidomide clearance between filtration, tubular secretion and non-renal routes at this record\'s estimated kidney function.',
    'is_not': ['a measurement of this patient\'s renal clearance or urine excretion',
               'an exposure prediction for this patient',
               'a dose recommendation'],
}
RESULT_TYPES['elimination_pathway_split_explorer'] = {
    'label': 'Typical split of elimination between pathways at an entered kidney function',
    'is': 'How a semi-physiological model divides lenalidomide clearance between filtration, tubular secretion and non-renal routes at the creatinine clearance chosen on the page, with no patient record.',
    'is_not': ['a measurement of anyone\'s renal clearance or urine excretion',
               'an exposure prediction for a patient',
               'a dose recommendation'],
    'patient_record': False,
}
RESULT_TYPES['relative_odds_vs_reference'] = {
    'label': 'Relative odds versus a reference exposure',
    'is': ('How the odds of a grade 3/4 low blood count for a patient at this typical exposure compare with a patient at '
           'the reference exposure with the same disease and baseline count, from a published exposure-safety odds ratio.'),
    'is_not': ['a probability or individual risk of a low blood count',
               'a prediction of this patient\'s blood counts',
               'a monitoring or dose recommendation'],
}
LAYER_ORDER = ('software_verification', 'transcription_verification', 'reproduction', 'external_consistency')


def load_evidence_status(path=EVIDENCE_PATH):
    return _load_pinned(path, EVIDENCE_SHA256, 'model-evidence-status-v1', 'Model evidence status')


def _evidence(model_id, evidence):
    entry = evidence['models'][model_id]
    layers = [dict(entry['layers'][name], layer=name, description=evidence['layers'][name]) for name in LAYER_ORDER]
    return {'model_id': model_id, 'name': entry['name'], 'citation': entry['citation'], 'doi': entry['doi'],
            'layers': layers, 'never_established': evidence['never_established']}


def _state_inputs(estimate):
    """Patient-record fields the estimator read, in the order first used, with their origin."""
    seen, rows = set(), []
    for step in estimate.get('derivations') or []:
        for item in step['inputs'].values():
            source = item.get('from', '')
            if source.startswith('patient_state.') and source not in seen:
                seen.add(source)
                rows.append({'name': source.split('.', 1)[1], 'value': item['value'], 'unit': item.get('unit'),
                             'origin': item.get('origin')})
    return rows


def _derived(estimate):
    return [{'name': step['quantity'], 'value': step['value'], 'unit': step['unit'],
             'method': f"{step['formula_id']} ({step['formula_version']})"} for step in estimate.get('derivations') or []]


def _coverage(estimate, source_label):
    return [{'item': c['field'], 'value': c['value'], 'unit': c['unit'],
             'reference': f"{source_label} range {c['source_range'][0]:.3g}–{c['source_range'][1]:.3g}",
             'status': c['status']} for c in estimate.get('coverage_checks') or []]


def _finish(record):
    record['validation'] = {'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
    record['record_sha256'] = digest(record)
    return record


def _base(kind, result_type, title, revision_id, state_schema_version, state_sha256, model_id, evidence):
    return {'schema_version': SCHEMA_VERSION, 'evidence_status_version': evidence['status_version'],
            'evidence_status_sha256': EVIDENCE_SHA256, 'kind': kind, 'title': title,
            'result_type': dict(RESULT_TYPES[result_type], id=result_type),
            'patient_record': {'revision_id': revision_id, 'state_schema_version': state_schema_version,
                               'state_sha256': state_sha256, 'data': 'synthetic'},
            'model': _evidence(model_id, evidence)}


def record_for_estimated_pk(report, evidence=None):
    """Run record for a Hughes 2019 calculation from `estimated_pk.calculate_estimated_pk`."""
    evidence = evidence or load_evidence_status()
    estimate = report['covariate_estimate']
    calculation = report.get('calculation') or {}
    record = _base('hughes_estimated_pk', 'typical_value_pk', 'Lenalidomide educational PK (Hughes 2019)',
                   report['revision_id'], estimate['state_schema_version'], estimate['state_sha256'],
                   'lenalidomide_hughes_2019', evidence)
    wb = estimate['weight_basis_evidence']
    record.update(
        status=calculation.get('status') or report.get('status'),
        inputs_from_record=_state_inputs(estimate), derived_inputs=_derived(estimate),
        assumptions=[{'name': 'Cockcroft–Gault weight basis', 'reading': estimate['weight_basis'].replace('_', ' '),
                      'status': wb['assessment_status'], 'evidence': wb['summary']},
                     {'name': 'Random effects', 'reading': 'all set to zero (typical value)', 'status': 'by_design',
                      'evidence': 'Between-patient variability is shown separately by the population band.'}],
        applicability=_coverage(estimate, 'Hughes 2019'),
        warnings=list(estimate.get('warnings') or []) + [f"{b['code']}: {b['message']}" for b in calculation.get('execution_blockers') or []],
        limitations=list(calculation.get('limitations') or []),
        checksums=[{'label': 'Report', 'sha256': report['report_sha256']},
                   {'label': 'Covariate estimate', 'sha256': report['covariate_estimate_sha256']}]
                  + ([{'label': 'Calculation', 'sha256': report['calculation_sha256']}] if report.get('calculation_sha256') else [])
                  + [
                   {'label': 'Patient state', 'sha256': estimate['state_sha256']},
                   {'label': 'Formula registry', 'sha256': estimate['registry_sha256']},
                     {'label': 'Weight-basis assessment', 'sha256': estimate['assessment_sha256']}])
    return _finish(record)


def record_for_kim_run(run, evidence=None):
    """Run record for a saved Kim 2026 run, as returned by `kim_pk_runs.read_kim_pk_run` (checksums already verified)."""
    evidence = evidence or load_evidence_status()
    payload = run.payload
    report = payload['report']
    estimate = report['covariate_estimate']
    record = _base('saved_kim_run', 'typical_value_pk', f"Saved Kim 2026 run #{run.id}", report['revision_id'],
                   estimate['state_schema_version'], estimate['state_sha256'], 'lenalidomide_kim_2026', evidence)
    form = report['cl_form_evidence']
    record.update(
        status=report['status'], saved_at_utc=payload['saved_at_utc'],
        inputs_from_record=_state_inputs(estimate), derived_inputs=_derived(estimate),
        assumptions=[{'name': 'CL/F equation reading', 'reading': report['cl_form'].replace('_', ' '),
                      'status': form['assessment_status'], 'evidence': form['summary']},
                     {'name': 'Random effects', 'reading': 'all set to zero (typical value)', 'status': 'by_design',
                      'evidence': 'No between-patient variability is shown for this model.'}],
        applicability=_coverage(estimate, 'Kim 2026'),
        warnings=list(estimate.get('warnings') or []),
        limitations=list(report.get('limitations') or []),
        checksums=[{'label': 'Saved payload', 'sha256': run.payload_sha256},
                   {'label': 'Report', 'sha256': run.report_sha256},
                   {'label': 'Covariate estimate', 'sha256': report['covariate_estimate_sha256']},
                   {'label': 'Patient state', 'sha256': estimate['state_sha256']},
                   {'label': 'Model extract', 'sha256': estimate['extract_sha256']},
                   {'label': 'Formula registry', 'sha256': estimate['registry_sha256']}])
    return _finish(record)


def record_for_patient_platelets(view, extract, evidence=None):
    """Run record for `bortezomib_patient_platelets.patient_platelet_view` (completed views only)."""
    evidence = evidence or load_evidence_status()
    record = _base('patient_bortezomib_platelets', 'hypothetical_typical_pd_curve',
                   'Bortezomib platelet curve for this record (Lignet 2022)', view['revision_id'],
                   view['state_schema_version'], view['state_sha256'], 'bortezomib_platelets_lignet_2022', evidence)
    reading = view['model_reading']
    prov = view['baseline_provenance']
    assumptions = [{'name': 'Drug-effect term', 'reading': f"C in {reading['units'].replace('_per_', '/').replace('ng/ml', 'ng/mL')}, "
                                                           f"{reading['effect_bound'].replace('_', ' ')}",
                    'status': 'settled_by_locked_check',
                    'evidence': 'The only reading consistent with the fitting data for both variants (docs/verification/bortezomib_platelet_check_v1.json).'}]
    for q in extract['open_questions']:
        if q['id'] in ('concentration_unit', 'negative_effect_term'):
            continue
        reading_text = q['candidate_readings'][0].replace('_', ' ')
        for raw, shown in (('ktr', 'Ktr'), ('circ0', 'Circ0'), ('iv bolus', 'IV bolus')):
            reading_text = reading_text.replace(raw, shown)
        entry = {'name': q['question'], 'reading': reading_text, 'status': 'assumed', 'evidence': q['resolution']}
        if q['id'] == 'time_dependent_clearance':
            # The PK component's external check tested exactly this assumption.
            pk = evidence['models']['bortezomib_pk_lignet_2022']['layers']['external_consistency']
            entry.update(status='contradicted_by_external_data',
                         evidence=f"{q['resolution']} External check: {pk['summary']} ({pk['evidence_report']}).")
        assumptions.append(entry)
    assumptions.append({'name': 'Regimen', 'reading': '1.3 mg/m² on days 1, 4, 8, 11 of 21-day cycles, no holds or reductions',
                        'status': 'fixed', 'evidence': 'The only regimen the model was fitted to.'})
    record.update(
        status=view['status'],
        inputs_from_record=[{'name': 'platelet_count', 'value': view['baseline_1e9_per_l'], 'unit': '10^9/L',
                             'origin': prov['origin']}],
        derived_inputs=[],
        assumptions=assumptions,
        applicability=[{'item': 'platelet_count', 'value': view['baseline_1e9_per_l'], 'unit': '10^9/L',
                        'reference': 'source entry threshold 50 (30 with extensive marrow involvement)',
                        'status': 'below_entry_threshold' if view['eligibility_warnings'] else 'at_or_above_entry_threshold'}],
        warnings=list(view['eligibility_warnings']),
        limitations=list(view['limitations']),
        checksums=[{'label': 'View', 'sha256': view['report_sha256']},
                   {'label': 'Model curve report', 'sha256': view['model_report_sha256']},
                   {'label': 'Reading check report (file)', 'sha256': reading['check_report_file_sha256']},
                   {'label': 'Observed context', 'sha256': view['context_sha256']},
                   {'label': 'Patient state', 'sha256': view['state_sha256']}]
                  + ([{'label': 'CTCAE v5.0 grading', 'sha256': view['current_grading_sha256']}]
                     if 'current_grading_sha256' in view else [])
                  + ([{'label': 'Model scope', 'sha256': view['scope_sha256']}] if 'scope_sha256' in view else []))
    return _finish(record)


def record_for_renal_pathways(view, evidence=None):
    """Run record for `patient_renal_pathways.patient_renal_pathways` (completed views only)."""
    evidence = evidence or load_evidence_status()
    estimate = view['covariate_estimate']
    record = _base('patient_renal_pathways', 'elimination_pathway_split', 'Lenalidomide elimination pathways for this record',
                   view['revision_id'], estimate['state_schema_version'], estimate['state_sha256'],
                   'lenalidomide_renal_pathways_2026', evidence)
    wb = estimate['weight_basis_evidence']
    record.update(
        status=view['status'], inputs_from_record=_state_inputs(estimate), derived_inputs=_derived(estimate),
        assumptions=[
            {'name': 'How secretion changes with kidney function', 'reading': 'intact nephron: in proportion to creatinine clearance',
             'status': 'partly_contradicted', 'evidence': view['reading_note']},
            {'name': 'Creatinine clearance', 'reading': f"Cockcroft-Gault, {estimate['weight_basis'].replace('_', ' ')}",
             'status': wb['assessment_status'], 'evidence': 'The calibration study measured creatinine clearance from urine; here it is estimated from serum creatinine. ' + wb['summary']},
            {'name': 'Unbound fraction', 'reading': f"{view['calibration']['fu']}", 'status': 'sourced',
             'evidence': '23% plasma protein binding in myeloma patients (EMA 2008, page 20).'},
            {'name': 'Normal-group creatinine clearance', 'reading': f"{view['calibration']['crcl_ml_min']:g} mL/min", 'status': 'assumed',
             'evidence': 'The study reports only "> 80 mL/min"; 110 is the primary scenario of the locked plan.'},
            {'name': 'Bioavailability', 'reading': '1', 'status': 'assumed', 'evidence': '85% urinary recovery of unchanged drug implies at least about 0.85.'}],
        applicability=[{'item': 'creatinine_clearance', 'value': view['crcl_ml_min'], 'unit': 'mL/min',
                        'reference': 'calibration and check groups about 10-140 mL/min', 'status': view['range_status']}],
        warnings=list(view['warnings']), limitations=list(view['limitations']),
        checksums=[{'label': 'View', 'sha256': view['report_sha256']},
                   {'label': 'Covariate estimate', 'sha256': estimate['report_sha256']},
                   {'label': 'Pathway evidence', 'sha256': view['evidence_sha256']},
                   {'label': 'Pathway check report (file)', 'sha256': evidence['models']['lenalidomide_renal_pathways_2026']['layers']['external_consistency']['evidence_report_file_sha256']},
                   {'label': 'Patient state', 'sha256': estimate['state_sha256']}])
    return _finish(record)



def _body_map_flow_assumptions(map_view):
    """Digital human 1.1: the reference blood flow and the blood-to-plasma ratio behind the extraction per pass."""
    if 'blood_flow' not in map_view:
        return []
    bf, ex = map_view['blood_flow'], map_view['extraction']
    return [{'name': 'Renal blood flow', 'reading': f"{bf['renal_blood_flow_ml_min']:.0f} mL/min (reference adult male)",
             'status': 'by_design', 'evidence': bf['basis'] + ' ' + bf['not_this']},
            {'name': 'Blood-to-plasma ratio', 'reading': f"{ex['blood_to_plasma_ratio']:.3f}", 'status': 'assumed',
             'evidence': ex['basis']}]


def record_for_body_map(map_view, pathways_view, evidence=None):
    """Run record for the record-mode body map (Digital human 1.0, step 1.3b).

    The numbers are those of the 2.0b pathways view for the same revision, so the record is that view's record with the
    body-map view and the pinned 3D assets added to its checksums.
    """
    from .body_map_assets import MANIFEST_SHA256, load_manifest
    record = record_for_renal_pathways(pathways_view, evidence)
    record.pop('record_sha256')
    record.pop('validation')
    manifest = load_manifest()
    record.update(kind='body_map', title='Lenalidomide elimination body map for this record')
    record['assumptions'] = record['assumptions'] + _body_map_flow_assumptions(map_view)
    record['checksums'] = ([{'label': 'Body map view', 'sha256': map_view['view_sha256']}] + record['checksums'] +
                           [{'label': '3D asset manifest', 'sha256': MANIFEST_SHA256}] +
                           [{'label': f"3D model ({o['class']} organs)", 'sha256': o['sha256']} for o in manifest['outputs']] +
                           ([{'label': 'Reference physiology (ICRP 89)', 'sha256': map_view['blood_flow']['source_sha256']},
                             {'label': 'Blood-to-plasma extract (Chen 2012)', 'sha256': map_view['extraction']['source_sha256']}]
                            if 'blood_flow' in map_view else []))
    record['limitations'] = record['limitations'] + [
        'The 3D organs are reference anatomy (Human Reference Atlas male body), not this record\'s body; their size, '
        'position and colour carry no result.']
    return _finish(record)


def record_for_body_map_explorer(map_view, context=None, evidence=None):
    """Run record for the explorer-mode body map (Digital human 1.0, step 1.4): no patient record, creatinine
    clearance entered directly, otherwise the same model, assumptions and assets as the record mode."""
    from .body_map import load_pathway_report
    from .body_map_assets import MANIFEST_SHA256, load_manifest
    from .patient_renal_pathways import CALIBRATION_CRCL, FU
    evidence = evidence or load_evidence_status()
    if map_view.get('status') != 'completed':
        raise ValueError('The explorer run record needs a completed body-map view.')
    manifest = load_manifest()
    crcl = map_view['crcl_ml_min']
    record = {'schema_version': SCHEMA_VERSION, 'evidence_status_version': evidence['status_version'],
              'evidence_status_sha256': EVIDENCE_SHA256, 'kind': 'body_map_explorer',
              'title': 'Lenalidomide elimination body map (explorer)',
              'result_type': dict(RESULT_TYPES['elimination_pathway_split_explorer'], id='elimination_pathway_split_explorer'),
              'patient_record': {'revision_id': None, 'state_schema_version': None, 'state_sha256': None,
                                 'data': 'none: explorer, creatinine clearance entered on the page'},
              'model': _evidence('lenalidomide_renal_pathways_2026', evidence), 'status': map_view['status'],
              'inputs_from_record': [{'name': 'creatinine_clearance', 'value': crcl, 'unit': 'mL/min',
                                      'origin': 'entered in the explorer (stands for measured creatinine clearance)'}],
              'derived_inputs': [],
              'assumptions': [
                  {'name': 'How secretion changes with kidney function', 'reading': 'intact nephron: in proportion to creatinine clearance',
                   'status': 'partly_contradicted', 'evidence': map_view['band']['status_text'] + (
                       ' ' + map_view['band']['myeloma_note']['text'] if map_view['band'].get('myeloma_note') else '')},
                  {'name': 'Unbound fraction', 'reading': f"{FU} (alternative split shown with 0.60)", 'status': 'sourced',
                   'evidence': '23% plasma protein binding in myeloma patients (EMA 2008, page 20); ex vivo about 40% (EMA 2013, page 20). Exposure is the same under both.'},
                  {'name': 'Normal-group creatinine clearance', 'reading': f"{CALIBRATION_CRCL:g} mL/min", 'status': 'assumed',
                   'evidence': 'The study reports only "> 80 mL/min"; 110 is the primary scenario of the locked plan.'},
                  {'name': 'Bioavailability', 'reading': '1', 'status': 'assumed',
                   'evidence': '85% urinary recovery of unchanged drug implies at least about 0.85.'}] + _body_map_flow_assumptions(map_view),
              'applicability': [{'item': 'creatinine_clearance', 'value': crcl, 'unit': 'mL/min',
                                 'reference': 'calibration and check groups about 10-140 mL/min', 'status': 'within_reported_range'}],
              'warnings': [map_view['band']['status_text']] if map_view['band']['status'] == 'check_disagrees' else [],
              'limitations': list(map_view['limitations']) + [
                  'No patient record: the creatinine clearance is entered directly, so no estimate from serum creatinine is involved.',
                  'The 3D organs are reference anatomy (Human Reference Atlas male body); their size, position and colour carry no result.'],
              'checksums': [{'label': 'Body map view', 'sha256': map_view['view_sha256']}] +
                           ([{'label': 'Observed-data context', 'sha256': context['context_sha256']}] if context else []) +
                           [{'label': 'Pathway evidence', 'sha256': map_view['model']['evidence_sha256']},
                            {'label': 'Pathway check report (file)', 'sha256': map_view['model']['report_file_sha256']}] +
                           ([{'label': 'Myeloma comparison, Simulation 2.0d report (file)',
                              'sha256': map_view['band']['myeloma_note']['report_file_sha256']}] if map_view['band'].get('myeloma_note') else []) +
                           [{'label': 'Unbound-fraction decision record', 'sha256': map_view['model']['fu_record_sha256']},
                            {'label': '3D asset manifest', 'sha256': MANIFEST_SHA256}] +
                           [{'label': f"3D model ({o['class']} organs)", 'sha256': o['sha256']} for o in manifest['outputs']] +
                           [{'label': 'Reference physiology (ICRP 89)', 'sha256': map_view['blood_flow']['source_sha256']},
                            {'label': 'Blood-to-plasma extract (Chen 2012)', 'sha256': map_view['extraction']['source_sha256']}]}
    load_pathway_report()  # refuses a changed check report, as the record mode does through the 2.0b view
    return _finish(record)


def record_for_relative_odds(models, estimate, evidence=None):
    """Run record for the relative-odds rows of `estimated_pk.compare_published_models` (Simulation 4.0a/4.0b).

    `estimate` is the covariate estimate of the same saved revision; it supplies the patient-record inputs. The PK
    models that produce the exposure ratio keep their own records; here they appear as inputs and assumptions.
    """
    evidence = evidence or load_evidence_status()
    rows = [r for r in models['rows'] if 'relative_odds' in r]
    if not rows:
        raise ValueError('No relative odds were computed for this comparison.')
    first = rows[0]['relative_odds']
    record = _base('relative_odds', 'relative_odds_vs_reference', 'Lenalidomide relative odds of grade 3/4 cytopenia',
                   models['revision_id'], estimate['state_schema_version'], estimate['state_sha256'],
                   'lenalidomide_exposure_safety_2016', evidence)
    derived = _derived(estimate)
    for row in rows:
        ref = row['reference_exposure']
        derived.append({'name': f"exposure ratio to reference ({row['label']})", 'value': ref['ratio_to_reference'],
                        'unit': 'ratio', 'method': f"typical daily AUC {ref['typical_daily_auc_ng_h_ml']:.0f} ÷ measured "
                                                   f"{ref['reference_auc_ng_h_ml']} ng·h/mL (CC-5013-PK-001, 25 mg, normal renal function)"})
    assumptions = [
        {'name': 'Exposure measure', 'reading': 'each PK model\'s typical daily AUC ÷ the measured reference AUC', 'status': 'assumed',
         'evidence': 'The source\'s AUC definition was not published. Only the ratio enters, so units cancel; both models reproduce '
                     'the reference within about 5% at normal renal function.'},
        {'name': 'Odds ratios used', 'reading': 'myeloma-only estimates (TGA): thrombocytopenia 2.972, neutropenia 1.982',
         'status': 'sourced', 'evidence': first['source_reconciliation']},
        {'name': 'Time window', 'reading': 'a course of treatment (all cycles up to 1 year), not cycle 1', 'status': 'sourced',
         'evidence': first['time_window']},
        {'name': 'Same disease and baseline count as the reference patient', 'reading': 'implicit in relative odds',
         'status': 'by_design', 'evidence': 'The odds ratio was adjusted for baseline count; without the intercept and the '
                                            'baseline-count coefficient only comparisons at the same baseline follow from it.'}]
    for row in rows:
        v = row['relative_odds'].get('variability')
        if v:
            assumptions.append({'name': f"Between-patient variability in clearance ({row['label']})",
                                'reading': f"SD of ln CL/F {v['omega_cl_sd']:.3f}", 'status': 'assumed' if v.get('assumption') else 'sourced',
                                'evidence': v['source'] + (f" — {v['assumption']}" if v.get('assumption') else '')})
    disease = models.get('declared_disease_code')
    warnings = [f"{row['label']}: {w}" for row in models['rows'] for w in row.get('warnings') or []]
    if disease != 'MM':
        warnings.insert(0, f"Declared disease is {disease}; the odds ratios used are the myeloma-only estimates.")
    safety = load_relative_odds_evidence()
    record.update(
        status='completed', inputs_from_record=_state_inputs(estimate), derived_inputs=derived, assumptions=assumptions,
        applicability=[{'item': 'declared_disease', 'value': disease, 'unit': '',
                        'reference': 'odds ratios estimated in multiple myeloma',
                        'status': 'within_reported_range' if disease == 'MM' else 'outside_reported_range'}],
        warnings=warnings,
        limitations=[first['meaning'], safety['consequence'],
                     'Not reported by the source: ' + '; '.join(safety['not_reported']) + '.',
                     'In severe renal impairment both PK models probably under-predict exposure, so relative odds there are probably understated.'],
        checksums=[{'label': 'Model comparison', 'sha256': models['report_sha256']},
                   {'label': 'Hughes report', 'sha256': models['hughes_report_sha256']},
                   {'label': 'Kim report', 'sha256': models['kim_report_sha256']},
                   {'label': 'Exposure-safety evidence', 'sha256': first['evidence_sha256']},
                   {'label': 'Covariate estimate', 'sha256': estimate['report_sha256']},
                   {'label': 'Patient state', 'sha256': estimate['state_sha256']}])
    return _finish(record)


def load_relative_odds_evidence():
    from .lenalidomide_relative_odds import load_evidence
    return load_evidence()
