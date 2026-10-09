"""Invented piecewise-constant free concentration; exact binding state carry-forward."""
from .target_binding_kinetics import calculate_binding_kinetics, _number, _hash

METHOD_VERSION='generic-piecewise-free-binding-v1.0'


def calculate_binding_schedule(*,phases,kon_nm_inv_h_inv,koff_h_inv,times_h,initial_fraction=0):
    """Phase starts are external concentration switches, not dose administrations."""
    kon=_number(kon_nm_inv_h_inv,'kon_nm_inv_h_inv',1e-9,1e3)
    koff=_number(koff_h_inv,'koff_h_inv',1e-9,1e3)
    initial=_number(initial_fraction,'initial_fraction',0,1)
    if not isinstance(times_h,list) or not 2<=len(times_h)<=1001:raise ValueError('Provide 2 to 1001 time points.')
    times=[_number(t,'time_h',0,72) for t in times_h]
    if times[0]!=0 or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Times must start at zero and strictly increase.')
    horizon=times[-1]
    if not isinstance(phases,list) or not 1<=len(phases)<=8:raise ValueError('Provide 1 to 8 explicit concentration phases.')
    normalized=[]
    for phase in phases:
        if not isinstance(phase,dict) or set(phase)!={'start_time_h','free_concentration_nm'}:
            raise ValueError('Each phase needs only start_time_h and free_concentration_nm; no dose or patient fields are accepted.')
        normalized.append({'start_time_h':_number(phase['start_time_h'],'start_time_h',0,72),
            'free_concentration_nm':_number(phase['free_concentration_nm'],'free_concentration_nm',0,1e6)})
    starts=[p['start_time_h'] for p in normalized]
    if starts[0]!=0 or any(b<=a for a,b in zip(starts,starts[1:])) or starts[-1]>=horizon:
        raise ValueError('Phases must start at zero, strictly increase and begin before the final sample time.')
    state=initial;segments=[];boundaries=[];points=[]
    def segment_report(concentration,duration,bound):
        return calculate_binding_kinetics(free_concentration_nm=concentration,kon_nm_inv_h_inv=kon,
            koff_h_inv=koff,initial_fraction=bound,times_h=[0,duration] if duration else [0])
    for index,phase in enumerate(normalized):
        start=phase['start_time_h'];end=starts[index+1] if index+1<len(starts) else horizon
        concentration=phase['free_concentration_nm']
        boundaries.append({'time_h':start,'transition':'schedule_start' if index==0 else 'external_concentration_switch',
            'before':None if index==0 else {'free_concentration_nm':normalized[index-1]['free_concentration_nm'],'fraction_bound':state},
            'after':{'free_concentration_nm':concentration,'fraction_bound':state}})
        endpoint=segment_report(concentration,end-start,state)
        segments.append({'phase_index':index,'start_time_h':start,'end_time_h':end,
            'constant_concentration_report':endpoint})
        for time in times:
            if start<=time<end or (index==len(normalized)-1 and time==end):
                exact=segment_report(concentration,time-start,state)
                points.append({'time_h':time,'phase_index':index,'free_concentration_nm':concentration,
                    'fraction_bound':exact['points'][-1]['fraction_bound']})
        state=endpoint['points'][-1]['fraction_bound']
    report={'schema_version':'generic-binding-schedule-v1','method_version':METHOD_VERSION,
        'purpose':'synthetic_educational','drug':None,'target':None,'patient_revision_id':None,'pk_run_id':None,
        'clinical_response':None,'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'inputs':{'phases':normalized,'phase_concentration_unit':'nM','phase_time_unit':'h',
            'kon':{'value':kon,'unit':'nM^-1 h^-1'},'koff':{'value':koff,'unit':'h^-1'},
            'initial_fraction':initial,'sample_times_h':times,'origin':'invented_educational_inputs'},
        'numerical_method':'Analytic constant-concentration solution on each phase, with exact state carry-forward; no ODE stepping or concentration interpolation.',
        'boundary_convention':'Sampled concentration at a switch uses the new phase. Fraction bound remains continuous. The pre-zero concentration is unknown, represented by a null first before-state.',
        'segments':segments,'boundaries':boundaries,'points':points,
        'concept_reference':{'url':'https://www.graphpad.com/guides/prism/latest/curve-fitting/reg_equaton_association_then_disso.htm',
            'role':'Association/dissociation concept only. Piecewise scheduling is our mathematical composition; no parameter or patient evidence is supplied.',
            'checked_on':'2026-10-09'},
        'assumptions':['Concentration changes are externally prescribed ideal steps, not absorption, distribution or elimination.',
            'Binding sites and rate constants remain fixed; binding state carries between phases without a jump.',
            'Generic reversible independent-site model; no depletion, competition, cooperativity or target turnover.'],
        'limitation':'Invented free-site concentration schedule only. A concentration switch is not a treatment event. No patient PK, exposure-to-site mapping, real drug-target model, efficacy, toxicity or dose suitability is established.'}
    report['report_sha256']=_hash(report)
    return report


def binding_pulse_example():
    phases=[{'start_time_h':0,'free_concentration_nm':10},{'start_time_h':4,'free_concentration_nm':0}]
    times=[0,.1,1,2,4,5,8,12,24]
    slow=calculate_binding_schedule(phases=phases,kon_nm_inv_h_inv=.01,koff_h_inv=.1,times_h=times)
    fast=calculate_binding_schedule(phases=phases,kon_nm_inv_h_inv=.1,koff_h_inv=1,times_h=times)
    report={'schema_version':'invented-binding-pulse-comparison-v1','purpose':'synthetic_educational',
        'slow_example':slow,'fast_example':fast,'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'scope':'Invented 10 nM free-site pulse until 4 h, then zero. Two generic binding systems, no drug or patient.'}
    report['report_sha256']=_hash(report)
    return report
