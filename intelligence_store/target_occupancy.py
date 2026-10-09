"""Generic equilibrium binding mathematics, with invented educational inputs only."""
import hashlib
import json
import math

METHOD_VERSION = 'generic-equilibrium-target-occupancy-v1.0'
MAX_POINTS = 1001
MAX_NM = 1e12
MIN_KD_NM = 1e-12
CONCEPT_REFERENCES = [
    {'reference_id':'graphpad-law-of-mass-action',
     'title':'GraphPad Prism Curve Fitting Guide: Law of mass action',
     'url':'https://www.graphpad.com/guides/prism/latest/curve-fitting/reg_key_concepts_law_of_mass_actio.htm',
     'role':'Equation/assumptions reference only; no drug or target parameters are taken from it.',
     'checked_on':'2026-10-09'},
    {'reference_id':'buchwald-2017-receptor-function',
     'doi':'10.1002/prp2.311',
     'url':'https://doi.org/10.1002/prp2.311',
     'role':'Distinguishes binding affinity, efficacy and signal amplification. Its response model is not implemented.',
     'checked_on':'2026-10-09'}]


def _number(value,label,minimum):
    if type(value) not in (int,float): raise ValueError(f'{label} must be a numeric value, not a string or Boolean.')
    try: number=float(value)
    except (ValueError,OverflowError): raise ValueError(f'{label} cannot be represented as a finite number.') from None
    if not math.isfinite(number) or not minimum<=number<=MAX_NM:
        raise ValueError(f'{label} must be finite and within {minimum:g} to {MAX_NM:g} nM (implementation bounds, not biological ranges).')
    return number


def calculate_target_occupancy(*,free_concentrations_nm,kd_nm):
    """Each point is an independent equilibrium example, not a time trajectory."""
    kd=_number(kd_nm,'kd_nm',MIN_KD_NM)
    if not isinstance(free_concentrations_nm,list) or not 1<=len(free_concentrations_nm)<=MAX_POINTS:
        raise ValueError(f'Provide a list of 1 to {MAX_POINTS} free concentrations in nM.')
    concentrations=[_number(v,'free_concentration_nm',0) for v in free_concentrations_nm]
    if any(b<=a for a,b in zip(concentrations,concentrations[1:])):
        raise ValueError('Free concentrations must be strictly increasing; no sorting or duplicate removal is performed.')
    result={'schema_version':'generic-target-occupancy-demo-v1','method_version':METHOD_VERSION,
        'status':'completed_educational_mathematics','purpose':'synthetic_educational',
        'model_kind':'generic_single_site_reversible_equilibrium_binding',
        'drug':None,'target':None,'patient_revision_id':None,'pk_run_id':None,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'pk_coupling_status':'not_connected','dynamic_simulation_status':'not_run',
        'clinical_response':None,
        'inputs':{'kd':{'value':kd,'unit':'nM','origin':'invented_educational_input'},
            'free_concentrations':{'values':concentrations,'unit':'nM','origin':'invented_educational_input',
                'meaning':'Specified free ligand concentration at the hypothetical target site; no concentration is inferred from plasma or tissue.'}},
        'equation':{'expression':'fraction_bound = C_free / (Kd + C_free)',
            'concentration_unit':'nM','output_unit':'dimensionless','scope':'Independent equilibrium points; no time variable.'},
        'points':[{'free_concentration_nm':c,'fraction_bound':c/(kd+c)} for c in concentrations],
        'assumptions':['One ligand and one class of equivalent, independent binding sites.',
            'Reversible one-to-one binding at equilibrium; all modeled sites are accessible.',
            'Free ligand concentration at the target is explicitly supplied, not total ligand concentration.',
            'No competing ligand, cooperativity, irreversible binding, receptor turnover or target degradation.',
            'No ligand depletion calculation, association/dissociation kinetics or downstream response model.'],
        'concept_references':[dict(r) for r in CONCEPT_REFERENCES],
        'parameter_evidence_status':'invented_inputs_not_drug_specific_evidence',
        'numerical_method':'Direct double-precision evaluation of the equilibrium equation.',
        'numerical_limitations':'Very high occupancy may round to 1.0 in floating point. Point count and input bounds are implementation limits.',
        'limitation':'Generic binding fraction only. No clinical effect, efficacy, toxicity, dose suitability, real drug-target applicability or patient response is established. Occupancy is not assumed to equal response.'}
    result['report_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False,
        separators=(',', ':'),allow_nan=False).encode('utf-8')).hexdigest()
    return result


def target_occupancy_example():
    return calculate_target_occupancy(kd_nm=10,free_concentrations_nm=[0,1,10,40,90,990])
