"""Phase 4.4: a guided path for one drug through the platform: trials, evidence, label, special populations, exposure
models, dose, credibility and review status. Nothing new is computed: every figure on the path is read from a pinned
source or from an existing view, and each step says what has been checked and what is missing.
"""
from .dose_optimisation import corpus_trials, load_exposure_response
from .extraction_review import queue_view
from .lenalidomide_label import load_label_extract, load_renal_reconciliation
from .patient_state import digest
from .run_record import load_evidence_status
from .special_populations import build as special_population_view

SCHEMA_VERSION = 'guided-path-v1'
STATUS_LABELS = {'done': 'done', 'partial': 'partly', 'not_done': 'not done', 'done_exploratory': 'exploratory',
                 'done_with_open_question': 'done, one open question', 'by_design': 'by design'}
OUTCOME_LABELS = {'consistent': 'consistent', 'model_under_predicts': 'model under-predicts', 'model_over_predicts': 'model over-predicts'}
LAYER_LABELS = {'software_verification': 'Code computes the intended equations', 'transcription_verification': 'Values checked against the source',
                'reproduction': 'Reproduces the data it was built on', 'external_consistency': 'Compared with outside data'}
MODELS = ('lenalidomide_hughes_2019', 'lenalidomide_kim_2026', 'lenalidomide_renal_pathways_2026', 'lenalidomide_exposure_safety_2016')


def _models():
    evidence = load_evidence_status()['models']
    out = []
    for model_id in MODELS:
        e = evidence[model_id]
        layers = [{'label': LAYER_LABELS[k], 'status': STATUS_LABELS.get(v['status'], v['status'].replace('_', ' '))}
                  for k, v in e['layers'].items()]
        groups = e['layers']['external_consistency'].get('result_by_group') or {}
        out.append({'model_id': model_id, 'name': e['name'], 'layers': layers,
                    'outside_results': [{'group': g, 'outcome': OUTCOME_LABELS.get(o, o)} for g, o in groups.items()]})
    return out


