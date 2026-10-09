"""Local validation-artifact inventory; file integrity is not evidence acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import re
import click
from .patient_state import digest
from .pk_transcription_review import transcription_review_packet
from .patient_lab_intended_use import intended_use_report

METHOD = 'pk-validation-artifact-inventory-v1.0'
MAX_MANIFEST_BYTES = 128 * 1024
REQUIREMENTS = (
    ('independent_transcription_review', 'Independent source transcription review', 'Recorded reviewer, independence, date, source locations, discrepancies and resolutions.'),
    ('source_analysis_dataset', 'Authorized source analysis dataset', 'Original observation-level model analysis dataset with documented access rights and data dictionary.'),
    ('source_dosing_records', 'Source dosing and sampling records', 'Dose amount/route/event times, sampling times and time origin linked to source subjects.'),
    ('original_model_code', 'Original final model code', 'Final control stream and dependencies; distinguish exploratory streams and modifications.'),
    ('source_software_environment', 'Source software environment', 'Software versions, estimation settings and execution dependencies.'),
    ('source_model_outputs', 'Source model outputs and diagnostics', 'Parameter estimates, objective function, subject-level predictions and diagnostic outputs.'),
    ('external_observed_dataset', 'Independent observed concentration dataset', 'Authorized deidentified independent observations with dosing, sampling, covariates, units and assay context.'),
    ('prespecified_validation_protocol', 'Prespecified validation protocol', 'Intended-use-specific endpoints, error/calibration metrics, subgroup checks and acceptance criteria defined before evaluation.'),
)
LIMITATION = ('Local artifact presence and SHA256 inventory only. It does not verify access rights, '
              'reviewer identity, contents, provenance, data deidentification, scientific suitability '
              'or validation results. No dataset is parsed, model fitted or prediction evaluated.')


def artifact_manifest_example():
    return {'schema_version': 'pk-validation-artifact-manifest-v1',
        'purpose': 'validation_planning',
        'artifacts': [{'requirement': code, 'file': None, 'expected_sha256': None,
                       'source_reference': None, 'access_basis': None, 'notes': None}
                      for code, _, _ in REQUIREMENTS]}


def _validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {'schema_version','purpose','artifacts'}:
        raise ValueError('Expected only schema_version, purpose and artifacts in the manifest.')
    if manifest['schema_version'] != 'pk-validation-artifact-manifest-v1' or manifest['purpose'] != 'validation_planning':
        raise ValueError('Unsupported artifact manifest schema or purpose.')
    if not isinstance(manifest['artifacts'], list) or len(manifest['artifacts']) > len(REQUIREMENTS):
        raise ValueError('Artifacts must be a bounded list of known requirements.')
    allowed = {code for code, _, _ in REQUIREMENTS}
    seen = set()
    for row in manifest['artifacts']:
        if not isinstance(row, dict) or set(row) != {'requirement','file','expected_sha256','source_reference','access_basis','notes'}:
            raise ValueError('Each artifact must use exactly the example fields.')
        code = row['requirement']
        if not isinstance(code,str) or code not in allowed or code in seen:
            raise ValueError('Unknown or duplicate artifact requirement.')
        seen.add(code)
        for key in ('file','source_reference','access_basis','notes'):
            if row[key] is not None and (not isinstance(row[key],str) or not row[key].strip() or len(row[key]) > 2000):
                raise ValueError(f'{key} must be null or bounded nonblank text.')
        sha = row['expected_sha256']
        if sha is not None and (not isinstance(sha,str) or re.fullmatch(r'[0-9a-f]{64}',sha) is None):
            raise ValueError('Expected SHA256 must be null or 64 lowercase hexadecimal characters.')
        if row['file'] is None and sha is not None:
            raise ValueError('A digest without a file is not a local artifact.')


def artifact_inventory(manifest, base_directory):
    _validate_manifest(manifest)
    packet = transcription_review_packet()
    use = intended_use_report()
    root = Path(base_directory).resolve()
    supplied = {row['requirement']: row for row in manifest['artifacts']}
    rows = []
    for code, label, needed in REQUIREMENTS:
        row = copy.deepcopy(supplied.get(code, {'requirement':code,'file':None,'expected_sha256':None,
                                                'source_reference':None,'access_basis':None,'notes':None}))
        status, actual, size = 'not_supplied', None, None
        if row['file'] is not None:
            # Read only files beneath the manifest directory. Absolute paths and
            # symlink escapes are rejected before reading any artifact bytes.
            relative = Path(row['file'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Artifact paths must be relative and remain beneath the manifest directory.')
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError('Artifact path escapes the manifest directory.')
            if not path.exists():
                status = 'file_missing'
            elif not path.is_file():
                status = 'not_regular_file'
            else:
                try:
                    with path.open('rb') as handle:
                        actual = hashlib.file_digest(handle,'sha256').hexdigest()
                    size = path.stat().st_size
                    if row['expected_sha256'] is None:
                        status = 'present_digest_not_bound'
                    elif actual != row['expected_sha256']:
                        status = 'digest_mismatch'
                    else:
                        status = 'present_digest_matches'
                except OSError:
                    status = 'file_unreadable'
        rows.append({'requirement':code,'label':label,'evidence_needed':needed,
                     'declared_artifact':row,'file_status':status,'actual_sha256':actual,'size_bytes':size,
                     'access_status':'not_verified','provenance_status':'not_verified',
                     'scientific_suitability':'not_assessed','accepted_for_validation':False})
    report = {'schema_version':'pk-validation-artifact-inventory-v1','method_version':METHOD,
        'status':'validation_evidence_not_established','manifest_sha256':digest(manifest),
        'source_reference':copy.deepcopy(packet['source_reference']),
        'model_contract_binding':copy.deepcopy(packet['contract_binding']),
        'intended_use_contract_sha256':use['contract_sha256'],
        'artifacts':rows,'file_status_counts':{s:sum(r['file_status']==s for r in rows) for s in sorted({r['file_status'] for r in rows})},
        'accepted_artifact_count':0,'access_rights_verified':False,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'governance_approval':None,'database_writes_performed':False,'ode_solver_rerun':False,
        'network_refresh_performed':False,'data_parsing_performed':False,'limitation':LIMITATION}
    report['report_sha256'] = digest(report)
    return report


def _no_duplicate_keys(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key.')
        result[key] = value
    return result


def register_pk_validation_artifact_commands(app):
    @app.cli.command('pk-validation-artifacts')
    @click.option('--manifest', type=click.Path(exists=True, dir_okay=False, path_type=Path))
    @click.option('--example', is_flag=True, help='Show a blank artifact manifest; contains no observations or approvals.')
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(manifest, example, json_output, output):
        """Inventory local files for later source reproduction and external validation."""
        if bool(manifest) == example:
            raise click.ClickException('Choose exactly one of --manifest or --example.')
        try:
            if example:
                report = artifact_manifest_example()
            else:
                with manifest.open('rb') as handle:
                    raw = handle.read(MAX_MANIFEST_BYTES + 1)
                if len(raw) > MAX_MANIFEST_BYTES:
                    raise ValueError('Artifact manifest exceeds the 128 KiB limit.')
                data = json.loads(raw,object_pairs_hook=_no_duplicate_keys)
                report = artifact_inventory(data,manifest.parent)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported validation-artifact document: {output}')
            elif json_output or example:
                click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Hughes validation artifacts | {report['status']}")
                for row in report['artifacts']:
                    click.echo(f"[{row['file_status'].upper()}] {row['label']}")
                click.echo('Accepted artifacts: 0 | Clinical prediction validated: false | Patient simulation ready: false')
                click.echo(LIMITATION)
        except (ValueError,OSError,UnicodeError) as exc:
            raise click.ClickException(str(exc)) from exc
