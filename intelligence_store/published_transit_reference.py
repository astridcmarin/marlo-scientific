"""Source-verified final structure with a normalized mathematical reference input."""
import copy
import hashlib
import json
import math
from pathlib import Path
import click
from .patient_state import digest
from .pk_parameter_reference import load_parameter_extract, EXTRACT_SHA256
from .transit_kernel import solve_transit, METHOD_VERSION as SOLVER_VERSION

CONTRACT_PATH = Path(__file__).parent/'data'/'hughes_structure_contract_v1.json'
CONTRACT_SHA256 = '4322208e9d7dcd6d60d25624879beb6731f67301e894c05f13911d77685ca91d'
METHOD_VERSION = 'hughes-structure-reference-v1.0'


def load_structure_contract(path=CONTRACT_PATH):
    try:
        raw=Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=CONTRACT_SHA256:
            raise ValueError('Contract checksum differs.')
        data=json.loads(raw)
        if data['schema_version']!='published-pk-structure-contract-v1':
            raise ValueError('Structure schema differs.')
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError('Published structure contract is missing or changed; no reference calculation was generated.') from exc


def _reference_calculation(max_step_h=0.001):
    contract=load_structure_contract()
    extract=load_parameter_extract()
    values=contract['reference_values']
    mapping={'apparent_clearance_l_h':'apparent_clearance','apparent_volume_l':'apparent_volume',
             'transit_rate_h':'transit_rate','ffm_kg':'reference_ffm','crcl_ml_min':'reference_crcl',
             'ffm_clearance_exponent':'ffm_clearance_exponent',
             'ffm_volume_exponent':'ffm_volume_exponent','crcl_exponent':'crcl_exponent'}
    if any(values[k]!=extract['parameters'][v]['value'] for k,v in mapping.items()):
        raise ValueError('Supplement and main-text parameter references disagree.')
    # The generic kernel represents EXACTLY eight precentral boxes here:
    # ABS followed by TRANS1 through TRANS7. Its generic scope labels are not
    # repurposed; this module constructs a separate source-specific report.
    numerical=solve_transit(dose_mg=1.0,volume_l=values['apparent_volume_l'],
        clearance_l_h=values['apparent_clearance_l_h'],transit_rate_h=values['transit_rate_h'],
        stages=contract['structure']['precentral_stage_count'],horizon_h=24.0,
        display_step_h=0.1,max_step_h=max_step_h)
    report={'schema_version':'published-transit-reference-report-v1','method_version':METHOD_VERSION,
        'drug':'lenalidomide','model_kind':'source_structural_reference_with_normalized_input',
        'patient_revision_id':None,'ready_for_patient_simulation':False,
        'status':'source_structure_verified_reference_calculated',
        'contract_version':contract['contract_version'],'contract_sha256':CONTRACT_SHA256,
        'parameter_extract_sha256':EXTRACT_SHA256,'source':copy.deepcopy(contract['source']),
        'structure':copy.deepcopy(contract['structure']),'reference_values':copy.deepcopy(values),
        'verification_input':copy.deepcopy(contract['verification_input']),
        'units':copy.deepcopy(contract['units']),
        'random_effects':contract['typical_value_assumption'],
        'solver':copy.deepcopy(numerical['solver']), 'solver_method_version':SOLVER_VERSION,
        'amount_balance':copy.deepcopy(numerical['amount_balance']),
        'points':copy.deepcopy(numerical['points']),
        'point_amount_order':contract['structure']['serial_precentral_order'],
        'auc_0_horizon_ng_h_ml':numerical['auc_0_horizon_ng_h_ml'],
        'analytic_auc_0_infinity_ng_h_ml':numerical['analytic_auc_0_infinity_ng_h_ml'],
        'validation_scope':'Final source topology and parameter agreement; analytic and independent numerical checks of the normalized linear response. Not a NONMEM run, observed concentration fit, population validation or clinical prediction.',
        'remaining_requirements':['Source-data/NONMEM-output comparison or documented evidence-based validation scope.',
            'Patient applicability and input derivation review before any adapter.',
            'Separate explicit treatment request and model-input provenance.'],
        'limitations':copy.deepcopy(contract['boundaries'])}
    report['report_sha256']=digest(report)
    return report


def published_transit_reference():
    return _reference_calculation()


def register_published_transit_reference_commands(app):
    @app.cli.command('pk-structure-reference')
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(json_output,output):
        """Source-verified structure, normalized unit input; no patient connection."""
        try:
            report=published_transit_reference()
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Saved published-structure reference: {output}')
            elif json_output:
                click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo('Hughes 2019 final structure | Normalized 1 mg input | No patient model')
                click.echo('Precentral stages: 8 = ABS + TRANS1 through TRANS7 | Central: CEN')
                click.echo('Reference FFM: 55 kg | CrCl: 90 mL/min | ETA1=ETA2=ETA3=0')
                click.echo('Apparent clearance: 12 L/h | Apparent volume: 68.8 L | KTR: 13.5/h')
                click.echo(f"AUC 0–24 h: {report['auc_0_horizon_ng_h_ml']:.6g} ng·h/mL")
                click.echo(f"Max amount-balance error: {report['amount_balance']['max_absolute_error_mg']:.3g} mg")
                click.echo('Patient simulation ready: false')
                click.echo(report['validation_scope'])
        except (ValueError,OSError) as exc:
            raise click.ClickException(str(exc)) from exc
