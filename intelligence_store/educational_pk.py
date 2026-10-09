"""Bounded deterministic PK under declared synthetic inputs; no clinical prediction."""
import copy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .patient_state import digest
from .model_coverage import review_model_coverage,CONTRACT_SHA256 as COVERAGE_SHA
from .published_transit_reference import load_structure_contract,CONTRACT_SHA256 as STRUCTURE_SHA
from .transit_kernel import solve_transit,METHOD_VERSION as SOLVER_VERSION
from .treatment_requests import _read_json

METHOD_VERSION='hughes-educational-pk-v1.0'
CONTRACT_PATH=Path(__file__).parent/'data'/'hughes_execution_contract_v1.json'
CONTRACT_SHA256='59670d7f0328a395cd2a04f7076d27287340a3a860ff38ea43a84e9dc088a682'


def load_execution_contract(path=CONTRACT_PATH):
    try:
        raw=Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=CONTRACT_SHA256:raise ValueError('Changed execution contract')
        data=json.loads(raw)
        if data['structure_contract_sha256']!=STRUCTURE_SHA or data['coverage_contract_sha256']!=COVERAGE_SHA:
            raise ValueError('Incompatible source contracts')
        return data
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise ValueError('Educational execution contract is missing or changed; no calculation was generated.') from exc


def _grid_index(value):
    scaled=Decimal(str(value))*10
    if scaled!=scaled.to_integral_value():raise ValueError('Time is not on the supported 0.1-hour grid.')
    return int(scaled)


