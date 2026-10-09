"""Published-parameter extraction checks, not a complete PK simulator."""
import copy
import hashlib
import json
import math
from pathlib import Path
import click
from .patient_state import digest

EXTRACT_PATH=Path(__file__).parent/'data'/'hughes_parameter_extract_v1.json'
EXTRACT_SHA256='8199220db206c3e78fd5abc40191602d5b59e6275f5c77d9e43e0f7c90ae5f74'
METHOD_VERSION='pk-parameter-reference-v1.0'


def load_parameter_extract(path=EXTRACT_PATH):
    try:
        content=Path(path).read_bytes()
        if hashlib.sha256(content).hexdigest()!=EXTRACT_SHA256:raise ValueError('Checksum differs')
        data=json.loads(content)
        if data['schema_version']!='pk-parameter-extract-v1':raise ValueError('Schema differs')
        return data
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise ValueError('Published parameter extract is missing or changed. Restore the Step 34 file; no parameter check was generated.') from exc


def _positive(value,label):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError(f'{label} must be a finite positive number.')
    return float(value)


def _parameter_math(ffm_kg,crcl_ml_min,parameters):
    """Internal algebra for fixed verification cases; no patient applicability check."""
    ffm=_positive(ffm_kg,'FFM');crcl=_positive(crcl_ml_min,'CrCl')
    p={k:v['value'] for k,v in parameters.items()}
    clearance=p['apparent_clearance']*(ffm/p['reference_ffm'])**p['ffm_clearance_exponent']*(crcl/p['reference_crcl'])**p['crcl_exponent']
    volume=p['apparent_volume']*(ffm/p['reference_ffm'])**p['ffm_volume_exponent']
    result={'apparent_clearance_l_h':clearance,'apparent_volume_l':volume,
            'elimination_rate_h':clearance/volume,'transit_rate_h':p['transit_rate']}
    if any(not math.isfinite(v) or v<=0 for v in result.values()):raise ValueError('Parameter algebra produced an invalid result.')
    return result


def parameter_reference_report():
    extract=load_parameter_extract();p=extract['parameters']
    cases=[]
    for label,ffm,crcl in [('published_normalization',55,90),('renal_math_check',55,45),('body_composition_math_check',80,90)]:
        values=_parameter_math(ffm,crcl,p)
        cases.append({'label':label,'inputs':{'ffm_kg':ffm,'crcl_ml_min':crcl},'parameters':values})
    reference=cases[0]['parameters'];renal=cases[1]['parameters'];body=cases[2]['parameters']
    checks=[{'name':'reference_clearance','expected':12.0,'actual':reference['apparent_clearance_l_h']},
            {'name':'reference_volume','expected':68.8,'actual':reference['apparent_volume_l']},
            {'name':'reference_transit_rate','expected':13.5,'actual':reference['transit_rate_h']},
            {'name':'renal_clearance_ratio','expected':0.5**0.224,'actual':renal['apparent_clearance_l_h']/reference['apparent_clearance_l_h']},
            {'name':'renal_volume_ratio','expected':1.0,'actual':renal['apparent_volume_l']/reference['apparent_volume_l']},
            {'name':'ffm_volume_ratio','expected':80/55,'actual':body['apparent_volume_l']/reference['apparent_volume_l']}]
    for check in checks:check['passed']=math.isclose(check['actual'],check['expected'],rel_tol=1e-12,abs_tol=1e-12)
    report={'schema_version':'pk-parameter-reference-report-v1','method_version':METHOD_VERSION,
            'extract_version':extract['extract_version'],'extract_sha256':EXTRACT_SHA256,
            'status':'parameter_math_passed' if all(c['passed'] for c in checks) else 'parameter_math_failed',
            'ready_for_patient_simulation':False,'concentration_simulation_status':'not_implemented',
            'source':copy.deepcopy(extract['source']),'parameter_basis':copy.deepcopy(p),
            'equations':copy.deepcopy(extract['equations']),'input_definitions':copy.deepcopy(extract['input_definitions']),
            'fixed_cases':cases,'checks':checks,'tolerance':{'relative':1e-12,'absolute':1e-12},
            'random_effects':'eta_CL=eta_V=0; deterministic typical parameter algebra',
            'limitations':copy.deepcopy(extract['limitations']),
            'validation_scope':'Normalization identities and algebraic consistency only. This is not reproduction of a published concentration curve, NONMEM run, population fit or clinical validation.'}
    report['report_sha256']=digest(report)
    return report


def register_pk_parameter_reference_commands(app):
    @app.cli.command('pk-parameter-check')
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def pk_parameter_check(json_output,output):
        """Check fixed published parameter algebra, without reading patient states."""
        try:
            report=parameter_reference_report()
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved parameter check: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo('Hughes 2019 parameter layer | '+report['status'])
                for check in report['checks']:click.echo(f"[{'PASSED' if check['passed'] else 'FAILED'}] {check['name']}: {check['actual']:.8g}")
                click.echo('Patient simulation ready: false | Concentration simulation: not_implemented')
                click.echo(report['validation_scope'])
            if report['status']=='parameter_math_failed':raise click.ClickException('Parameter checks failed.')
        except (ValueError,OSError) as exc:raise click.ClickException(str(exc)) from exc
