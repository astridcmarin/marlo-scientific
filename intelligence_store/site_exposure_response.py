"""Prescribed hypothetical site exposure with binding and downstream turnover."""
import math
from .target_binding_kinetics import _number, _hash


def calculate_site_response(*,profile='decay',initial_concentration_nm=10,profile_time_h=2,
        loss_rate_h_inv=.2,hypothetical_gain=4,times_h=None,max_step_h=.01):
    if profile not in ('decay','pulse'):
        raise ValueError('Profile must be decay or pulse.')
    concentration=_number(initial_concentration_nm,'initial_concentration_nm',0,100)
    profile_time=_number(profile_time_h,'profile_time_h',.1,23.9)
    kout=_number(loss_rate_h_inv,'loss_rate_h_inv',.001,1)
    gain=_number(hypothetical_gain,'hypothetical_gain',0,10)
    step=_number(max_step_h,'max_step_h',.001,.05)
    times=times_h if times_h is not None else [i*.12 for i in range(201)]
    if not isinstance(times,list) or not 2<=len(times)<=1001:raise ValueError('Provide 2 to 1001 sample times.')
    times=[_number(t,'time_h',0,24) for t in times]
    if times[0]!=0 or times[-1]!=24 or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Times must strictly increase from 0 to 24 h.')
    def site_concentration(time):
        if profile=='decay':return concentration*math.exp(-math.log(2)*time/profile_time)
        return concentration if time<profile_time else 0.
    targets=sorted(set(times+([profile_time] if profile=='pulse' else [])))
    examples={}
    for name,kon,koff in [('slower_binding',.01,.1),('faster_binding',.1,1.)]:
        fraction=0.;amount=1.;previous=0.;steps=0;largest=0.;states={0.:(fraction,amount)}
        for target in targets[1:]:
            count=max(1,math.ceil((target-previous)/step));h=(target-previous)/count
            if steps+count>30000:raise ValueError('Demonstration solver work limit exceeded.')
            # At a pulse boundary, integrate the left phase through its endpoint.
            # Sampled concentration uses the right phase. The state is continuous.
            pulse_c=concentration if previous<profile_time else 0.
            def derivatives(time,b,r):
                c=site_concentration(time) if profile=='decay' else pulse_c
                return kon*c*(1-b)-koff*b,kout*(1-(1+gain*b)*r)
            for i in range(count):
                t=previous+i*h
                b1,r1=derivatives(t,fraction,amount)
                b2,r2=derivatives(t+h/2,fraction+h*b1/2,amount+h*r1/2)
                b3,r3=derivatives(t+h/2,fraction+h*b2/2,amount+h*r2/2)
                b4,r4=derivatives(t+h,fraction+h*b3,amount+h*r3)
                fraction+=h*(b1+2*b2+2*b3+b4)/6
                amount+=h*(r1+2*r2+2*r3+r4)/6
                if not math.isfinite(fraction) or not math.isfinite(amount) or not -1e-12<=fraction<=1+1e-12 or not 0<=amount<=1+1e-12:
                    raise ValueError('Numerically invalid state; no clipping is performed.')
            steps+=count;largest=max(largest,h);states[target]=(fraction,amount);previous=target
        points=[{'time_h':t,'free_concentration_nm':site_concentration(t),
            'fraction_bound':states[t][0],'relative_amount':states[t][1],
            'loss_multiplier':1+gain*states[t][0]} for t in times]
        boundary=None
        if profile=='pulse':
            boundary={'time_h':profile_time,'fraction_bound':states[profile_time][0],
                'relative_amount':states[profile_time][1],
                'free_concentration_before_nm':concentration,'free_concentration_after_nm':0.}
        example={'schema_version':'hypothetical-site-response-system-v1',
            'binding_inputs':{'kon_nm_inv_h_inv':kon,'koff_h_inv':koff,'kd_nm':koff/kon,
                'initial_fraction':0,'origin':'invented_educational_inputs'},
            'points':points,'pulse_boundary':boundary,
            'solver':{'method':'Coupled RK4 for binding and relative amount; analytic prescribed concentration at each stage',
                'requested_max_step_h':step,'actual_max_step_h':largest,'steps':steps},
            'clinical_prediction_validated':False,'ready_for_patient_simulation':False}
        example['report_sha256']=_hash(example);examples[name]=example
    report={'schema_version':'hypothetical-site-exposure-response-v1',
        'method_version':'prescribed-site-profile-coupled-rk4-v1.0','purpose':'synthetic_educational',
        'inputs':{'profile':profile,'initial_concentration_nm':concentration,
            'profile_time_h':profile_time,'profile_time_meaning':'prescribed concentration half-life' if profile=='decay' else 'imposed pulse duration',
            'loss_rate_h_inv':kout,'hypothetical_gain':gain,'sample_times_h':times,'max_step_h':step,
            'initial_relative_amount':1,'origin':'invented_educational_inputs'},
        'equations':{'site_concentration':'C(t)=C0*exp(-ln(2)*t/profile_time)' if profile=='decay' else 'C(t)=C0 before profile_time; C(t)=0 at and after profile_time',
            'binding':'dB/dt=kon*C(t)*(1-B)-koff*B',
            'coupling':'loss_multiplier=1+hypothetical_gain*B',
            'turnover':'dR/dt=kout*(1-loss_multiplier*R)'},
        'units':{'time':'h','site_concentration':'nM','kon':'nM^-1 h^-1','koff':'h^-1',
            'kout':'h^-1','binding_fraction':'dimensionless','relative_amount':'dimensionless','hypothetical_gain':'dimensionless'},
        'examples':examples,'coupling_status':'explicit_unvalidated_hypothesis','coupling_evidence':None,
        'pk_connection':'not_connected','drug':None,'target':None,'downstream_protein':None,
        'patient_revision_id':None,'pk_run_id':None,'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'assumptions':['Concentration is prescribed directly at a hypothetical site, independent of binding and downstream state.',
            'No dose, absorption, organ distribution, clearance, plasma-to-site mapping or measured drug half-life is represented.',
            'Both binding systems have fixed sites and invented Kd=10 nM; the downstream quantity is separate from the binding target.',
            'Loss gain is an invented one-way coupling; constant synthesis, no feedback or variability.',
            'Initial binding is zero and downstream amount is at baseline; pre-zero history is unknown.'],
        'limitation':'Educational mathematical chain only. A smooth site concentration profile is not patient PK or a validated exposure-response relationship. No lenalidomide/IKZF model, efficacy, toxicity or dosing inference is established.'}
    report['report_sha256']=_hash(report)
    return report
