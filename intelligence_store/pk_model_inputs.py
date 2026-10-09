"""Explicit synthetic model covariates and bounded parameter preview; no patient adapter."""
import copy
import hashlib
import json
import math
from pathlib import Path
import click
from .patient_state import digest
from .published_transit_reference import load_structure_contract, CONTRACT_SHA256
from .pk_parameter_reference import load_parameter_extract, _parameter_math, EXTRACT_SHA256

SCHEMA_VERSION='hughes-model-inputs-v1'
METHOD_VERSION='hughes-model-input-preview-v1.0'
INPUT_CONTRACT_PATH=Path(__file__).parent/'data'/'hughes_input_contract_v1.json'
INPUT_CONTRACT_SHA256='ee460cb9853edd6811b44d6dffa755bc086d76e3cc8ad6fb976c1b9104476722'
UNITS={'fat_free_mass':'kg','creatinine_clearance':'mL/min'}
RECORDED_METHODS={'fat_free_mass':'janmahasatian_recorded','creatinine_clearance':'cockcroft_gault_recorded'}
FIELD_KEYS={'value','unit','origin','method','source_ref'}


def load_input_contract(path=INPUT_CONTRACT_PATH):
    try:
        raw=Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=INPUT_CONTRACT_SHA256:raise ValueError('Changed contract')
        data=json.loads(raw)
        if data['model_contract_sha256']!=CONTRACT_SHA256:raise ValueError('Incompatible contract')
        return data
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise ValueError('Model input contract is missing or changed; no preview was generated.') from exc


def validate_model_inputs(inputs):
    if not isinstance(inputs,dict) or set(inputs)!={'schema_version','purpose','fields'}:
        raise ValueError('Supply schema_version, purpose and fields only.')
    if inputs['schema_version']!=SCHEMA_VERSION or inputs['purpose']!='synthetic_educational':
        raise ValueError('Only synthetic educational Hughes model inputs are supported.')
    fields=inputs['fields']
    if not isinstance(fields,dict) or set(fields)-set(UNITS):
        raise ValueError('Only fat_free_mass and creatinine_clearance are model covariates. No weight or eGFR substitution.')
    result={'schema_version':SCHEMA_VERSION,'purpose':'synthetic_educational','fields':{}}
    for name,unit in UNITS.items():
        raw=fields.get(name,{'value':None,'unit':unit,'origin':'unknown','method':'unknown','source_ref':None})
        if not isinstance(raw,dict) or set(raw)!=FIELD_KEYS:
            raise ValueError(f'{name}: supply value, unit, origin, method and source_ref.')
        if raw['unit']!=unit:raise ValueError(f'{name}: unit must be {unit}; no conversion is performed.')
        source=raw['source_ref']
        if source is not None:
            if not isinstance(source,str) or not 1<=len(source.strip())<=1000:
                raise ValueError(f'{name}: source_ref must be nonblank text up to 1000 characters or null.')
            source=source.strip()
        value=raw['value']
        if value is None:
            if raw['origin']!='unknown' or raw['method']!='unknown' or source is not None:
                raise ValueError(f'{name}: unknown value requires unknown origin/method and null source_ref.')
        else:
            if type(value) not in (int,float):raise ValueError(f'{name}: expected a finite positive JSON number.')
            try:value=float(value)
            except (ValueError,OverflowError):raise ValueError(f'{name}: number is not representable.') from None
            if not math.isfinite(value) or not 0<value<=1000000:
                raise ValueError(f'{name}: value must be positive, finite and within the implementation limit of 1000000.')
            if raw['origin'] not in ('synthetic_input','assumption'):
                raise ValueError(f'{name}: use synthetic_input or assumption for supplied values.')
            if raw['method'] not in ('direct_synthetic_covariate',RECORDED_METHODS[name]):
                raise ValueError(f'{name}: unsupported method; total weight and indexed eGFR are not equivalents.')
            if (raw['origin']=='assumption' or raw['method']==RECORDED_METHODS[name]) and source is None:
                raise ValueError(f'{name}: assumptions and recorded methods require source_ref.')
        result['fields'][name]={'value':value,'unit':unit,'origin':raw['origin'],
                                'method':raw['method'],'source_ref':source}
    return result


