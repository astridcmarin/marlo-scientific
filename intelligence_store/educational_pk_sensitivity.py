"""Declared one-parameter mathematical sensitivity, separate from published PK."""
import copy
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .educational_pk_runs import read_pk_run
from .educational_pk_audit import audit_pk_run, analytic_state
from .educational_pk_metrics import sampled_peak
from .patient_state import digest

METHOD='educational-pk-clearance-sensitivity-v1.0'
LIMITATION='Invented clearance perturbation with other parameters fixed. Not a published patient model variant, confidence interval, population distribution, renal-function adjustment, efficacy/toxicity prediction or dose recommendation.'


def clearance_sensitivity(run_id,clearance_factor,assumption_note):
    if type(clearance_factor) not in (int,float) or not 0.5<=clearance_factor<=2 or not math.isfinite(clearance_factor):
        raise ValueError('Declare a finite clearance factor from 0.5 to 2.0 (software demonstration bounds, not clinical limits).')
    if not isinstance(assumption_note,str) or not 1<=len(assumption_note.strip())<=1000:
        raise ValueError('Supply an assumption note of 1–1000 characters describing the invented perturbation.')
    factor=float(clearance_factor);note=assumption_note.strip()
    row=read_pk_run(run_id)
    if row is None:raise ValueError('Saved educational PK run does not exist.')
    r=row.payload['report'];audit=audit_pk_run(run_id)
    request=r['preflight_review']['treatment_request_preview']['request']
    report={'schema_version':'educational-pk-clearance-sensitivity-v1','method_version':METHOD,
        'source_run_id':row.id,'source_revision_id':row.revision_id,
        'source_payload_sha256':row.payload_sha256,'source_report_sha256':row.report_sha256,
        'source_model_method_version':r['method_version'],'source_execution_contract_sha256':r['execution_contract_sha256'],
        'source_audit_method_version':audit['method_version'],'source_audit_report_sha256':audit['report_sha256'],
        'source_audit_status':audit['status'],'source_binding':copy.deepcopy(r['preflight_review']['binding']),
        'assumption':{'origin':'assumption','source_ref':note,'clearance_factor':factor,
            'factor_bounds':[0.5,2.0],'bounds_basis':'Software demonstration limits; not source coverage or physiological limits.'},
        'request':copy.deepcopy(request),'parameters':None,'points':None,'summaries':None,
        'status':'sensitivity_withheld','clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'uncertainty_interval_estimated':False,'population_variability_sampled':False,
        'patient_covariates_changed':False,'ode_solver_rerun':False,'analytic_reference_evaluated':False,
        'limitation':LIMITATION,
        'fixed_assumptions':['V/F and transit rate remain fixed at archived values.',
            'The administration request and archived sampling grid remain fixed.',
            'Only CL/F is multiplied. No covariate equation is re-evaluated or inferred.',
            'Each perturbation is a mathematical scenario, not a plausible individual or a confidence bound.']}
    grid=sampled_peak(r['points'])
    if audit['status']!='mathematical_checks_passed':
        report['withheld_reason']='The source archive did not pass the supported mathematical audit.'
    elif grid is None or grid['window_start_h']!=0 or grid['window_end_h']!=request['horizon']['value'] or len(r['points'])>2001:
        report['withheld_reason']='The source grid must be uniform, increasing, cover the requested window and contain at most 2001 samples.'
    else:
        original=copy.deepcopy(r['parameters']);changed=copy.deepcopy(original)
        changed['apparent_clearance_l_h']*=factor
        changed['elimination_rate_h']=changed['apparent_clearance_l_h']/changed['apparent_volume_l']
        cl=original['apparent_clearance_l_h'];volume=original['apparent_volume_l'];ktr=original['transit_rate_h']
        if changed['apparent_clearance_l_h']/volume>ktr:
            report['withheld_reason']='The perturbed rate is outside this analytic implementation.'
        else:
            baseline=[];variation=[];points=[]
            for point in r['points']:
                t=point['time_h']
                b=analytic_state(t,request['events'],cl,volume,ktr)
                v=analytic_state(t,request['events'],cl*factor,volume,ktr)
                baseline.append({'time_h':t,**b});variation.append({'time_h':t,**v})
                points.append({'time_h':t,'archived_concentration_ng_ml':point['concentration_ng_ml'],
                    'analytic_baseline_concentration_ng_ml':b['concentration_ng_ml'],
                    'perturbed_concentration_ng_ml':v['concentration_ng_ml'],
                    'analytic_baseline_auc_0_t_ng_h_ml':b['auc_0_t_ng_h_ml'],
                    'perturbed_auc_0_t_ng_h_ml':v['auc_0_t_ng_h_ml']})
            if not all(math.isfinite(value) for p in points for value in p.values()):
                raise ValueError('The sensitivity calculation produced a non-finite value.')
            total=math.fsum(e['amount']['value'] for e in request['events'])
            def summary(states,clearance):
                peak=sampled_peak(states)
                peak['scope']='Maximum among analytically evaluated samples on the source grid; not per-dose, steady-state or exact continuous Cmax.'
                peak['tie_policy']='Exact equality; earliest evaluated sample is reported first.'
                return {'auc_0_window_ng_h_ml':states[-1]['auc_0_t_ng_h_ml'],
                    'analytic_auc_0_infinity_ng_h_ml':1000*total/clearance,
                    'sampled_peak':peak}
            b=summary(baseline,cl);v=summary(variation,cl*factor)
            report.update(status='sensitivity_available',parameters={'archived':original,'perturbed':changed},
                points=points,analytic_reference_evaluated=True,
                summaries={'analytic_baseline':b,'perturbed':v,
                    'archived_auc_0_window_ng_h_ml':r['auc_0_horizon_ng_h_ml'],
                    'window_auc_ratio':v['auc_0_window_ng_h_ml']/b['auc_0_window_ng_h_ml'] if b['auc_0_window_ng_h_ml']>0 else None,
                    'infinity_auc_ratio':v['analytic_auc_0_infinity_ng_h_ml']/b['analytic_auc_0_infinity_ng_h_ml'],
                    'comparison_basis':'Analytic baseline and perturbed curves evaluated on the same archived grid; original archived values are retained separately.'})
    report['report_sha256']=digest(report)
    return report


def register_educational_pk_sensitivity_commands(app):
    @app.cli.command('patient-pk-sensitivity')
    @click.option('--id','run_id',type=click.IntRange(min=1),required=True)
    @click.option('--clearance-factor',type=float,required=True)
    @click.option('--assumption-note',required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(run_id,clearance_factor,assumption_note,json_output,output):
        """Explore a declared CL/F perturbation without changing a saved run."""
        try:
            report=clearance_sensitivity(run_id,clearance_factor,assumption_note)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported declared sensitivity: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Run #{run_id} | {report['status']} | Invented CL/F factor: {clearance_factor:g}")
                if report['summaries']:
                    s=report['summaries']
                    click.echo(f"Analytic baseline window AUC: {s['analytic_baseline']['auc_0_window_ng_h_ml']:.6g} ng·h/mL")
                    click.echo(f"Perturbed window AUC: {s['perturbed']['auc_0_window_ng_h_ml']:.6g} ng·h/mL")
                    click.echo(f"AUC-to-infinity ratio (perturbed / baseline): {s['infinity_auc_ratio']:.6g}")
                else:click.echo(report['withheld_reason'])
                click.echo(LIMITATION)
            if report['status']!='sensitivity_available':raise click.exceptions.Exit(1)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
