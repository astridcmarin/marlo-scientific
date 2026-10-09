"""Explicit synthetic administration requests; validation does not run treatment or PK."""
import copy
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .patient_state import digest
from .pk_model_inputs import _no_duplicate_keys
from .patient_model_binding import review_model_binding

SCHEMA_VERSION='synthetic-treatment-request-v1'
VALIDATION_VERSION='synthetic-treatment-validation-v1.0'
PLAN_VERSION='patient-treatment-preview-v1.0'
MAX_HORIZON_H=168.0
MAX_EVENTS=20


def _number(value,label,zero=False,maximum=1000000):
    if type(value) not in (int,float):raise ValueError(f'{label}: expected a JSON number.')
    try:value=float(value)
    except (ValueError,OverflowError):raise ValueError(f'{label}: number is not representable.') from None
    if not math.isfinite(value) or value<0 or (not zero and value==0) or value>maximum:
        raise ValueError(f'{label}: invalid value or implementation bound exceeded.')
    return value


def _provenance(origin,source,label):
    if origin not in ('synthetic_input','assumption'):raise ValueError(f'{label}: use synthetic_input or assumption.')
    if source is not None:
        if not isinstance(source,str) or not 1<=len(source.strip())<=1000:
            raise ValueError(f'{label}: source_ref must be nonblank text up to 1000 characters or null.')
        source=source.strip()
    if origin=='assumption' and source is None:raise ValueError(f'{label}: an assumption requires source_ref.')
    return source


def _quantity(raw,unit,label,zero=False,maximum=1000000):
    if not isinstance(raw,dict) or set(raw)!={'value','unit'} or raw['unit']!=unit:
        raise ValueError(f'{label}: supply value and unit {unit}; no conversion is performed.')
    return {'value':_number(raw['value'],label,zero,maximum),'unit':unit}


def validate_treatment_request(request):
    keys={'schema_version','purpose','drug','route','formulation','origin','source_ref','horizon','events'}
    if not isinstance(request,dict) or set(request)!=keys:raise ValueError('Treatment request has missing or unsupported fields.')
    if request['schema_version']!=SCHEMA_VERSION or request['purpose']!='synthetic_educational':
        raise ValueError('Only the synthetic educational treatment-request schema is supported.')
    if request['drug']!='lenalidomide' or request['route']!='oral' or request['formulation']!='capsule':
        raise ValueError('This initial request contract supports lenalidomide/oral/capsule only; no drug, route or formulation substitution.')
    source=_provenance(request['origin'],request['source_ref'],'Request')
    horizon=_quantity(request['horizon'],'h','Horizon',maximum=MAX_HORIZON_H)
    events=request['events']
    if not isinstance(events,list) or not 1<=len(events)<=MAX_EVENTS:
        raise ValueError('Supply 1–20 explicit administration events (implementation limit).')
    canonical=[];previous=-1.0
    for index,event in enumerate(events):
        if not isinstance(event,dict) or set(event)!={'time','amount','origin','source_ref'}:
            raise ValueError(f'Event {index+1}: supply time, amount, origin and source_ref.')
        time=_quantity(event['time'],'h',f'Event {index+1} time',zero=True,maximum=MAX_HORIZON_H)
        amount=_quantity(event['amount'],'mg',f'Event {index+1} amount')
        if time['value']<=previous:raise ValueError('Event times must be strictly increasing; duplicates and automatic sorting are not supported.')
        if time['value']>horizon['value']:raise ValueError('An event is outside the requested horizon.')
        previous=time['value']
        event_source=_provenance(event['origin'],event['source_ref'],f'Event {index+1}')
        canonical.append({'time':time,'amount':amount,'origin':event['origin'],'source_ref':event_source})
    return {'schema_version':SCHEMA_VERSION,'purpose':'synthetic_educational',
        'drug':'lenalidomide','route':'oral','formulation':'capsule','origin':request['origin'],
        'source_ref':source,'horizon':horizon,'events':canonical}


def treatment_request_example():
    return {'schema_version':SCHEMA_VERSION,'purpose':'synthetic_educational','drug':'lenalidomide',
        'route':'oral','formulation':'capsule','origin':'synthetic_input',
        'source_ref':'Invented request example; not a prescribed or recommended regimen.',
        'horizon':{'value':72.0,'unit':'h'},
        'events':[{'time':{'value':float(t),'unit':'h'},'amount':{'value':5.0,'unit':'mg'},
            'origin':'synthetic_input','source_ref':'Invented administration event for schema demonstration.'}
            for t in (0,24,48)]}


