"""Inventory installed drug references and registered models; no model execution."""
import copy
from .drug_aliases import load_alias_catalog
from .mechanisms import load_annotation_catalog
from .safety import load_safety_catalog
from .interactions import load_interaction_catalog
from .model_coverage import load_coverage_contract, CONTRACT_SHA256 as COVERAGE_SHA
from .pk_model_inputs import load_input_contract, INPUT_CONTRACT_SHA256
from .pk_parameter_reference import load_parameter_extract, EXTRACT_SHA256
from .published_transit_reference import load_structure_contract, CONTRACT_SHA256 as STRUCTURE_SHA
from .educational_pk import load_execution_contract, CONTRACT_SHA256 as EXECUTION_SHA
from .patient_state import digest

from .drug_research_tools import research_tool_registry
from .kim_model import load_extract as load_kim_extract, load_form_assessment, EXTRACT_SHA256 as KIM_EXTRACT_SHA, FORM_ASSESSMENT_SHA256
from .bortezomib_platelet_evidence import load_model_extract as load_bortezomib_extract, EXTRACT_SHA256 as BORTEZOMIB_EXTRACT_SHA

METHOD = 'drug-capability-inventory-v1.4'
DISEASE_LABELS = {'MM':'Multiple Myeloma', 'CLL':'Chronic Lymphocytic Leukemia',
                  'AML':'Acute Myeloid Leukemia', 'ALL':'Acute Lymphoblastic Leukemia'}


def _exposure_model():
    """Check installed contracts without running the solver or patient review."""
    coverage = load_coverage_contract()
    inputs = load_input_contract()
    load_structure_contract()
    load_parameter_extract()
    execution = load_execution_contract()
    return {
        'model_id': 'hughes-educational-pk-v1', 'drug_id': 'lenalidomide',
        'status': 'implemented_educational', 'endpoint': 'plasma concentration and exposure',
        'source': copy.deepcopy(coverage['source']),
        'source_populations': [{'code': code, 'label': DISEASE_LABELS[code], 'subject_count': n}
                               for code,n in coverage['disease_counts'].items()],
        'covariates': copy.deepcopy(inputs['fields']),
        'execution_limits': {k: execution[k] for k in ('maximum_horizon_h','maximum_events','required_interval_h')},
        'contract_versions': {'coverage': coverage['contract_version'], 'input': inputs['contract_version'],
                              'execution': execution['contract_version']},
        'contract_sha256': {'coverage': COVERAGE_SHA, 'input': INPUT_CONTRACT_SHA256,
                            'structure': STRUCTURE_SHA, 'parameters': EXTRACT_SHA256, 'execution': EXECUTION_SHA},
        'assumptions': ['Deterministic typical parameters; random effects and observation error omitted.',
                        'Source population membership and marginal input ranges do not establish patient suitability.',
                        'Project execution limits are not clinical dosing recommendations.'],
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
    }


def _kim_exposure_model():
    """Kim 2026: second lenalidomide exposure model (renal impairment, unbound scale); contracts only."""
    extract = load_kim_extract()
    form = load_form_assessment()
    population = extract['study_population']
    return {
        'model_id': 'kim-2026-educational-pk-v1', 'drug_id': 'lenalidomide',
        'status': 'implemented_educational', 'endpoint': 'total and unbound plasma concentration and exposure',
        'source': {'citation': extract['source']['citation'], 'doi': extract['source']['doi']},
        'source_populations': [{'code': 'MM', 'label': DISEASE_LABELS['MM'], 'subject_count': population['n']}],
        'covariates': sorted(extract['covariate_definitions']),
        'contract_versions': {'extract': extract['extract_version'], 'cl_form_assessment': form.get('assessment_version')},
        'contract_sha256': {'extract': KIM_EXTRACT_SHA, 'cl_form_assessment': FORM_ASSESSMENT_SHA256},
        'assumptions': ['Deterministic typical parameters; random effects and observation error omitted.',
                        'The printed CL/F equation form is unresolved; a multiplicative reading is used until the authors confirm.',
                        'Fitted in 30 Korean patients with multiple myeloma at steady state; other populations are not represented.'],
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
    }


def _bortezomib_pk_component():
    """Bortezomib three-compartment PK: runs only inside the platelet research tool, not as patient PK."""
    extract = load_bortezomib_extract()
    return {
        'model_id': 'bortezomib-3cmt-lignet-2022-pk-v1', 'drug_id': 'bortezomib',
        'status': 'research_component', 'endpoint': 'plasma concentration driving the platelet model',
        'source': {'citation': extract['source']['citation'], 'doi': extract['source']['doi']},
        'used_by': ['bortezomib-platelet-timecourse'],
        'contract_sha256': {'extract': BORTEZOMIB_EXTRACT_SHA},
        'assumptions': ['Single linear clearance: about 7-fold below the label first-dose clearance; against measured '
                        'exposure, first-dose AUC is 2-3-fold too high in two studies and consistent in one, and the rise '
                        'over repeated doses is too small.',
                        'Not offered as a patient PK calculation.'],
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
    }


