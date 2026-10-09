"""Read-only association review of explicit covariates and an immutable patient revision."""
import copy
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .patient_state import digest
from .patient_state_revisions import read_revision
from .saved_scenarios import read_scenario
from .pk_model_inputs import (validate_model_inputs,preview_model_inputs,load_input_contract,
    INPUT_CONTRACT_SHA256,_no_duplicate_keys)
from .published_transit_reference import CONTRACT_SHA256,load_structure_contract

METHOD_VERSION='patient-model-binding-preview-v1.0'


def review_model_binding(revision_id,inputs):
    if type(revision_id) is not int or revision_id<=0:
        raise ValueError('Revision ID must be a positive integer record ID.')
    canonical=validate_model_inputs(inputs)
    row=read_revision(revision_id)
    if row is None:raise ValueError('Saved patient-state revision does not exist.')
    scenario=read_scenario(row.scenario_id)
    if scenario is None:raise ValueError('Source scenario is missing.')
    contract=load_structure_contract();input_contract=load_input_contract()
    profile=scenario.payload['analysis']['report']['profile']
    supported=profile['selected_drug']==contract['drug']
    state=copy.deepcopy(row.payload['state'])
    ffm=canonical['fields']['fat_free_mass']['value']
    crcl=canonical['fields']['creatinine_clearance']['value']
    weight=state['fields']['weight']['value']
    saved_crcl=state['fields']['creatinine_clearance']['value']
    if crcl is None:crcl_status='model_input_unknown'
    elif saved_crcl is None:crcl_status='additional_explicit_input'
    elif math.isclose(crcl,saved_crcl,rel_tol=1e-12,abs_tol=1e-12):crcl_status='value_matches_provenance_separate'
    else:crcl_status='value_conflict'
    if ffm is None:ffm_status='model_input_unknown'
    elif weight is None:ffm_status='recorded_weight_unknown'
    elif ffm>weight:ffm_status='exceeds_recorded_total_weight'
    else:ffm_status='not_greater_than_recorded_total_weight'
    conflicts=[]
    if crcl_status=='value_conflict':conflicts.append('creatinine_clearance_value_conflict')
    if ffm_status=='exceeds_recorded_total_weight':conflicts.append('fat_free_mass_exceeds_recorded_weight')
    preview=preview_model_inputs(canonical) if supported else None
    blockers=[{'code':'applicability_not_established','message':'A scenario drug-name match and numeric range checks do not establish model applicability.'},
              {'code':'covariate_provenance_not_verified','message':'Model-input methods are recorded declarations; no FFM or CrCl estimator is executed or independently verified.'},
              {'code':'treatment_request_missing','message':'No explicit treatment request is attached. The scenario dose is not promoted into a simulation regimen.'}]
    if not supported:blockers.insert(0,{'code':'unsupported_drug','message':'Only the Hughes lenalidomide contract is supported; no other drug model is substituted.'})
    for code in conflicts:blockers.append({'code':code,'message':'Explicit model inputs differ from the saved state or violate the FFM/total-weight consistency check. Both are retained for review.'})
    if preview and preview['status']!='parameter_preview_available':
        blockers.append({'code':preview['status'],'message':'The standalone model-input preview withheld parameter algebra.'})
    binding={'revision_id':row.id,'revision_payload_sha256':row.payload_sha256,'state_sha256':row.state_sha256,
        'scenario_id':row.scenario_id,'scenario_payload_sha256':scenario.payload_sha256,
        'model_inputs_sha256':digest(canonical),'structure_contract_sha256':CONTRACT_SHA256,
        'input_contract_sha256':INPUT_CONTRACT_SHA256}
    report={'schema_version':'patient-model-binding-preview-v1','method_version':METHOD_VERSION,
        'status':'unsupported_drug' if not supported else ('binding_conflict' if conflicts else 'review_required'),
        'binding':binding,'binding_sha256':digest(binding),'revision_number':row.revision_number,
        'revision_title':row.title,'selected_drug':profile['selected_drug'],
        'model_contract_version':contract['contract_version'],'model_input_contract_version':input_contract['contract_version'],
        'captured_state':state,'explicit_model_inputs':canonical,
        'consistency_checks':[
            {'code':'creatinine_clearance_comparison','status':crcl_status,
             'saved_input':copy.deepcopy(state['fields']['creatinine_clearance']),
             'explicit_input':copy.deepcopy(canonical['fields']['creatinine_clearance']),
             'limitation':'Value agreement does not verify matching estimation methods; the saved-state schema has no CrCl-method field.'},
            {'code':'fat_free_mass_total_weight_comparison','status':ffm_status,
             'recorded_total_weight':copy.deepcopy(state['fields']['weight']),
             'explicit_fat_free_mass':copy.deepcopy(canonical['fields']['fat_free_mass']),
             'limitation':'A consistency check only. No FFM is derived or substituted from weight.'}],
        'conflicts':conflicts,'standalone_input_preview':preview,
        'ready_for_patient_simulation':False,'simulation_status':'not_run','predicted_outputs':None,
        'blockers':blockers,
        'limitation':'Read-only proposed association, exported on request. No binding record is saved, no patient input is replaced, no treatment or concentration simulation runs. Standalone parameter algebra remains separate from patient applicability.'}
    report['report_sha256']=digest(report)
    return report


def register_patient_model_binding_commands(app):
    @app.cli.command('patient-model-bind-preview')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True,
                  help='Saved patient-state record ID, not a scenario ID or revision number.')
    @click.option('--inputs-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(revision_id,inputs_file,json_output,output):
        """Review an explicit model-input association; no write or simulation."""
        try:
            with inputs_file.open('rb') as handle:raw=handle.read(65537)
            if len(raw)>65536:raise ValueError('Model input file exceeds 64 KiB.')
            inputs=json.loads(raw.decode('utf-8'),object_pairs_hook=_no_duplicate_keys)
            report=review_model_binding(revision_id,inputs)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved binding preview export: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Patient-state record #{revision_id} | Scenario #{report['binding']['scenario_id']} | {report['status']}")
                for check in report['consistency_checks']:click.echo(f"{check['code']}: {check['status']}")
                click.echo('Simulation: not_run | Patient simulation ready: false')
                for blocker in report['blockers']:click.echo(f"[BLOCKED] {blocker['code']}: {blocker['message']}")
                click.echo(report['limitation'])
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
