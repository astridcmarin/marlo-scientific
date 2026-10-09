"""Evidence/planning review of a saved state. No simulation or model eligibility claim."""
import copy
import hashlib
import json
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .patient_state import UNITS, digest
from .patient_state_revisions import read_revision
from .saved_scenarios import read_scenario

METHOD_VERSION='patient-model-review-v1.0'
CONTRACT_PATH=Path(__file__).parent/'data'/'patient_model_contract_v1.json'
CONTRACT_SHA256='e96ba7cfd997c7372b4e6caa393fea984ec7e596e61f3aa3d2a0dbb273bb7bed'


def load_model_contract(path=CONTRACT_PATH):
    try:
        raw=Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=CONTRACT_SHA256:raise ValueError('Contract checksum mismatch')
        contract=json.loads(raw)
        if (contract['schema_version']!='patient-model-contract-v1'
                or contract['execution_enabled'] is not False or contract['drug']!='lenalidomide'):
            raise ValueError('Unsupported contract')
        return contract
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise ValueError('Model-review contract is missing or changed. Restore the bundled Step 33 file; no model review was generated.') from exc


def review_patient_model(revision_id):
    row=read_revision(revision_id)
    if row is None:raise ValueError('Patient-state revision record does not exist.')
    scenario=read_scenario(row.scenario_id)
    contract=load_model_contract()
    profile=scenario.payload['analysis']['report']['profile']
    supported=profile['selected_drug']==contract['drug']
    fields=[{'field':name,'availability':'unknown' if value['value'] is None else 'recorded',
             'input':copy.deepcopy(value)} for name,value in row.payload['state']['fields'].items()]
    known=[f['field'] for f in fields if f['availability']=='recorded']
    unknown=[f['field'] for f in fields if f['availability']=='unknown']
    blockers=copy.deepcopy(contract['global_blockers']) if supported else [
        {'code':'unsupported_drug','message':'This planning contract reviews lenalidomide only. No alternate drug model is substituted.'}]
    report={'schema_version':'patient-model-review-report-v1','method_version':METHOD_VERSION,
            'revision_id':row.id,'revision_number':row.revision_number,'scenario_id':row.scenario_id,
            'revision_payload_sha256':row.payload_sha256,'state_sha256':row.state_sha256,
            'scenario_payload_sha256':scenario.payload_sha256,
            'contract_version':contract['contract_version'],'contract_sha256':CONTRACT_SHA256,
            'status':'blocked_model_review' if supported else 'unsupported_drug',
            'ready_for_personalized_simulation':False,'simulation_status':'not_run',
            'selected_model':None,'patient_parameter_adjustments':None,'predicted_outputs':None,
            'captured_scenario_inputs':copy.deepcopy(profile),
            'fields':fields,'recorded_fields':known,'unknown_fields':unknown,
            'input_count':len(UNITS),'blockers':blockers,
            'candidate_models':copy.deepcopy(contract['candidate_models']) if supported else [],
            'label_context':copy.deepcopy(contract['label_context']) if supported else None,
            'invariants':copy.deepcopy(contract['invariants']),
            'limitation':'Input-presence and model-planning review only. All candidate equations, applicability and reproduction checks remain unresolved. No individual eligibility, clinical suitability, dose recommendation or exposure prediction is established.'}
    report['report_sha256']=digest(report)
    return report


def register_patient_model_review_commands(app):
    @app.cli.command('patient-model-review')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True,help='Saved patient-state record ID, not its revision number.')
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def patient_model_review(revision_id,json_output,output):
        """Inspect inputs and unresolved model requirements without running PK."""
        try:
            report=review_patient_model(revision_id)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved model review: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Scenario #{report['scenario_id']} | Patient-state record #{revision_id} | {report['status']}")
                click.echo(f"Recorded inputs: {len(report['recorded_fields'])}/{report['input_count']}; unknown: {len(report['unknown_fields'])}")
                click.echo('Simulation: not_run | Personalized simulation ready: false')
                for item in report['blockers']:click.echo(f"[BLOCKED] {item['code']}: {item['message']}")
                click.echo(report['limitation'])
        except (ValueError,OSError,SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
