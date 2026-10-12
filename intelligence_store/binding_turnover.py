"""Hypothetical one-way binding-to-loss coupling, not a drug-response model."""
import math
from .target_binding_kinetics import _number, _hash
from .target_binding_schedule import calculate_binding_schedule


def calculate_binding_turnover(*,free_concentration_nm=10,pulse_duration_h=4,
        loss_rate_h_inv=.2,hypothetical_gain=4,times_h=None,max_step_h=.01):
    concentration=_number(free_concentration_nm,'free_concentration_nm',0,100)
    duration=_number(pulse_duration_h,'pulse_duration_h',.1,23.9)
    kout=_number(loss_rate_h_inv,'loss_rate_h_inv',.001,1)
    gain=_number(hypothetical_gain,'hypothetical_gain',0,10)
    step=_number(max_step_h,'max_step_h',.001,.05)
    times=times_h if times_h is not None else sorted(set([i*.12 for i in range(201)]+[duration]))
    if not isinstance(times,list) or not 2<=len(times)<=1001:
        raise ValueError('Provide 2 to 1001 sample times.')
    times=[_number(t,'time_h',0,24) for t in times]
    if times[0]!=0 or times[-1]!=24 or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Sample times must strictly increase from 0 to 24 h.')
    targets=sorted(set(times+[duration]))
    examples={}
    for name,kon,koff in [('slower_binding',.01,.1),('faster_binding',.1,1.)]:
        binding=calculate_binding_schedule(phases=[{'start_time_h':0,'free_concentration_nm':concentration},
            {'start_time_h':duration,'free_concentration_nm':0}],kon_nm_inv_h_inv=kon,koff_h_inv=koff,
            times_h=times,initial_fraction=0)
        switch_bound=binding['boundaries'][1]['after']['fraction_bound']
        association=kon*concentration;rate=association+koff;equilibrium=association/rate
        def bound(time):
            if time<duration:
                return equilibrium*(-math.expm1(-rate*time))
            return switch_bound*math.exp(-koff*(time-duration))
        def derivative(time,amount):
            return kout*(1-(1+gain*bound(time))*amount)
        amount=1.;previous=0.;steps=0;largest_step=0.;amounts={0.:amount}
        for target in targets[1:]:
            interval=target-previous
            count=max(1,math.ceil(interval/step));h=interval/count
            if steps+count>30000:raise ValueError('Demonstration solver work limit exceeded.')
            for i in range(count):
                t=previous+i*h
                a=derivative(t,amount)
                b=derivative(t+h/2,amount+h*a/2)
                c=derivative(t+h/2,amount+h*b/2)
                d=derivative(t+h,amount+h*c)
                amount+=h*(a+2*b+2*c+d)/6
                if not math.isfinite(amount) or not 0<=amount<=1+1e-12:
                    raise ValueError('Numerically invalid relative amount; no clipping is applied.')
            steps+=count;largest_step=max(largest_step,h)
            amounts[target]=amount;previous=target
        points=[{'time_h':p['time_h'],'free_concentration_nm':p['free_concentration_nm'],
            'fraction_bound':p['fraction_bound'],'loss_multiplier':1+gain*p['fraction_bound'],
            'relative_amount':amounts[p['time_h']]} for p in binding['points']]
        example={'schema_version':'hypothetical-binding-turnover-system-v1',
            'binding_report':binding,'points':points,
            'pulse_boundary':{'time_h':duration,'fraction_bound':switch_bound,
                'relative_amount':amounts[duration],'free_concentration_before_nm':concentration,
                'free_concentration_after_nm':0},
            'solver':{'method':'RK4 for relative amount; analytic binding at every stage',
                'requested_max_step_h':step,'actual_max_step_h':largest_step,'steps':steps},
            'clinical_prediction_validated':False,'ready_for_patient_simulation':False}
        example['report_sha256']=_hash(example);examples[name]=example
    report={'schema_version':'hypothetical-binding-turnover-comparison-v1',
        'method_version':'analytic-binding-rk4-turnover-v1.0','purpose':'synthetic_educational',
        'inputs':{'free_concentration_nm':concentration,'pulse_duration_h':duration,
            'loss_rate_h_inv':kout,'hypothetical_gain':gain,'sample_times_h':times,
            'max_step_h':step,'origin':'invented_educational_inputs'},
        'equations':{'binding':'dB/dt = kon*C_free*(1-B) - koff*B',
            'coupling':'loss_multiplier = 1 + hypothetical_gain*B',
            'turnover':'dR/dt = kout*(1 - loss_multiplier*R)'},
        'units':{'time':'h','free_site_concentration':'nM','kout':'h^-1',
            'binding_fraction':'dimensionless','relative_amount':'dimensionless','hypothetical_gain':'dimensionless'},
        'coupling_status':'explicit_unvalidated_hypothesis',
        'coupling_evidence':None,'pk_connection':'not_connected',
        'examples':examples,
        'assumptions':['Free concentration is an imposed site-level step, not patient plasma PK or a dose.',
            'Binding drives loss of a separate generic downstream quantity through an invented linear gain.',
            'Binding-site population stays fixed. The downstream quantity is not the binding target being depleted.',
            'Synthesis stays constant; baseline amount is 1; binding starts at 0.',
            'One-way coupling only: downstream amount does not change binding, site concentration or physiology.',
            'Both hypothetical binding systems have Kd=10 nM; this is not a calibrated drug-target affinity.'],
        'drug':None,'target':None,'downstream_protein':None,'patient_revision_id':None,'pk_run_id':None,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'limitation':'Hypothetical composition of generic equations only. The occupancy-to-loss rule and all parameters are invented. No lenalidomide, IKZF degradation, patient response, efficacy, toxicity or dosing inference is established.'}
    report['report_sha256']=_hash(report)
    return report
