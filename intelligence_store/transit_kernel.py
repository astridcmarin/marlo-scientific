"""Generic serial-transit ODE kernel. No drug model or patient adapter is attached."""
import json
import math
from pathlib import Path
import click
from .patient_state import digest

METHOD_VERSION='generic-transit-rk4-v1.0'
MAX_STEPS=250000
MAX_POINTS=2001


def _positive(value,label):
    if type(value) not in (int,float):raise ValueError(f'{label} requires a finite positive number.')
    try:value=float(value)
    except (ValueError,OverflowError):raise ValueError(f'{label} requires a finite positive number.') from None
    if not math.isfinite(value) or not 0<value<=1000000:
        raise ValueError(f'{label} must be positive, finite and at most 1000000 (implementation limit).')
    return value


def solve_transit(*,dose_mg,volume_l,clearance_l_h,transit_rate_h,stages,
                  horizon_h=24.0,display_step_h=0.1,max_step_h=0.01):
    """Dose starts in stage 1. Exactly stages transfer steps precede the central compartment."""
    if type(stages) is not int or not 1<=stages<=20:raise ValueError('stages must be an integer from 1 to 20.')
    dose=_positive(dose_mg,'dose_mg');volume=_positive(volume_l,'volume_l')
    clearance=_positive(clearance_l_h,'clearance_l_h');rate=_positive(transit_rate_h,'transit_rate_h')
    horizon=_positive(horizon_h,'horizon_h');display=_positive(display_step_h,'display_step_h')
    requested=_positive(max_step_h,'max_step_h');ke=clearance/volume
    if not math.isfinite(ke) or ke<=0:raise ValueError('Elimination rate is not representable.')
    point_ratio=horizon/display
    if not math.isfinite(point_ratio) or point_ratio>MAX_POINTS-1:raise ValueError('Requested display grid exceeds the point budget.')
    step=min(requested,0.05/max(rate,ke))
    step_ratio=horizon/step if step else math.inf
    if not math.isfinite(step_ratio) or step_ratio+math.ceil(point_ratio)>MAX_STEPS:
        raise ValueError('Requested integration exceeds the step budget.')
    times=[0.0]
    for i in range(1,math.ceil(point_ratio)+1):
        t=min(i*display,horizon)
        if t>times[-1]:times.append(t)
    # stages transit amounts, central amount, eliminated amount, concentration integral.
    y=[dose]+[0.0]*(stages+2)
    def derivative(a):
        d=[-rate*a[0]]
        d.extend(rate*(a[i-1]-a[i]) for i in range(1,stages))
        d.extend((rate*a[stages-1]-ke*a[stages],ke*a[stages],1000*a[stages]/volume))
        return d
    def add(a,b,factor):return [x+factor*z for x,z in zip(a,b)]
    def advance(a,dt):
        k1=derivative(a);k2=derivative(add(a,k1,dt/2));k3=derivative(add(a,k2,dt/2));k4=derivative(add(a,k3,dt))
        return [x+dt*(b+2*c+2*d+e)/6 for x,b,c,d,e in zip(a,k1,k2,k3,k4)]
    points=[];max_balance_error=0.0;steps=0;t=0.0
    for target in times:
        remaining=target-t
        count=math.ceil(remaining/step) if remaining>0 else 0
        if count:
            dt=remaining/count
            for _ in range(count):
                y=advance(y,dt);steps+=1
                if any(not math.isfinite(v) or v<0 for v in y):raise ValueError('Integration produced an invalid amount or integral.')
                max_balance_error=max(max_balance_error,abs(math.fsum(y[:stages+2])-dose))
            t=target
        points.append({'time_h':target,'transit_amounts_mg':y[:stages],
                       'central_amount_mg':y[stages],'eliminated_amount_mg':y[stages+1],
                       'concentration_ng_ml':1000*y[stages]/volume,'auc_0_t_ng_h_ml':y[-1]})
    if max_balance_error>1e-9*dose:raise ValueError('Amount balance check failed.')
    theoretical_auc=1000*dose/clearance
    result={'schema_version':'generic-transit-demo-v1','method_version':METHOD_VERSION,
            'model_kind':'invented_mathematical_example','drug':None,'patient_revision_id':None,
            'ready_for_patient_simulation':False,
            'inputs':{'dose_mg':dose,'volume_l':volume,'clearance_l_h':clearance,
                      'transit_rate_h':rate,'stages':stages,'horizon_h':horizon,'display_step_h':display},
            'solver':{'method':'classical fourth-order Runge–Kutta','requested_max_step_h':requested,
                      'effective_max_step_h':step,'steps':steps,'rate_step_bound':0.05,
                      'error_control':'Rate-based step ceiling only; not adaptive local-error estimation.'},
            'amount_balance':{'max_absolute_error_mg':max_balance_error,'tolerance_mg':1e-9*dose},
            'auc_0_horizon_ng_h_ml':y[-1],'analytic_auc_0_infinity_ng_h_ml':theoretical_auc,
            'points':points,
            'assumptions':['Linear serial transfer; one invented dose at time zero; all amount eventually reaches central compartment.',
                           'Exactly stages transit boxes before central; no separate depot or absorption box.',
                           'No lag, repeat doses, bioavailability multiplier, patient covariates or variability.'],
            'limitation':'Generic mathematical solver only. The compartments are not organs. Parameters are explicit invented inputs, not lenalidomide estimates. No published model, real patient response, efficacy, toxicity or dose recommendation is established.'}
    result['report_sha256']=digest(result)
    return result


def transit_demo():
    return solve_transit(dose_mg=1,volume_l=10,clearance_l_h=2,transit_rate_h=1,stages=3)


def register_transit_kernel_commands(app):
    @app.cli.command('transit-demo')
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(json_output,output):
        """Run a fixed invented transit example; no patient or published-model fitting."""
        try:
            report=transit_demo()
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved transit demonstration: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo('Generic transit demonstration | Invented parameters | No patient model')
                click.echo(f"Transit stages: {report['inputs']['stages']} | Solver steps: {report['solver']['steps']}")
                click.echo(f"Max amount-balance error: {report['amount_balance']['max_absolute_error_mg']:.3g} mg")
                click.echo(f"AUC 0–24 h: {report['auc_0_horizon_ng_h_ml']:.6g} ng·h/mL")
                click.echo('Patient simulation ready: false')
                click.echo(report['limitation'])
        except (ValueError,OSError) as exc:raise click.ClickException(str(exc)) from exc