def treatment_request_preview(request):
    canonical=validate_treatment_request(request)
    report={'schema_version':'treatment-request-preview-v1','validation_version':VALIDATION_VERSION,
        'status':'syntax_valid','request':canonical,'request_sha256':digest(canonical),
        'event_count':len(canonical['events']),
        'total_requested_amount_mg':math.fsum(e['amount']['value'] for e in canonical['events']),
        'time_basis':'Hours relative to the requested simulation-window start, not observed administration timestamps.',
        'simulation_status':'not_run','ready_for_patient_simulation':False,
        'limitation':'Request shape, units, finite values, ordering and bounds only. Amounts are requested synthetic events, not confirmed administrations. No marketed strength, label regimen, dose suitability, PK or clinical outcome is established.'}
    report['report_sha256']=digest(report)
    return report


def review_patient_treatment(revision_id,inputs,request):
    treatment=treatment_request_preview(request)
    base=review_model_binding(revision_id,inputs)
    report=copy.deepcopy(base)
    report.pop('report_sha256')
    report['schema_version']='patient-treatment-preview-v1';report['method_version']=PLAN_VERSION
    report['model_binding_preview_sha256']=base['report_sha256']
    report['treatment_request_preview']=treatment
    report['binding']['treatment_request_sha256']=treatment['request_sha256']
    report['binding_sha256']=digest(report['binding'])
    report['blockers']=[b for b in report['blockers'] if b['code']!='treatment_request_missing']
    if base['selected_drug']!=treatment['request']['drug']:
        report['blockers'].append({'code':'treatment_scenario_drug_mismatch',
            'message':'The explicit request differs from the saved scenario drug. No alternate model is used.'})
    report['blockers'].append({'code':'treatment_applicability_not_established',
        'message':'Recorded route, formulation, amount and timing have not been validated as a suitable model request or clinical regimen.'})
    report['limitation']='Read-only proposed patient/input/treatment association. No plan is saved, no scenario dose is imported, no administration is performed and no concentration simulation runs. Syntax validation does not establish model or clinical applicability.'
    report['report_sha256']=digest(report)
    return report


def _read_json(path):
    with path.open('rb') as handle:raw=handle.read(65537)
    if len(raw)>65536:raise ValueError('JSON file exceeds 64 KiB.')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=_no_duplicate_keys)


def _emit(report,json_output,output):
    if output:
        with output.open('x',encoding='utf-8') as handle:
            json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
        click.echo(f'Saved treatment preview export: {output}')
    elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
    else:
        click.echo(f"Synthetic treatment preview | {report['status']}")
        treatment=report.get('treatment_request_preview',report)
        click.echo(f"Requested events: {treatment['event_count']} | Total requested: {treatment['total_requested_amount_mg']:g} mg")
        click.echo('Simulation: not_run | Patient simulation ready: false')
        for b in report.get('blockers',[]):click.echo(f"[BLOCKED] {b['code']}: {b['message']}")
        click.echo(report['limitation'])


def register_treatment_request_commands(app):
    @app.cli.command('treatment-request')
    @click.option('--example',is_flag=True)
    @click.option('--request-file',type=click.Path(exists=True,dir_okay=False,path_type=Path))
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def request_command(example,request_file,json_output,output):
        """Validate explicit synthetic administrations without a patient or PK run."""
        if bool(example)==bool(request_file):raise click.ClickException('Choose exactly one of --example or --request-file.')
        try:_emit(treatment_request_preview(treatment_request_example() if example else _read_json(request_file)),json_output,output)
        except (ValueError,OSError,UnicodeError) as exc:raise click.ClickException(str(exc)) from exc

    @app.cli.command('patient-treatment-preview')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--inputs-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--treatment-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def patient_command(revision_id,inputs_file,treatment_file,json_output,output):
        """Review patient/input/treatment identity without writes or simulation."""
        try:_emit(review_patient_treatment(revision_id,_read_json(inputs_file),_read_json(treatment_file)),json_output,output)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
