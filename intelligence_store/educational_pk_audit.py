"""Independent analytic checks of archived eight-stage educational mathematics."""
import copy
import json
import math
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .educational_pk_runs import read_pk_run
from .patient_state import digest

METHOD='educational-pk-audit-v1.0'
LIMITATION='Mathematical verification of an archived synthetic calculation only. No observed-data fit, verified patient covariates, clinical prediction validity or uncertainty coverage is established.'


def _tail8(x):
    # Positive Poisson-tail series avoids cancellation at short times.
    if x<10:
        term=x**8/math.factorial(8);total=term
        for j in range(9,200):
            term*=x/j;total+=term
            if term<1e-17*total:break
        return math.exp(-x)*total
    return 1-math.exp(-x)*math.fsum(x**j/math.factorial(j) for j in range(8))


def analytic_state(time_h,events,cl,volume,ktr,*,before_event=False):
    """Closed-form serial Erlang absorption plus one-compartment elimination."""
    ke=cl/volume
    if not all(math.isfinite(v) and v>0 for v in (cl,volume,ktr)) or ke>ktr:
        raise ValueError('Analytic audit supports positive rates with elimination no faster than transit.')
    parts=[]
    for event in events:
        age=time_h-event['time']['value'];dose=event['amount']['value']
        if age<0 or (age==0 and before_event):continue
        z=ktr*age
        stages=[dose*math.exp(-z)*z**j/math.factorial(j) for j in range(8)]
        if age==0:central=0.0
        elif ke==ktr:central=dose*math.exp(-z)*z**8/math.factorial(8)
        else:central=dose*(ktr/(ktr-ke))**8*math.exp(-ke*age)*_tail8((ktr-ke)*age)
        eliminated=math.fsum([dose,-math.fsum(stages),-central])
        parts.append((stages,central,eliminated,dose))
    stages=[math.fsum(p[0][j] for p in parts) for j in range(8)]
    central=math.fsum(p[1] for p in parts);eliminated=math.fsum(p[2] for p in parts)
    return {'precentral_amounts_mg':stages,'central_amount_mg':central,'eliminated_amount_mg':eliminated,
            'concentration_ng_ml':1000*central/volume,'auc_0_t_ng_h_ml':1000*eliminated/cl,
            'cumulative_requested_amount_mg':math.fsum(p[3] for p in parts)}