def model_input_example():
    return {'schema_version':SCHEMA_VERSION,'purpose':'synthetic_educational','fields':{
        name:{'value':value,'unit':UNITS[name],'origin':'synthetic_input',
              'method':'direct_synthetic_covariate',
              'source_ref':'Invented algebra example at source normalization; not a saved patient'}
        for name,value in (('fat_free_mass',55.0),('creatinine_clearance',90.0))}}


def preview_model_inputs(inputs):
    canonical=validate_model_inputs(inputs)
    contract=load_input_contract();structure=load_structure_contract();extract=load_parameter_extract()
    if structure['contract_version']!='hughes-2019-final-structure-v1.0':
        raise ValueError('Structure contract is incompatible.')
    checks=[];missing=[];outside=[]
    for name,spec in contract['fields'].items():
        value=canonical['fields'][name]['value'];lo,hi=spec['observed_range']
        if value is None:status='unknown';missing.append(name)
        elif not lo<=value<=hi:status='outside_observed_range';outside.append(name)
        else:status='within_observed_range'
        checks.append({'field':name,'value':value,'unit':spec['unit'],
                       'observed_range':[lo,hi],'status':status})
    parameters=None
    if not missing and not outside:
        parameters=_parameter_math(canonical['fields']['fat_free_mass']['value'],
            canonical['fields']['creatinine_clearance']['value'],extract['parameters'])
    report={'schema_version':'pk-model-input-preview-v1','method_version':METHOD_VERSION,
        'inputs':canonical,'inputs_sha256':digest(canonical),
        'input_contract_version':contract['contract_version'],'input_contract_sha256':INPUT_CONTRACT_SHA256,
        'structure_contract_sha256':CONTRACT_SHA256,'parameter_extract_sha256':EXTRACT_SHA256,
        'source':copy.deepcopy(contract['source']),
        'status':'missing_inputs' if missing else ('outside_reference_range' if outside else 'parameter_preview_available'),
        'missing_fields':missing,'outside_reference_range_fields':outside,'range_checks':checks,
        'parameter_preview':parameters,'patient_revision_id':None,
        'ready_for_patient_simulation':False,'simulation_status':'not_run',
        'provenance_verification':'Input origins, method names and source_ref are recorded declarations, not independently verified calculations or evidence.',
        'policy':contract['policy'],
        'limitations':['Synthetic covariates only; no saved patient is read or modified.',
            'No Janmahasatian or Cockcroft–Gault estimation, unit conversion, eGFR substitution or default patient values.',
            'Observed ranges are source coverage context, not clinical thresholds or sufficient evidence of applicability.',
            'Parameter algebra uses zero random effects; no concentration, efficacy, toxicity or recommended dose is calculated.']}
    report['report_sha256']=digest(report)
    return report


def _no_duplicate_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError(f'Duplicate JSON key: {key}')
        result[key]=value
    return result


def register_pk_model_input_commands(app):
    @app.cli.command('pk-model-inputs')
    @click.option('--example',is_flag=True)
    @click.option('--inputs-file',type=click.Path(exists=True,dir_okay=False,path_type=Path))
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(example,inputs_file,json_output,output):
        """Validate explicit synthetic covariates; no patient or simulation run."""
        if bool(example)==bool(inputs_file):raise click.ClickException('Choose exactly one of --example or --inputs-file.')
        try:
            if example:inputs=model_input_example()
            else:
                with inputs_file.open('rb') as handle:raw=handle.read(65537)
                if len(raw)>65536:raise ValueError('Input JSON exceeds 64 KiB.')
                inputs=json.loads(raw.decode('utf-8'),object_pairs_hook=_no_duplicate_keys)
            report=preview_model_inputs(inputs)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved model input preview: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Hughes model inputs | {report['status']} | Synthetic parameter algebra only")
                for check in report['range_checks']:
                    click.echo(f"{check['field']}: {check['value']} {check['unit']} | {check['status']}")
                if report['parameter_preview']:
                    for name,value in report['parameter_preview'].items():click.echo(f'{name}: {value:.6g}')
                click.echo('Simulation: not_run | Patient simulation ready: false')
                click.echo(report['provenance_verification'])
        except (ValueError,OSError,UnicodeError) as exc:raise click.ClickException(str(exc)) from exc
