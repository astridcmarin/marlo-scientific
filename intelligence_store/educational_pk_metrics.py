"""Clearly labeled grid-sampled peak summaries of mathematically audited archives."""
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .educational_pk_runs import read_pk_run
from .educational_pk_audit import audit_pk_run
from .patient_state import digest

METHOD='educational-pk-sampled-metrics-v1.0'
LIMITATION='Sampled educational exposure summaries over the recorded window. No exact continuous Cmax/Tmax, clinical prediction, uncertainty interval, efficacy, toxicity or dose suitability is established.'


def sampled_peak(points):
    """Pure sample statistics. No interpolation or continuous-peak estimation."""
    if len(points)<2:return None
    times=[p['time_h'] for p in points];concentrations=[p['concentration_ng_ml'] for p in points]
    if not all(type(x) in (int,float) and math.isfinite(x) for x in times+concentrations):return None
    steps=[b-a for a,b in zip(times,times[1:])]
    if not all(s>0 and math.isclose(s,steps[0],rel_tol=1e-10,abs_tol=1e-10) for s in steps):return None
    maximum=max(concentrations)
    peak_times=[t for t,c in zip(times,concentrations) if c==maximum]
    return {'concentration_ng_ml':maximum,'first_time_h':peak_times[0],
        'equal_maximum_times_h':peak_times,'tie_policy':'Exact equality; earliest archived sample is reported first.',
        'window_start_h':times[0],'window_end_h':times[-1],'sampling_step_h':steps[0],'sample_count':len(points),
        'maximum_on_window_boundary':any(t in (times[0],times[-1]) for t in peak_times),
        'time_basis':'Hours from the simulation-window start, not from each administration.',
        'scope':'Maximum among archived samples across the entire recorded window; not per-dose or steady-state Cmax.',
        'resolution_note':'Sampling interval describes grid resolution. It is not a timing confidence interval or a bound on continuous-peak error.'}


def summarize_pk_run(run_id):
    row=read_pk_run(run_id)
    if row is None:raise ValueError('Saved educational PK run does not exist.')
    r=row.payload['report'];audit=audit_pk_run(run_id)
    report={'schema_version':'educational-pk-sampled-metrics-v1','method_version':METHOD,'run_id':row.id,
        'revision_id':row.revision_id,'source_payload_sha256':row.payload_sha256,'source_report_sha256':row.report_sha256,
        'audit_method_version':audit['method_version'],'audit_report_sha256':audit['report_sha256'],
        'audit_status':audit['status'],'sampled_peak':None,'exposure':None,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'continuous_peak_estimated':False,'ode_solver_rerun':False,'limitation':LIMITATION}
    if audit['status']!='mathematical_checks_passed':
        report['status']='metrics_withheld'
        report['withheld_reason']='The archived run did not pass the supported mathematical audit.'
    else:
        peak=sampled_peak(r['points'])
        request=r['preflight_review']['treatment_request_preview']['request']
        if peak is None or peak['window_start_h']!=0 or peak['window_end_h']!=request['horizon']['value']:
            report['status']='metrics_withheld';report['withheld_reason']='The sampling grid must be uniform, increasing and cover the requested window.'
        else:
            report.update(status='sampled_metrics_available',sampled_peak=peak,
                exposure={'auc_0_window_ng_h_ml':r['auc_0_horizon_ng_h_ml'],
                    'analytic_auc_0_infinity_ng_h_ml':r['analytic_auc_0_infinity_ng_h_ml'],
                    'dose_normalized':False})
    report['report_sha256']=digest(report)
    return report


def register_educational_pk_metrics_commands(app):
    @app.cli.command('patient-pk-metrics')
    @click.option('--id','run_id',type=click.IntRange(min=1),required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(run_id,json_output,output):
        """Summarize archived sampled peaks without claiming continuous Cmax/Tmax."""
        try:
            report=summarize_pk_run(run_id)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported sampled educational metrics: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Run #{run_id} | {report['status']}")
                if report['sampled_peak']:
                    peak=report['sampled_peak']
                    click.echo(f"Sampled maximum concentration: {peak['concentration_ng_ml']:.6g} ng/mL")
                    click.echo(f"First sampled maximum time: {peak['first_time_h']:g} h from window start")
                    click.echo(f"Sampling interval: {peak['sampling_step_h']:g} h | Window: {peak['window_start_h']:g}–{peak['window_end_h']:g} h")
                else:click.echo(report['withheld_reason'])
                click.echo(LIMITATION)
            if report['status']!='sampled_metrics_available':raise click.exceptions.Exit(1)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
