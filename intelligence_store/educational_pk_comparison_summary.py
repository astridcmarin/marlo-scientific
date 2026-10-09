"""Audited archived exposure differences; no clinical response attribution."""
import copy
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .educational_pk_comparison import compare_pk_runs
from .educational_pk_metrics import summarize_pk_run
from .patient_state import digest

METHOD = 'educational-pk-comparison-summary-v1.0'
LIMITATION = ('Arithmetic between compatible audited educational archives, right minus left. '
              'Sampled peaks are not exact continuous Cmax/Tmax. Differences are not renal impairment '
              'diagnoses, clinical effects, uncertainty intervals, dose recommendations or observed patient responses.')


def _treatment_values(request):
    return {'drug':request['drug'],'route':request['route'],'formulation':request['formulation'],
            'horizon':request['horizon'],
            'events':[{'time':e['time'],'amount':e['amount']} for e in request['events']]}


def _delta(code,label,unit,left,right,percent=True):
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (left,right)):
        raise ValueError('Archived metric is not a finite number.')
    return {'code':code,'label':label,'unit':unit,'left':left,'right':right,
            'right_minus_left':right-left,
            'percent_relative_to_left':100*(right-left)/left if percent and left!=0 else None,
            'right_to_left_ratio':right/left if percent and left!=0 else None}


def comparison_summary(left_id,right_id,*,revision_id):
    comparison = compare_pk_runs(left_id,right_id,revision_id=revision_id)
    changed = [row['field'] for row in comparison['covariate_changes'] if row['value_changed']]
    metadata_changed = [row['field'] for row in comparison['covariate_changes'] if row['metadata_changed']]
    treatment_changed = _treatment_values(comparison['left']['request']) != _treatment_values(comparison['right']['request'])
    if treatment_changed: context = 'treatment_values_changed_do_not_isolate_covariate_effect'
    elif len(changed)>1: context = 'multiple_covariate_values_changed'
    elif len(changed)==1: context = 'single_declared_covariate_value_changed'
    else: context = 'no_declared_numeric_input_change'
    report = {'schema_version':'educational-pk-comparison-summary-v1','method_version':METHOD,
        'revision_id':revision_id,'left_run_id':left_id,'right_run_id':right_id,
        'source_comparison_sha256':comparison['report_sha256'],
        'left_source':copy.deepcopy(comparison['left']),'right_source':copy.deepcopy(comparison['right']),
        'compatibility_checks':copy.deepcopy(comparison['compatibility_checks']),
        'covariate_changes':copy.deepcopy(comparison['covariate_changes']),
        'comparison_context':{'status':context,'changed_covariate_values':changed,
            'changed_covariate_metadata':metadata_changed,'treatment_values_changed':treatment_changed,
            'full_treatment_request_changed':comparison['treatment_request_changed'],
            'meaning':'Describes declared archived inputs only; it does not establish verified biological change or clinical causality.'},
        'status':'comparison_summary_withheld','metrics':None,'sampled_peak_context':None,
        'audited_metrics':None,'withheld_reasons':[],
        'difference_direction':'right minus left','dose_normalized':False,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'ode_solver_rerun':False,'database_writes_performed':False,'network_refresh_performed':False,
        'limitation':LIMITATION}
    if comparison['status']!='compatible_educational_comparison':
        report['withheld_reasons']=[c['code'] for c in comparison['compatibility_checks'] if not c['matches']]
    else:
        a=summarize_pk_run(left_id);b=summarize_pk_run(right_id)
        report['audited_metrics']={'left':a,'right':b}
        if any(r['status']!='sampled_metrics_available' for r in (a,b)):
            report['withheld_reasons']=['both_archives_require_a_passed_mathematical_audit_and_supported_sampling_grid']
        else:
            metrics=[]
            for code,label,unit in (
                ('apparent_clearance_l_h','Apparent clearance CL/F','L/h'),
                ('apparent_volume_l','Apparent volume V/F','L'),
                ('elimination_rate_h','Elimination rate','1/h'),
                ('transit_rate_h','Common transit rate','1/h')):
                metrics.append(_delta(code,label,unit,comparison['left']['parameters'][code],comparison['right']['parameters'][code]))
            metrics.append(_delta('auc_recorded_window','AUC over the common recorded window','ng·h/mL',a['exposure']['auc_0_window_ng_h_ml'],b['exposure']['auc_0_window_ng_h_ml']))
            metrics.append(_delta('sampled_maximum','Maximum among archived concentration samples','ng/mL',a['sampled_peak']['concentration_ng_ml'],b['sampled_peak']['concentration_ng_ml']))
            metrics.append(_delta('first_sampled_maximum_time','First sampled maximum time from window start','h',a['sampled_peak']['first_time_h'],b['sampled_peak']['first_time_h'],False))
            report.update(status='educational_comparison_summary_available',metrics=metrics,
                sampled_peak_context={'left':copy.deepcopy(a['sampled_peak']),'right':copy.deepcopy(b['sampled_peak']),
                 'note':'Earliest equal maximum across the entire sampled window; not a per-dose or steady-state peak. Boundary flags and tied sample times remain visible.'})
    report['report_sha256']=digest(report)
    return report


def register_educational_pk_comparison_summary_commands(app):
    @app.cli.command('patient-pk-comparison-summary')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--left',type=click.IntRange(min=1),required=True)
    @click.option('--right',type=click.IntRange(min=1),required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    @click.option('--html-output',type=click.Path(dir_okay=False,path_type=Path))
    def command(revision_id,left,right,json_output,output,html_output):
        """Show input context and audited exposure differences for two stored runs."""
        if sum((bool(output),bool(html_output),bool(json_output)))>1:
            raise click.ClickException("Choose only one of --output, --html-output or --json.")
        try:
            report=comparison_summary(left,right,revision_id=revision_id)
            if html_output:
                from .educational_pk_comparison_html import render_comparison_html
                html=render_comparison_html(report)
                with html_output.open("x",encoding="utf-8") as handle:handle.write(html)
                click.echo(f"Exported visual educational comparison: {html_output}")
            elif output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported educational comparison summary: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Educational comparison | {report['status']} | Right minus left")
                click.echo(f"Input context: {report['comparison_context']['status']}")
                for metric in report['metrics'] or []:
                    click.echo(f"{metric['label']}: {metric['left']:.6g} → {metric['right']:.6g} {metric['unit']} | difference {metric['right_minus_left']:.6g}")
                if report['withheld_reasons']:click.echo('Withheld: '+', '.join(report['withheld_reasons']))
                click.echo(LIMITATION)
            if report['status']=='comparison_summary_withheld':raise click.exceptions.Exit(1)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
