"""Build explicit synthetic declarations only; no patient lookup or execution."""
import re
from decimal import Decimal
from intelligence_store.pk_model_inputs import validate_model_inputs
from intelligence_store.treatment_requests import validate_treatment_request

BUILDER_FIELDS={'ffm','crcl','horizon','events','source_ref'}


def _decimal(text, label):
    if not isinstance(text,str) or len(text)>40 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',text.strip()):
        raise ValueError(f'{label}: enter a positive decimal number without units or exponent notation.')
    number=Decimal(text.strip())
    if number>1000000:
        raise ValueError(f'{label}: implementation limit exceeded.')
    return number


def build_synthetic_inputs(values):
    """Return canonical covariates/request; all units and events are explicit."""
    if set(values)!=BUILDER_FIELDS:
        raise ValueError('Supply all builder fields only.')
    note=values['source_ref']
    if not isinstance(note,str) or not 1<=len(note.strip())<=1000:
        raise ValueError('Describe the invented inputs in a provenance note (1–1000 characters).')
    note=note.strip()
    ffm=_decimal(values['ffm'],'FFM');crcl=_decimal(values['crcl'],'CrCl')
    treatment=_treatment(values['horizon'],values['events'],note)
    inputs=validate_model_inputs({'schema_version':'hughes-model-inputs-v1','purpose':'synthetic_educational',
        'fields':{name:{'value':float(value),'unit':unit,'origin':'synthetic_input',
            'method':'direct_synthetic_covariate','source_ref':note}
            for name,value,unit in [('fat_free_mass',ffm,'kg'),('creatinine_clearance',crcl,'mL/min')]}})
    return inputs,treatment


TREATMENT_FIELDS={'horizon','events','source_ref'}


def build_treatment_request(values):
    """Treatment request only, for workflows whose covariates come from elsewhere (estimated PK)."""
    if set(values)!=TREATMENT_FIELDS:
        raise ValueError('Supply horizon, events and a provenance note only.')
    note=values['source_ref']
    if not isinstance(note,str) or not 1<=len(note.strip())<=1000:
        raise ValueError('Describe the requested administrations in a provenance note (1–1000 characters).')
    return _treatment(values['horizon'],values['events'],note.strip())


def _treatment(horizon_text,text,note):
    horizon=_decimal(horizon_text,'Horizon')
    if not 0<horizon<=72 or horizon*10!=(horizon*10).to_integral_value():
        raise ValueError('Horizon must be positive, at most 72 h, and on a 0.1 h grid.')
    if not isinstance(text,str) or len(text)>1000:
        raise ValueError('Supply up to four administration lines: time in h, amount in mg.')
    lines=text.strip().splitlines()
    if not 1<=len(lines)<=4:
        raise ValueError('Supply one to four explicit administration lines.')
    events=[]
    for index,line in enumerate(lines):
        parts=line.split(',')
        if len(parts)!=2:
            raise ValueError('Each administration line must contain time in h, amount in mg.')
        time=_decimal(parts[0],'Event time');amount=_decimal(parts[1],'Event amount')
        if time!=24*index:
            raise ValueError('This execution supports time zero followed by exactly 24 h intervals; enter each event explicitly.')
        events.append({'time':{'value':float(time),'unit':'h'},
            'amount':{'value':float(amount),'unit':'mg'},'origin':'synthetic_input','source_ref':note})
    return validate_treatment_request({'schema_version':'synthetic-treatment-request-v1',
        'purpose':'synthetic_educational','drug':'lenalidomide','route':'oral','formulation':'capsule',
        'origin':'synthetic_input','source_ref':note,'horizon':{'value':float(horizon),'unit':'h'},'events':events})
