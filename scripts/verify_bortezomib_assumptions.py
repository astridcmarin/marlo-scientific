"""Optional developer verification; requires SciPy, not needed by the application."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scipy.integrate import solve_ivp
import scipy
from intelligence_store.bortezomib_timecourse import build_timecourse

def verify(rate):
    # Separately written RHS and direct Hill evaluation, no production derivative calls.
    def rhs(t,z):
        k=1.08+2.64*math.exp(-rate*t)
        central,fast,slow,eliminated=z
        return [-(k+2.77+2.14)*central+0.89*fast+0.04*slow,
                2.77*central-0.89*fast,2.14*central-0.04*slow,k*central]
    report=build_timecourse(relaxation_rate_per_h=rate);t=0.;z=[0.,0.,0.,0.];errors={'amount_mg':0.,'concentration_nm':0.,'activity_percentage_points':0.}
    for row in report['points']:
        target=row['time_h']
        if target>t:
            sol=solve_ivp(rhs,(t,target),z,method='DOP853',rtol=1e-11,atol=1e-13)
            if not sol.success:raise RuntimeError(sol.message)
            z=list(sol.y[:,-1]);t=target
        if row['phase']=='post_dose':z[0]+=2.327
        c=z[0]/19.1*1e6/384.24
        pa=100-71.1*c**1.47/(1.79**1.47+c**1.47)
        errors['amount_mg']=max(errors['amount_mg'],*(abs(v-row[k]) for v,k in zip(z,['central_mg','peripheral_2_mg','peripheral_3_mg','eliminated_mg'])))
        errors['concentration_nm']=max(errors['concentration_nm'],abs(c-row['concentration_nm']))
        errors['activity_percentage_points']=max(errors['activity_percentage_points'],abs(pa-row['activity_percent']))
    limits={'amount_mg':1e-5,'concentration_nm':0.002,'activity_percentage_points':0.001}
    passed=all(errors[k]<limits[k] for k in errors)
    return dict(status='passed' if passed else 'failed',comparison='RK4 versus separately coded DOP853 under the same explicit assumptions',
        assumed_relaxation_rate_per_h=rate,scipy_version=scipy.__version__,maximum_absolute_differences=errors,tolerances=limits,
        points_compared=len(report['points']),report_sha256=report['report_sha256'],
        biological_validation=False,independent_scientific_review=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args();runs=[verify(rate) for rate in [0.1,1.,10.]];result={'status':'passed' if all(r['status']=='passed' for r in runs) else 'failed','scenarios':runs}
    if a.output:
        with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2));sys.exit(0 if result['status']=='passed' else 1)