def capability_inventory():
    catalog = load_alias_catalog()
    aliases = {'catalog_sha256': catalog['sha256'], 'catalog_version': catalog['catalog_version'],
               'catalog_entries': catalog['entries']}
    references, warnings, provenance = {}, [], {
        'aliases': {'version':catalog['catalog_version'], 'sha256':catalog['sha256']}}
    for name, loader in [('mechanism',load_annotation_catalog), ('safety',load_safety_catalog),
                         ('interactions',load_interaction_catalog)]:
        try:
            result = loader(aliases)
            references[name] = result['entity_index']
            provenance[name] = {'version':result['catalog_version'], 'sha256':result['sha256']}
        except ValueError:
            references[name] = None
            warnings.append({'area':name,'message':'Installed reference catalog could not be verified; its coverage is unavailable.'})
    model = None
    try:
        model = _exposure_model()
    except ValueError:
        warnings.append({'area':'exposure','message':'The Hughes 2019 lenalidomide model contracts could not be verified.'})
    extra_models = {}
    for builder, label in [(_kim_exposure_model, 'Kim 2026 lenalidomide'), (_bortezomib_pk_component, 'bortezomib PK component')]:
        try:
            card = builder()
            extra_models.setdefault(card['drug_id'], []).append(card)
        except ValueError:
            warnings.append({'area':'exposure','message':f'The {label} model contracts could not be verified.'})
    research_registry = research_tool_registry()
    from .capability_levels import LEVELS, drug_level
    from .model_scorecards import all_scorecards
    scorecards = all_scorecards()
    rows = []
    for entry in sorted(catalog['entries'], key=lambda e:e['canonical_name'].casefold()):
        capabilities = {}
        for name, index in references.items():
            record = index.get(entry['id']) if index is not None else None
            present = record is not None
            if name == 'mechanism' and present:
                present = any(record['fields'].values())
            capabilities[name] = {'status': 'unavailable' if index is None else
                                  'curated_reference' if present else 'not_curated'}
        registered = entry['id'] == 'lenalidomide'
        exposure_models = ([copy.deepcopy(model)] if registered and model else []) + copy.deepcopy(extra_models.get(entry['id'], []))
        statuses = {m['status'] for m in exposure_models}
        capabilities['exposure'] = {'status': 'implemented_educational' if 'implemented_educational' in statuses else
                                    'research_component_only' if statuses else
                                    'unavailable' if registered else 'not_registered'}
        capabilities['efficacy'] = {'status':'not_registered'}
        capabilities['toxicity'] = {'status':'not_registered'}
        research_tools = copy.deepcopy(research_registry.get(entry['id'],[]))
        for kind in ('target_activity','research_timecourse','assumption_experiment','drug_effect_timecourse'):
            candidates=[t for t in research_tools if t['kind']==kind]
            capabilities[kind]={'status':'available_research_tool' if any(t['availability']=='available' for t in candidates)
                                else 'unavailable' if candidates else 'not_registered'}
        row = {'research_tools':research_tools,'entity_id':entry['id'], 'label':entry['canonical_name'], 'aliases':copy.deepcopy(entry['aliases']),
               'identity_reference':copy.deepcopy(entry['source']), 'capabilities':capabilities,
               'exposure_model':copy.deepcopy(model) if registered and model else None,
               'exposure_models':exposure_models,
               'capability_level':drug_level(entry['canonical_name'],
                                             any(capabilities[k]['status']=='curated_reference' for k in ('mechanism','safety','interactions')),
                                             scorecards),
               'disease_indications':'not_assessed_by_this_inventory'}
        rows.append(row)
    report = {'schema_version':'drug-capability-inventory-v1','method_version':METHOD,
              'scope':'Installed curated drug entities and explicitly registered models only. Not a comprehensive medication library.',
              'entries':rows,'warnings':warnings,'provenance':provenance,
              'counts':{'drug_entities':len(rows),
                        'educational_exposure_models':sum(m['status']=='implemented_educational' for r in rows for m in r['exposure_models']),
                        'research_exposure_components':sum(m['status']=='research_component' for r in rows for m in r['exposure_models']),
                        'efficacy_models':0,'toxicity_models':0},
              'capability_level_counts':{level['id']:sum(r['capability_level']['id']==level['id'] for r in rows) for level in LEVELS},
              'capability_levels':[{k:level[k] for k in ('id','label','meaning')} for level in LEVELS],
              # Every registered kind is counted, so a new kind cannot be silently left out.
              'research_tool_counts':{kind:sum(t['availability']=='available' and t['kind']==kind for r in rows for t in r['research_tools'])
                                      for kind in sorted({t['kind'] for tools in research_registry.values() for t in tools})},
              'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
              'limitation':'Catalog presence is not current-label verification, disease indication, approval, model applicability or clinical suitability. Safety references are not toxicity predictions. Generic experiments are not drug-specific models.'}
    report['report_sha256'] = digest(report)
    return report
