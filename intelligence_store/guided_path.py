"""Phase 4.4: a guided path for one drug through the platform: trials, evidence, label, special populations, exposure
models, dose, credibility and review status. Nothing new is computed: every figure on the path is read from a pinned
source or from an existing view, and each step says what has been checked and what is missing.
"""
from .dose_optimisation import corpus_trials, load_exposure_response
from .extraction_review import owner_review, queue_view
from .lenalidomide_label import load_label_extract, load_label_pk_extract, load_renal_reconciliation
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


def _pk_step(pk, review_text):
    a, e = pk['absorption'], pk['elimination']
    food, ex, dial = a['food_effect'], e['excretion'], pk['renal_dialysis']
    dig = pk['drug_interactions_7']['digoxin']['digoxin_cmax_and_auc_increase_percent']
    return {
        'id': 'pharmacokinetics', 'title': 'Label pharmacokinetics and interactions',
        'question': 'How is the drug absorbed and eliminated, and what interacts with it?',
        'found': (f"Peak at {a['tmax']['tmax_range_h'][0]:g}-{a['tmax']['tmax_range_h'][1]:g} h; a high-fat meal lowers AUC about "
                  f"{food['auc_decrease_percent_approx']}% and Cmax about {food['cmax_decrease_percent_approx']}%; half-life "
                  f"{e['half_life']['healthy_h']:g} h in healthy subjects and {e['half_life']['patients_h'][0]:g}-{e['half_life']['patients_h'][1]:g} h "
                  f"in patients; about {ex['radioactive_dose_percent_10_days']['urine']}% of a radioactive dose in urine "
                  f"({ex['unchanged_in_urine_24_h_percent_of_radioactive_dose']}% as unchanged drug within 24 h); about "
                  f"{dial['removed_percent_of_drug_in_body']}% removed in a {dial['session_h']}-hour haemodialysis session. "
                  f"Interactions (label): digoxin Cmax and AUC up {dig}%; no significant or clinically relevant change in "
                  "lenalidomide exposure with dexamethasone, quinidine or temsirolimus; a P-gp substrate; no CYP450 inhibition or "
                  "induction; caution with agents that raise thrombosis risk; PT and INR monitoring with warfarin."),
        'checked': 'REVLIMID label, revision 3/2023, sections 12.3 and 7: every quote matched by script against the label file '
                   '(5 November 2026). AI-assisted. ' + review_text,
        'missing': 'The label states no absolute bioavailability (the platform\'s bound comes from a mass-balance study, Simulation 2.0e). '
                   'No interaction is modelled: the Patient Lab runs one drug at a time.',
        'links': [('Label pharmacokinetics and interactions', 'landscape.special_populations', {'drug': 'lenalidomide', '_anchor': 'sp-label-pk'})]}


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
    pk = load_label_pk_extract()
    pk_status = owner_review('intelligence_store/data/lenalidomide_label_2023_pk_v1.json')
    pk_review = pk_status[0]['text'] if pk_status else 'Not in a review queue.'
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
         'checked': 'Label quotes checked against the file text; Table 3 also against the rendered page. AI-assisted; the dosing values and Table 3 were reviewed against the label by the platform owner (extraction review rounds 1 and 2, November 2026). Not an independent review.',
         'missing': 'Adverse reactions, warnings and clinical studies sections of the label are not extracted.',
         'links': [('Drug knowledge', 'landscape.drug_knowledge_detail', {'entity': 'lenalidomide'}), ('Regulatory evidence', 'landscape.regulatory', {}),
                   ('Safety', 'landscape.safety', {})]},
        {'id': 'special_populations', 'title': 'Special populations', 'question': 'How do kidney, liver, age and body size change exposure?',
         'found': '; '.join(f'{n} {k.lower()}' for k, n in kinds.items()) + '.',
         'checked': 'Every value matched by script to the platform\'s stored extract of its source before display (the extract\'s review status is shown on the special-populations page). Sources reconciled: the label and the EMA table describe the same renal study, '
                    'grouped by Cockcroft-Gault and by measured clearance (' + rec['items'][0]['status'].replace('_', ' ') + ').',
         'missing': 'Each of the five domains has at least one sourced statement. Moderate and severe hepatic impairment were not studied (label), so nothing is known there; kidney function dominates the evidence.',
         'links': [('Lenalidomide in special populations', 'landscape.special_populations', {'drug': 'lenalidomide'})]},
        _pk_step(pk, pk_review),
        {'id': 'exposure', 'title': 'Exposure models', 'question': 'What typical exposure do the models give for a synthetic record?',
         'found': 'Two population PK models (Hughes 2019, Kim 2026), an elimination-pathway model, and an exposure-safety relationship, run on synthetic records in the Patient Lab, inside each model\'s scope.',
         'checked': 'See each model below. Both PK models were compared with the dedicated renal study, rechecked with virtual subjects matched to that study, and checked against myeloma patients under a prespecified plan (Bridoux 2016; recorded deviation, outcome largely known from the abstract): Hughes under-predicts exposure in moderate and severe impairment, Kim in severe; for Kim in moderate the checks disagree.',
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
