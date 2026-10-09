"""Read-only arithmetic comparisons of verified archived educational runs."""
import copy
import json
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .educational_pk_runs import read_pk_run
from .patient_state_revisions import _positive_id
from .patient_state import digest

METHOD='educational-pk-comparison-v1.0'
LIMITATION='Archived educational exposure arithmetic only. Differences are not clinical benefit, toxicity, suitability or a dose recommendation. No model is rerun; comparisons are not dose-normalized.'


def compare_pk_runs(left_id,right_id,*,revision_id):
    _positive_id(revision_id,'Revision ID')
    left=read_pk_run(left_id);right=read_pk_run(right_id)
    if left is None or right is None:raise ValueError('Both saved educational runs must exist.')
    if left.revision_id!=revision_id or right.revision_id!=revision_id:
        raise ValueError('Both runs must belong to the requested patient-state record.')
    return _compare_verified_runs(left,right,revision_id=revision_id)


def _compare_verified_runs(left,right,*,revision_id):
    """Shared arithmetic after each caller has verified archive ownership."""
    a=left.payload['report'];b=right.payload['report'];ra=a['preflight_review'];rb=b['preflight_review']
    checks=[]
    def check(code,x,y):checks.append({'code':code,'matches':x==y})
    for key in ('schema_version','method_version','execution_contract_sha256','solver_method_version','point_amount_order','assumption','combination_method'):
        check(key,a[key],b[key])
    for key in ('structure_contract_sha256','input_contract_sha256','coverage_contract_sha256','declared_disease_code'):
        check(key,ra['binding'][key],rb['binding'][key])
    check('parameter_extract_sha256',ra['standalone_input_preview']['parameter_extract_sha256'],rb['standalone_input_preview']['parameter_extract_sha256'])
    check('solver_settings',{k:a['solver'][k] for k in ('method','requested_max_step_h','effective_max_step_h','rate_step_bound','error_control')},
                            {k:b['solver'][k] for k in ('method','requested_max_step_h','effective_max_step_h','rate_step_bound','error_control')})
    check('time_grid',[p['time_h'] for p in a['points']],[p['time_h'] for p in b['points']])
    compatible=all(c['matches'] for c in checks)
    def captured(row,report,review):
        return {'run_id':row.id,'title':row.title,'payload_sha256':row.payload_sha256,'report_sha256':row.report_sha256,
                'inputs':copy.deepcopy(review['explicit_model_inputs']),
                'request':copy.deepcopy(review['treatment_request_preview']['request']),
                'declared_disease':copy.deepcopy(review['declared_disease_context']),
                'parameters':copy.deepcopy(report['parameters']),
                'horizon_h':report['points'][-1]['time_h'],
                'total_requested_amount_mg':report['total_requested_amount_mg'],
                'auc_0_horizon_ng_h_ml':report['auc_0_horizon_ng_h_ml'],
                'clinical_review_blockers':copy.deepcopy(report['clinical_review_blockers'])}
    covariates=[]
    for field in ('fat_free_mass','creatinine_clearance'):
        x=ra['explicit_model_inputs']['fields'][field];y=rb['explicit_model_inputs']['fields'][field]
        covariates.append({'field':field,'left':copy.deepcopy(x),'right':copy.deepcopy(y),
            'value_changed':x['value']!=y['value'] or x['unit']!=y['unit'],
            'metadata_changed':{k:v for k,v in x.items() if k not in ('value','unit')}!={k:v for k,v in y.items() if k not in ('value','unit')}})
    report={'schema_version':'educational-pk-comparison-v1','method_version':METHOD,
        'revision_id':revision_id,'left':captured(left,a,ra),'right':captured(right,b,rb),
        'status':'compatible_educational_comparison' if compatible else 'comparison_withheld',
        'compatibility_checks':checks,'covariate_changes':covariates,
        'treatment_request_changed':ra['treatment_request_preview']['request']!=rb['treatment_request_preview']['request'],
        'points':None,'exposure_difference':None,'clinical_prediction_validated':False,
        'ready_for_patient_simulation':False,'model_rerun':False,'difference_direction':'right minus left',
        'limitation':LIMITATION}
    if compatible:
        report['points']=[{'time_h':x['time_h'],'left_concentration_ng_ml':x['concentration_ng_ml'],
            'right_concentration_ng_ml':y['concentration_ng_ml'],
            'difference_ng_ml':y['concentration_ng_ml']-x['concentration_ng_ml']} for x,y in zip(a['points'],b['points'])]
        av=a['auc_0_horizon_ng_h_ml'];bv=b['auc_0_horizon_ng_h_ml']
        report['exposure_difference']={'auc_right_minus_left_ng_h_ml':bv-av,
            'auc_percent_relative_to_left':100*(bv-av)/av if av>0 else None,
            'window_h':a['points'][-1]['time_h'],'dose_normalized':False}
    report['report_sha256']=digest(report)
    return report


def register_educational_pk_comparison_commands(app):
    @app.cli.command('patient-pk-compare')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--left',type=click.IntRange(min=1),required=True)
    @click.option('--right',type=click.IntRange(min=1),required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(revision_id,left,right,json_output,output):
        """Compare frozen educational exposure reports without rerunning either model."""
        try:
            report=compare_pk_runs(left,right,revision_id=revision_id)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported educational comparison: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Educational PK comparison | {report['status']} | Right minus left")
                for c in report['compatibility_checks']:
                    if not c['matches']:click.echo(f"[WITHHELD] {c['code']} differs")
                if report['exposure_difference']:
                    click.echo(f"AUC difference: {report['exposure_difference']['auc_right_minus_left_ng_h_ml']:.6g} ng·h/mL")
                click.echo(LIMITATION)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
