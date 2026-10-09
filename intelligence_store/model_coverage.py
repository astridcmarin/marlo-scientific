"""Source coverage context for a proposed synthetic run; no clinical suitability decision."""
import copy
import hashlib
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .patient_state import digest
from .treatment_requests import review_patient_treatment,_read_json

METHOD_VERSION='hughes-source-coverage-review-v1.0'
CONTRACT_PATH=Path(__file__).parent/'data'/'hughes_coverage_contract_v1.json'
CONTRACT_SHA256='b452b4f21d4449ef88fc7821481376c08b16ad8fcd1b90a6664bba7408857fe6'
DISEASE_CODES=('MM','CLL','AML','ALL','OTHER','UNKNOWN')


def load_coverage_contract(path=CONTRACT_PATH):
    try:
        raw=Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=CONTRACT_SHA256:raise ValueError('Changed contract')
        data=json.loads(raw)
        if data['schema_version']!='hughes-coverage-contract-v1':raise ValueError('Wrong schema')
        return data
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise ValueError('Source coverage contract is missing or changed; no review was generated.') from exc


def _range_row(name,field,spec,role):
    value=field['value'];lo,hi=spec['range']
    if field['unit']!=spec['unit']:raise ValueError(f'{name}: source coverage units differ; no conversion is performed.')
    return {'field':name,'role':role,'input':copy.deepcopy(field),'source_range':[lo,hi],
        'status':'unknown' if value is None else ('within_reported_range' if lo<=value<=hi else 'outside_reported_range')}


def review_model_coverage(revision_id,inputs,request,disease_code='UNKNOWN'):
    if disease_code not in DISEASE_CODES:raise ValueError('Unsupported disease context code.')
    contract=load_coverage_contract()
    base=review_patient_treatment(revision_id,inputs,request)
    rows=[_range_row(name,base['captured_state']['fields'][name],spec,'saved_state_context')
          for name,spec in contract['state_ranges'].items()]
    rows += [_range_row(name,base['explicit_model_inputs']['fields'][name],spec,'explicit_model_covariate')
             for name,spec in contract['covariate_ranges'].items()]
    amounts=[]
    for index,event in enumerate(base['treatment_request_preview']['request']['events']):
        value=event['amount']['value'];lo,hi=contract['amount_range_mg']
        listed=any(math.isclose(value,x,rel_tol=0,abs_tol=1e-12) for x in contract['listed_amounts_mg'])
        amounts.append({'event_index':index+1,'time_h':event['time']['value'],'amount_mg':value,
            'status':'outside_reported_amount_range' if not lo<=value<=hi else
                     ('listed_study_amount' if listed else 'within_range_but_not_listed_amount')})
    disease_status='unknown' if disease_code=='UNKNOWN' else ('represented_group' if disease_code in contract['disease_counts'] else 'not_a_reported_group')
    unknown=[r['field'] for r in rows if r['status']=='unknown']
    outside=[r['field'] for r in rows if r['status']=='outside_reported_range']
    if base['status'] in ('unsupported_drug','binding_conflict'):status=base['status']
    elif outside or any(a['status']=='outside_reported_amount_range' for a in amounts) or disease_status=='not_a_reported_group':status='source_extrapolation_flagged'
    elif unknown or disease_status=='unknown' or any(a['status']=='within_range_but_not_listed_amount' for a in amounts):status='source_coverage_gaps'
    else:status='coverage_review_only'
    report=copy.deepcopy(base);report.pop('report_sha256')
    report['schema_version']='model-source-coverage-review-v1';report['method_version']=METHOD_VERSION
    report['patient_treatment_preview_sha256']=base['report_sha256']
    report['status']=status
    report['coverage_contract_version']=contract['contract_version'];report['coverage_contract_sha256']=CONTRACT_SHA256
    report['coverage_source']=copy.deepcopy(contract['source'])
    report['source_subject_count']=contract['study_subject_count']
    report['declared_disease_context']={'code':disease_code,'status':disease_status,
        'origin':'explicit_synthetic_declaration' if disease_code!='UNKNOWN' else 'unknown',
        'source_group_subject_count':contract['disease_counts'].get(disease_code),
        'verification':'Not inferred from cohort condition, scenario indication or a verified diagnosis.'}
    report['coverage_checks']=rows;report['treatment_amount_checks']=amounts
    report['unknown_context_fields']=unknown;report['outside_reported_ranges']=outside
    report['listed_study_amounts_mg']=copy.deepcopy(contract['listed_amounts_mg'])
    report['binding']['coverage_contract_sha256']=CONTRACT_SHA256
    report['binding']['declared_disease_code']=disease_code
    report['binding_sha256']=digest(report['binding'])
    report['coverage_limits']=copy.deepcopy(contract['inference_limits'])
    report['blockers'].append({'code':'joint_and_regimen_coverage_not_established',
        'message':'Separate range and listed-amount checks do not verify their combination, treatment schedule or clinical suitability.'})
    if outside or unknown or disease_status!='represented_group' or any(a['status']!='listed_study_amount' for a in amounts):
        report['blockers'].append({'code':'source_coverage_uncertain','message':'Unknown context or extrapolation flags remain. All inputs are preserved without substitution.'})
    report['limitation']='Source coverage review only. A range match is not clinical validation or an applicability approval. Unknown values are not filled, declarations are not authenticated, and no simulation or database write occurs.'
    report['report_sha256']=digest(report)
    return report


def register_model_coverage_commands(app):
    @app.cli.command('patient-model-coverage')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--inputs-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--treatment-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--disease-code',type=click.Choice(DISEASE_CODES),default='UNKNOWN',show_default=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(revision_id,inputs_file,treatment_file,disease_code,json_output,output):
        """Review documented source coverage without approving or running simulation."""
        try:
            report=review_model_coverage(revision_id,_read_json(inputs_file),_read_json(treatment_file),disease_code)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved source coverage review: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Patient-state record #{revision_id} | Source coverage: {report['status']}")
                context=report['declared_disease_context']
                click.echo(f"Declared disease: {context['code']} | {context['status']} | Source group count: {context['source_group_subject_count']}")
                for row in report['coverage_checks']:click.echo(f"{row['field']}: {row['input']['value']} {row['input']['unit']} | {row['status']}")
                for row in report['treatment_amount_checks']:click.echo(f"Event {row['event_index']}: {row['amount_mg']:g} mg | {row['status']}")
                click.echo('Simulation: not_run | Patient simulation ready: false')
                click.echo(report['limitation'])
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