def lenalidomide_path():
    trials = corpus_trials()
    label = load_label_extract()
    sp = special_population_view('lenalidomide')
    kinds = {}
    for row in sp['rows']:
        for st in row['statements']:
            kinds[st['kind_label']] = kinds.get(st['kind_label'], 0) + 1
    review = queue_view()
    len_groups = [g for g in review['groups'] if g['id'].startswith('lenalidomide_')]
    review_counts = {'values': sum(len(g['items']) for g in len_groups), 'reviewed': sum(g['reviewed'] for g in len_groups)}
    er = load_exposure_response()
    rec = load_renal_reconciliation()
    steps = [
        {'id': 'trials', 'title': 'Clinical trials', 'question': 'What has been studied?',
         'found': f"{trials['matched']} of {trials['corpus_trials']} interventional myeloma trials test lenalidomide by exact name "
                  f"({trials['by_phase'][0][1]} of them {trials['by_phase'][0][0].lower()}); "
                  f"{trials['mention_only_not_matched']} more mention it inside a combination name.",
         'checked': 'Corpus pinned by checksum (snapshot ' + trials['retrieved'][:10] + '). Intervention names matched exactly to the alias catalog.',
         'missing': 'Dose levels used in trials (arm descriptions are not in the corpus).',
         'links': [('Trial explorer', 'home', {}), ('Dose view: trials by phase', 'landscape.lenalidomide_dose_optimisation', {})]},
        {'id': 'knowledge', 'title': 'Drug knowledge and label', 'question': 'What is the drug, and what does its label say?',
         'found': f"REVLIMID prescribing information, revision 3/2023: myeloma starting dose {label['multiple_myeloma_dosing']['combination_starting_dose']['dose_mg']} mg "
                  f"days 1-21 with dexamethasone; maintenance {label['multiple_myeloma_dosing']['maintenance_starting_dose']['dose_mg']} mg; "
                  f"{len(label['renal_dose_adjustments']['rows'])} renal dose-adjustment rows (Table 3). Mechanism, safety and interaction records in the drug catalog.",
         'checked': 'Label quotes checked against the file text; Table 3 also against the rendered page. AI-assisted, owner review pending.',
         'missing': 'Adverse reactions, warnings and clinical studies sections of the label are not extracted.',
         'links': [('Drug knowledge', 'landscape.drug_knowledge_detail', {'entity': 'lenalidomide'}), ('Regulatory evidence', 'landscape.regulatory', {}),
                   ('Safety', 'landscape.safety', {})]},
        {'id': 'special_populations', 'title': 'Special populations', 'question': 'How do kidney, liver, age and body size change exposure?',
         'found': '; '.join(f'{n} {k.lower()}' for k, n in kinds.items()) + '.',
         'checked': 'Every value resolved against its pinned source before display. Sources reconciled: the label and the EMA table describe the same renal study, '
                    'grouped by Cockcroft-Gault and by measured clearance (' + rec['items'][0]['status'].replace('_', ' ') + ').',
         'missing': 'No gaps in the five domains. Moderate and severe hepatic impairment were not studied (label), so nothing is known there; kidney function dominates the evidence.',
         'links': [('Lenalidomide in special populations', 'landscape.special_populations', {'drug': 'lenalidomide'})]},
        {'id': 'exposure', 'title': 'Exposure models', 'question': 'What exposure would a synthetic patient have?',
         'found': 'Two population PK models (Hughes 2019, Kim 2026), an elimination-pathway model, and an exposure-safety relationship, run on synthetic records in the Patient Lab, inside each model\'s scope.',
         'checked': 'See each model below. Both PK models were compared with the dedicated renal study, and rechecked with virtual subjects matched to that study: both under-predict exposure in moderate and severe impairment.',
         'missing': 'No model is validated for clinical prediction. Below 36 mL/min (Hughes) or outside eGFR 11.1-94.7 (Kim) the platform refuses to compute.',
         'links': [('Patient Lab', 'landscape.patient_directory', {}), ('Model library', 'landscape.drug_capability_library', {'q': 'lenalidomide'})]},
        {'id': 'dose', 'title': 'Dose', 'question': 'How do exposure and safety odds move between dose levels?',
         'found': 'Typical daily exposure at each model\'s own study doses for one synthetic record, with relative odds of grade 3/4 cytopenia, next to the label\'s doses.',
         'checked': 'Every cell recomputes from pinned sources in tests. No dose is ranked or recommended.',
         'missing': f"A usable exposure-efficacy relationship: none found. The one myeloma analysis ({er['design']['n_patients']} patients, {er['time_to_progression']['events']} events) "
                    'is shown on the dose page but not used.',
         'links': [('Dose view', 'landscape.lenalidomide_dose_optimisation', {})]},
        {'id': 'credibility', 'title': 'Credibility and review', 'question': 'How far can these results be trusted?',
         'found': 'One credibility record per model in the ICH M15 structure, model scorecards and enforced scopes.',
         'checked': f"{review_counts['reviewed']} of {review_counts['values']} lenalidomide values that feed calculations have been reviewed by the platform owner.",
         'missing': 'Independent review of the extractions; author answers on the Hughes weight basis and the Kim clearance equation.',
         'links': [('Credibility records', 'credibility_records', {}), ('Extraction review', 'extraction_review', {}), ('Models', 'model_scorecards', {})]},
    ]
    result = {'schema_version': SCHEMA_VERSION, 'drug': 'lenalidomide', 'title': 'Lenalidomide: from trials to dose',
              'steps': steps, 'models': _models(), 'review': review_counts,
              'not_this': 'A map of what the platform holds for one drug. Not dosing guidance and not a clinical prediction.',
              'clinical_prediction_validated': False}
    result['path_sha256'] = digest(result)
    return result
