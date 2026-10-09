"""Closed-form generic reversible binding at constant free site concentration."""
import hashlib
import json
import math

METHOD_VERSION='generic-constant-free-binding-kinetics-v1.0'
REFERENCE={'reference_id':'graphpad-association-one-concentration',
    'url':'https://www.graphpad.com/guides/prism/latest/curve-fitting/reg_association1.htm',
    'role':'Conceptual rate/equilibrium reference; no drug-specific parameters are taken from it.',
    'checked_on':'2026-10-09'}


def _number(value,label,minimum,maximum):
    if type(value) not in (int,float):raise ValueError(f'{label} must be numeric, not a string or Boolean.')
    try: number=float(value)
    except (ValueError,OverflowError):raise ValueError(f'{label} is not representable.') from None
    if not math.isfinite(number) or not minimum<=number<=maximum:
        raise ValueError(f'{label} must be finite within {minimum:g} to {maximum:g} (implementation bounds, not biological ranges).')
    return number


def _hash(report):
    return hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def calculate_binding_kinetics(*,free_concentration_nm,kon_nm_inv_h_inv,koff_h_inv,times_h,initial_fraction=0):
    """Independent analytic time points for one constant-concentration experiment."""
    concentration=_number(free_concentration_nm,'free_concentration_nm',0,1e6)
    kon=_number(kon_nm_inv_h_inv,'kon_nm_inv_h_inv',1e-9,1e3)
    koff=_number(koff_h_inv,'koff_h_inv',1e-9,1e3)
    initial=_number(initial_fraction,'initial_fraction',0,1)
    if not isinstance(times_h,list) or not 1<=len(times_h)<=1001:raise ValueError('Provide 1 to 1001 times in hours.')
    times=[_number(t,'time_h',0,72) for t in times_h]
    if times[0]!=0 or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Times must start at zero and strictly increase; no sorting or resampling is performed.')
    association=kon*concentration
    rate=association+koff
    equilibrium=association/rate
    points=[]
    for time in times:
        z=rate*time
        # Convex combination, using expm1 to preserve very small changes from zero.
        fraction=initial*math.exp(-z)+equilibrium*(-math.expm1(-z))
        if not math.isfinite(fraction) or not 0<=fraction<=1:raise ValueError('Numerically invalid binding fraction.')
        points.append({'time_h':time,'fraction_bound':fraction})
    report={'schema_version':'generic-binding-kinetics-demo-v1','method_version':METHOD_VERSION,
        'purpose':'synthetic_educational','model_kind':'reversible_single_site_constant_free_concentration',
        'drug':None,'target':None,'patient_revision_id':None,'pk_run_id':None,'clinical_response':None,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,'pk_coupling_status':'not_connected',
        'inputs':{'free_concentration':{'value':concentration,'unit':'nM','origin':'invented_educational_input',
                    'meaning':'Constant explicitly supplied free concentration at a hypothetical target site.'},
            'kon':{'value':kon,'unit':'nM^-1 h^-1','origin':'invented_educational_input'},
            'koff':{'value':koff,'unit':'h^-1','origin':'invented_educational_input'},
            'initial_fraction':{'value':initial,'unit':'dimensionless','origin':'invented_educational_input'},
            'times':{'values':times,'unit':'h','origin':'explicit_demonstration_grid'}},
        'equations':{'derivative':'dtheta/dt = kon*C_free*(1-theta) - koff*theta',
            'solution':'theta(t) = theta_eq + (theta_initial - theta_eq)*exp(-(kon*C_free+koff)*t)',
            'derived_kd':'Kd = koff/kon'},
        'derived':{'kd_nm':koff/kon,'equilibrium_fraction':equilibrium,'relaxation_rate_h_inv':rate,
            'relaxation_half_time_h':math.log(2)/rate,
            'half_time_meaning':'Time to halve the gap to equilibrium at this constant free concentration, not a PK elimination half-life.'},
        'points':points,'numerical_method':'Analytic constant-coefficient solution; exp/expm1, no numerical ODE integration.',
        'numerical_limitation':'Floating-point rounding can produce the equilibrium value at finite time when the remaining gap is too small to resolve.',
        'concept_references':[dict(REFERENCE)],'parameter_evidence_status':'invented_not_drug_specific',
        'assumptions':['One class of equivalent independent sites; reversible one-to-one binding.',
            'Constant externally maintained free site concentration; no ligand depletion or PK calculation.',
            'Fixed site population, no competition, cooperativity, irreversible binding or target turnover.',
            'Explicit initial bound fraction; no assumed equilibration before time zero.'],
        'limitation':'Generic binding kinetics only. No patient physiology, real drug-target applicability, efficacy, toxicity, biomarker, dose suitability or clinical response is established.'}
    report['report_sha256']=_hash(report)
    return report


def binding_kinetics_example():
    times=[0,.1,.5,1,2,4,8,12,24]
    shared={'free_concentration_nm':10,'times_h':times,'initial_fraction':0}
    slow=calculate_binding_kinetics(kon_nm_inv_h_inv=.01,koff_h_inv=.1,**shared)
    fast=calculate_binding_kinetics(kon_nm_inv_h_inv=.1,koff_h_inv=1,**shared)
    result={'schema_version':'invented-binding-rate-comparison-v1','purpose':'synthetic_educational',
        'example_kind':'same_equilibrium_affinity_different_relaxation_rates',
        'slow_example':slow,'fast_example':fast,
        'comparison':{'kd_nm':10,'equilibrium_fraction':.5,'free_concentration_nm':10,
            'rate_multiplier':10,'meaning':'Rate constants are both multiplied by ten; their ratio and equilibrium fraction remain the same.'},
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'scope':'Two invented constant-concentration mathematical examples, not two drugs or virtual patients.'}
    result['report_sha256']=_hash(result)
    return result
