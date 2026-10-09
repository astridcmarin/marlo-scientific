"""Draft educational intended use and risk register; no governance sign-off."""
import copy
import hashlib
import json
from pathlib import Path
import click
from .patient_state import digest
from .pk_transcription_review import transcription_review_packet

CONTRACT_PATH = Path(__file__).parent / 'data' / 'patient_lab_intended_use_v1.json'
CONTRACT_SHA256 = '3b11dacc9528c8bcea65001712af5c88046de8f88ec1b157fbd20e360fa72701'
METHOD = 'patient-lab-intended-use-report-v1.0'
LIMITATION = ('Project-specific educational intended-use and risk draft. It is not governance '
              'acceptance, clinical validation, regulatory classification or readiness for real-patient use.')


def load_intended_use_contract(path=CONTRACT_PATH):
    try:
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
            raise ValueError('Changed contract digest')
        data = json.loads(raw)
        if data['schema_version'] != 'patient-lab-intended-use-contract-v1':
            raise ValueError('Unsupported schema')
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError('Intended-use contract is missing or changed; no report generated. Restore the Step 57 file or implement a reviewed versioned change.') from exc


def intended_use_report():
    contract = load_intended_use_contract()
    packet = transcription_review_packet()
    report = {'schema_version': 'patient-lab-intended-use-report-v1', 'method_version': METHOD,
        'status': 'draft_pending_review', 'contract_version': contract['contract_version'],
        'contract_sha256': CONTRACT_SHA256, 'model_contract_binding': copy.deepcopy(packet['contract_binding']),
        'source_reference': copy.deepcopy(packet['source_reference']),
        'purpose': contract['purpose'], 'scope': copy.deepcopy(contract['scope']),
        'permitted_uses': copy.deepcopy(contract['permitted_uses']),
        'prohibited_uses': copy.deepcopy(contract['prohibited_uses']),
        'failure_modes': copy.deepcopy(contract['failure_modes']),
        'change_control': copy.deepcopy(contract['change_control']),
        'independent_transcription_review': 'pending',
        'control_verification_performed': False, 'residual_risk_accepted': False,
        'governance_approval': None, 'clinical_prediction_validated': False,
        'ready_for_patient_simulation': False, 'database_writes_performed': False,
        'ode_solver_rerun': False, 'network_refresh_performed': False,
        'limitations': copy.deepcopy(contract['limitations']), 'limitation': LIMITATION}
    report['report_sha256'] = digest(report)
    return report


def register_patient_lab_intended_use_commands(app):
    @app.cli.command('patient-lab-intended-use')
    @click.option('--json', 'json_output', is_flag=True)
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(json_output, output):
        """Inspect the draft purpose, misuse risks and proposed review/change process."""
        try:
            report = intended_use_report()
            if output:
                with output.open('x', encoding='utf-8') as handle:
                    json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
                    handle.write('\n')
                click.echo(f'Exported intended-use draft: {output}')
            elif json_output:
                click.echo(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
            else:
                click.echo(f"Patient Lab | {report['status']} | Purpose: {report['purpose']}")
                click.echo(f"Failure modes: {len(report['failure_modes'])} | Governance approval: none")
                click.echo('Clinical prediction validated: false | Patient simulation ready: false')
                click.echo(LIMITATION)
        except (ValueError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