def audit_pk_run(run_id):
    row=read_pk_run(run_id)
    if row is None:raise ValueError('Saved educational PK run does not exist.')
    r=row.payload['report'];review=r['preflight_review'];p=r['parameters']
    report={'schema_version':'educational-pk-audit-v1','method_version':METHOD,'run_id':row.id,
        'revision_id':row.revision_id,'source_payload_sha256':row.payload_sha256,'source_report_sha256':row.report_sha256,
        'model_method_version':r['method_version'],'execution_contract_sha256':r['execution_contract_sha256'],
        'source_binding':copy.deepcopy(review['binding']),
        'checks':[{'code':'frozen_payload_and_source_integrity','status':'passed','detail':'Saved payload and complete patient-state lineage verified.'}],
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,'ode_solver_rerun':False,
        'analytic_reference_evaluated':False,'limitation':LIMITATION,
        'not_checked_by_this_audit':['Source equation transcription','Covariate-to-parameter derivation; the analytic reference uses the archived CL/F, V/F and transit rate.'],
        'unestablished':['Independent patient covariate verification','Individual model applicability',
            'Observed-data fit or reproduction of the source population study','Prediction uncertainty coverage',
            'PD, efficacy, toxicity and dose suitability']}
    supported=(isinstance(p,dict) and all(type(p.get(k)) in (int,float) and math.isfinite(p[k]) and p[k]>0
               for k in ('apparent_clearance_l_h','apparent_volume_l','transit_rate_h'))
               and r['method_version']=='hughes-educational-pk-v1.0' and r['point_amount_order']==['ABS']+[f'TRANS{i}' for i in range(1,8)]
               and 0<p['apparent_clearance_l_h']/p['apparent_volume_l']<=p['transit_rate_h'])
    if not supported:
        report['status']='analytic_audit_withheld'
        report['checks'].append({'code':'analytic_reference_scope','status':'withheld','detail':'Archived model version, structure or rates are outside this analytic audit.'})
    else:
        events=review['treatment_request_preview']['request']['events'];cl=p['apparent_clearance_l_h'];volume=p['apparent_volume_l'];ktr=p['transit_rate_h']
        report['analytic_reference_evaluated']=True
        references=[analytic_state(point['time_h'],events,cl,volume,ktr) for point in r['points']]
        def values_check(code,unit,actual,expected,atol,rtol=0.0):
            errors=[abs(x-y) for x,y in zip(actual,expected)]
            passed=len(actual)==len(expected) and all(math.isfinite(x) and math.isfinite(y) and abs(x-y)<=atol+rtol*abs(y) for x,y in zip(actual,expected))
            report['checks'].append({'code':code,'status':'passed' if passed else 'failed','unit':unit,
                'max_absolute_error':max(errors,default=0.0),'absolute_tolerance':atol,'relative_tolerance':rtol})
        for code,key,unit,tol in [('analytic_concentration','concentration_ng_ml','ng/mL',5e-7),('analytic_cumulative_auc','auc_0_t_ng_h_ml','ng·h/mL',5e-5)]:
            values_check(code,unit,[s[key] for s in r['points']],[s[key] for s in references],tol,1e-8)
        def amounts(s):return s['precentral_amounts_mg']+[s['central_amount_mg'],s['eliminated_amount_mg']]
        values_check('analytic_compartment_amounts','mg',[v for s in r['points'] for v in amounts(s)],
                     [v for s in references for v in amounts(s)],5e-8,1e-8)
        values_check('requested_amount_schedule','mg',[s['cumulative_requested_amount_mg'] for s in r['points']],
                     [s['cumulative_requested_amount_mg'] for s in references],1e-10)
        total=math.fsum(e['amount']['value'] for e in events)
        values_check('point_amount_conservation','mg',[math.fsum(amounts(s)) for s in r['points']],
                     [s['cumulative_requested_amount_mg'] for s in r['points']],1e-9*total)
        boundaries=r['event_boundaries'];expected_times=[e['time']['value'] for e in events]
        values_check('event_times','h',[e['time_h'] for e in boundaries],expected_times,0)
        for unit,key,tol in [('ng/mL','concentration_ng_ml',5e-7),('ng·h/mL','auc_0_t_ng_h_ml',5e-5),('mg','central_amount_mg',5e-8)]:
            values_check('event_continuity_'+key,unit,[e['after'][key] for e in boundaries],[e['before'][key] for e in boundaries],tol)
        actual_boundaries=[boundary[k] for boundary in boundaries for k in ('before','after')]
        reference_boundaries=[analytic_state(e['time']['value'],events,cl,volume,ktr,before_event=before) for e in events for before in (True,False)]
        values_check('analytic_event_amounts','mg',[v for state in actual_boundaries for v in amounts(state)],
                     [v for state in reference_boundaries for v in amounts(state)],5e-8,1e-8)
        for key,unit,tol in [('concentration_ng_ml','ng/mL',5e-7),('auc_0_t_ng_h_ml','ng·h/mL',5e-5)]:
            values_check('analytic_event_'+key,unit,[state[key] for state in actual_boundaries],
                         [state[key] for state in reference_boundaries],tol,1e-8)
        values_check('event_addition_to_abs','mg',[e['after']['precentral_amounts_mg'][0]-e['before']['precentral_amounts_mg'][0] for e in boundaries],
                     [e['amount']['value'] for e in events],1e-9*total)
        values_check('analytic_total_auc','ng·h/mL',[r['analytic_auc_0_infinity_ng_h_ml']],[1000*total/cl],5e-5,1e-8)
        values_check('reported_window_auc','ng·h/mL',[r['auc_0_horizon_ng_h_ml']],[r['points'][-1]['auc_0_t_ng_h_ml']],5e-5,1e-8)
        report['status']='mathematical_checks_passed' if all(c['status']=='passed' for c in report['checks']) else 'mathematical_check_failed'
    report['report_sha256']=digest(report)
    return report


def register_educational_pk_audit_commands(app):
    @app.cli.command('patient-pk-audit')
    @click.option('--id','run_id',type=click.IntRange(min=1),required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(run_id,json_output,output):
        """Audit frozen arithmetic against an independent closed-form reference."""
        try:
            report=audit_pk_run(run_id)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported educational audit: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Run #{run_id} | {report['status']} | Clinical prediction validated: false")
                for c in report['checks']:click.echo(f"[{c['status'].upper()}] {c['code']}")
                click.echo(LIMITATION)
            if report['status']!='mathematical_checks_passed':raise click.exceptions.Exit(1)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