def calculate_educational_pk(revision_id,inputs,request,disease_code='UNKNOWN'):
    policy=load_execution_contract();structure=load_structure_contract()
    coverage=review_model_coverage(revision_id,inputs,request,disease_code)
    canonical=coverage['treatment_request_preview']['request'];events=canonical['events']
    horizon=canonical['horizon']['value'];blockers=[]
    def block(code,message):blockers.append({'code':code,'message':message})
    if coverage['status'] in ('unsupported_drug','binding_conflict'):
        block(coverage['status'],'Source association has an unsupported drug or input conflict.')
    if coverage['outside_reported_ranges']:
        block('outside_context_range','Known state/covariate context is outside reported ranges.')
    if any(c['field'] in policy['required_known_context'] for c in coverage['coverage_checks'] if c['status']=='unknown'):
        block('age_context_missing','Recorded age is required for this educational execution scope.')
    if coverage['declared_disease_context']['status']!='represented_group':
        block('disease_context_missing_or_unrepresented','Declare a represented synthetic disease context explicitly.')
    preview=coverage['standalone_input_preview']
    if preview is None or preview['parameter_preview'] is None:
        block('parameters_unavailable','Explicit covariates did not produce a bounded parameter preview.')
    if any(e['status']!='listed_study_amount' for e in coverage['treatment_amount_checks']):
        block('amount_outside_execution_scope','This first calculation accepts individually listed source amounts only.')
    if horizon>policy['maximum_horizon_h'] or len(events)>policy['maximum_events']:
        block('execution_budget','This calculation supports at most 72 hours and four events.')
    if events[0]['time']['value']!=policy['first_event_time_h']:
        block('initial_event_time','This first execution requires an event at time zero.')
    if any(b['time']['value']-a['time']['value']!=policy['required_interval_h'] for a,b in zip(events,events[1:])):
        block('interval_outside_execution_scope','This first execution accepts exactly 24-hour intervals.')
    try:
        horizon_index=_grid_index(horizon)
        indices=[_grid_index(e['time']['value']) for e in events]
    except ValueError:
        block('unsupported_time_grid','Use an explicit 0.1-hour grid for horizon and event times.')
        horizon_index=None;indices=[]
    report={'schema_version':'educational-pk-calculation-v1','method_version':METHOD_VERSION,
        'calculation_scope':policy['scope'],'clinical_prediction_validated':False,
        'ready_for_patient_simulation':False,'patient_context_role':'Immutable provenance and consistency context, not verified clinical covariates.',
        'execution_contract_version':policy['contract_version'],'execution_contract_sha256':CONTRACT_SHA256,
        'preflight_review':coverage,'preflight_report_sha256':coverage['report_sha256'],
        'clinical_review_blockers':copy.deepcopy(coverage['blockers']),
        'execution_blockers':blockers,'parameters':None,'points':None,'event_boundaries':None,
        'limitations':['Declared synthetic covariates are not independently verified patient physiology.',
            'Unknown contextual values remain unknown and do not affect the parameter equations.',
            'No uncertainty distribution, observed-data fit, organ physiology, PD, efficacy or toxicity is calculated.',
            'Requested administrations are not confirmed administrations or clinical dose recommendations.']}
    if blockers:
        report['status']='blocked_educational_calculation';report['simulation_status']='not_run'
    else:
        p=preview['parameter_preview']
        basis=solve_transit(dose_mg=1.0,volume_l=p['apparent_volume_l'],clearance_l_h=p['apparent_clearance_l_h'],
            transit_rate_h=p['transit_rate_h'],stages=structure['structure']['precentral_stage_count'],
            horizon_h=horizon,display_step_h=policy['display_step_h'],max_step_h=policy['max_step_h'])
        series=basis['points']
        if len(series)!=horizon_index+1:raise ValueError('Reference series does not match the execution grid.')
        event_inputs=[(index,event['amount']['value']) for index,event in zip(indices,events)]
        def state(index,before_event=False):
            active=[(i,amount) for i,amount in event_inputs if i<index or (i==index and not before_event)]
            terms=[(series[index-i],amount) for i,amount in active]
            stages=[math.fsum(a*s['transit_amounts_mg'][j] for s,a in terms) for j in range(8)]
            return {'time_h':series[index]['time_h'],'precentral_amounts_mg':stages,
                'central_amount_mg':math.fsum(a*s['central_amount_mg'] for s,a in terms),
                'eliminated_amount_mg':math.fsum(a*s['eliminated_amount_mg'] for s,a in terms),
                'concentration_ng_ml':math.fsum(a*s['concentration_ng_ml'] for s,a in terms),
                'auc_0_t_ng_h_ml':math.fsum(a*s['auc_0_t_ng_h_ml'] for s,a in terms),
                'cumulative_requested_amount_mg':math.fsum(a for i,a in active)}
        points=[state(i) for i in range(len(series))]
        boundaries=[{'time_h':e['time']['value'],'amount_mg':e['amount']['value'],
                     'before':state(i,True),'after':state(i)} for i,e in zip(indices,events)]
        total=math.fsum(e['amount']['value'] for e in events)
        error=max(abs(math.fsum(s['precentral_amounts_mg']+[s['central_amount_mg'],s['eliminated_amount_mg']])-
                      s['cumulative_requested_amount_mg']) for s in points)
        if error>1e-9*total:raise ValueError('Educational calculation amount balance failed.')
        report.update(status='completed_educational_calculation',simulation_status='completed_educational_calculation',
            parameters=copy.deepcopy(p),points=points,event_boundaries=boundaries,
            point_amount_order=copy.deepcopy(structure['structure']['serial_precentral_order']),
            solver=copy.deepcopy(basis['solver']),solver_method_version=SOLVER_VERSION,
            unit_response_sha256=basis['report_sha256'],
            combination_method='Linear superposition of shifted unit responses; constant parameters and zero random effects.',
            amount_balance={'display_point_max_error_mg':error,'tolerance_mg':1e-9*total,
                            'unit_basis_internal_max_error_mg':basis['amount_balance']['max_absolute_error_mg']},
            total_requested_amount_mg=total,auc_0_horizon_ng_h_ml=points[-1]['auc_0_t_ng_h_ml'],
            analytic_auc_0_infinity_ng_h_ml=1000*total/p['apparent_clearance_l_h'],
            assumption='Zero initial amounts before the time-zero request; no prior exposure or concomitant-treatment effect.')
    report['report_sha256']=digest(report)
    return report


def register_educational_pk_commands(app):
    @app.cli.command('patient-pk-educational')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--inputs-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--treatment-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--disease-code',type=click.Choice(('MM','CLL','AML','ALL','OTHER','UNKNOWN')),default='UNKNOWN')
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(revision_id,inputs_file,treatment_file,disease_code,json_output,output):
        """Run bounded declared-input mathematics; never a clinical prediction."""
        try:
            report=calculate_educational_pk(revision_id,_read_json(inputs_file),_read_json(treatment_file),disease_code)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved educational PK calculation: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Educational PK | {report['status']} | Clinical prediction validated: false")
                for b in report['execution_blockers']:click.echo(f"[BLOCKED] {b['code']}: {b['message']}")
                if report['points'] is not None:
                    click.echo(f"Time points: {len(report['points'])} | Precentral stages: 8")
                    click.echo(f"AUC over requested horizon: {report['auc_0_horizon_ng_h_ml']:.6g} ng·h/mL")
                    click.echo(f"Display-point amount-balance error: {report['amount_balance']['display_point_max_error_mg']:.3g} mg")
                click.echo(f"Retained source-review status: {report['preflight_review']['status']}")
                click.echo('Declared synthetic inputs only. No efficacy, toxicity or dose recommendation.')
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
