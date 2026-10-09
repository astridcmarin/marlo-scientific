"""Explicit archived-workflow checkpoint with unresolved scientific evidence."""
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import platform
import click
from .patient_lab_checkpoint import patient_lab_checkpoint
from .pk_validation_gap import validation_gap_report
from .pk_transcription_review import transcription_review_packet
from .patient_lab_intended_use import intended_use_report
from .pk_validation_artifacts import (
 artifact_manifest_example, artifact_inventory, MAX_MANIFEST_BYTES, _no_duplicate_keys)
from .patient_state import digest

METHOD = 'patient-lab-phase-checkpoint-v1.0'
LIMITATION = ('Reproducibility evidence snapshot for an explicit educational archive. '
              'A software pass does not establish independent source review, governance approval, '
              'accepted validation data, predictive validity, patient applicability or deployment readiness.')
CODE_MODULES = ('patient_lab_checkpoint','pk_validation_gap','pk_transcription_review',
 'patient_lab_intended_use','pk_validation_artifacts','educational_pk','educational_pk_runs',
 'educational_pk_audit','educational_pk_metrics','published_transit_reference',
 'pk_parameter_reference','model_coverage','transit_kernel','transit_regimen','patient_lab_milestone')


def _environment_snapshot():
    packages = {}
    for package in ('Flask','SQLAlchemy','Flask-SQLAlchemy','Flask-Migrate'):
        try: packages[package] = version(package)
        except PackageNotFoundError: packages[package] = None
    root = Path(__file__).parent
    code = {name + '.py': hashlib.sha256((root/(name+'.py')).read_bytes()).hexdigest() for name in CODE_MODULES}
    return {'python_version':platform.python_version(),'python_implementation':platform.python_implementation(),
        'system':platform.system(),'machine':platform.machine(),'package_versions':packages,
        'selected_code_sha256':code,
        'scope':'Selected loaded project files and runtime versions only; not a full dependency lock, git checkout or complete environment reproduction.'}


def phase_checkpoint(cohort_id,scenario_id,revision_id,run_id,*,manifest_path=None):
    software = patient_lab_checkpoint(cohort_id,scenario_id,revision_id,run_id)
    report = {'schema_version':'patient-lab-phase-checkpoint-v1','method_version':METHOD,
        'selected':software['selected'],'status':'phase_checkpoint_failed',
        'software_checkpoint':software,'validation_gap':None,'transcription_review':None,
        'intended_use':None,'artifact_inventory':None,'environment':None,
        'scientific_status':'clinical_validation_not_established','blockers':[],
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'independent_review_completed':False,'governance_approval':None,
        'database_writes_performed':False,'ode_solver_rerun':False,'network_refresh_performed':False,
        'limitation':LIMITATION}
    if software['status']=='software_checkpoint_failed':
        report['blockers'].append('selected_workflow_software_checks_failed')
    else:
        gap = validation_gap_report(run_id)
        packet = transcription_review_packet()
        use = intended_use_report()
        if manifest_path is None:
            manifest, directory = artifact_manifest_example(), Path('.')
        else:
            path = Path(manifest_path)
            with path.open('rb') as handle:
                raw = handle.read(MAX_MANIFEST_BYTES+1)
            if len(raw)>MAX_MANIFEST_BYTES:
                raise ValueError('Artifact manifest exceeds the 128 KiB limit.')
            manifest, directory = json.loads(raw,object_pairs_hook=_no_duplicate_keys), path.parent
        inventory = artifact_inventory(manifest,directory)
        report.update(validation_gap=gap,transcription_review=packet,intended_use=use,
                      artifact_inventory=inventory,environment=_environment_snapshot())
        report['artifact_manifest_supplied'] = manifest_path is not None
        report['blockers'] = [g['code'] for g in gap['gates'] if g['status']!='passed']
        file_failures = {'file_missing','not_regular_file','file_unreadable','digest_mismatch'}
        if any(row['file_status'] in file_failures for row in inventory['artifacts']):
            report['blockers'].append('declared_artifact_file_integrity_failed')
        compatible = all(gap['contract_matches'].values())
        math_ok = not any(g['status']=='failed' for g in gap['gates'])
        artifacts_ok = 'declared_artifact_file_integrity_failed' not in report['blockers']
        if compatible and math_ok and artifacts_ok:
            report['status'] = 'software_checkpoint_passed_science_pending'
    report['report_sha256'] = digest(report)
    return report


def register_patient_lab_milestone_commands(app):
    @app.cli.command('patient-lab-phase-checkpoint')
    @click.option('--cohort-id',type=click.IntRange(min=1),required=True)
    @click.option('--scenario-id',type=click.IntRange(min=1),required=True)
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--run-id',type=click.IntRange(min=1),required=True)
    @click.option('--manifest',type=click.Path(exists=True,dir_okay=False,path_type=Path))
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(cohort_id,scenario_id,revision_id,run_id,manifest,json_output,output):
        """Snapshot selected software checks, runtime and pending scientific evidence."""
        try:
            report=phase_checkpoint(cohort_id,scenario_id,revision_id,run_id,manifest_path=manifest)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported Patient Lab phase checkpoint: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Patient Lab phase checkpoint | {report['status']}")
                click.echo(f"Selected IDs: {report['selected']}")
                click.echo(f"Software: {report['software_checkpoint']['status']} | Science: {report['scientific_status']}")
                click.echo('Pending/failed evidence: '+', '.join(report['blockers']))
                click.echo('Clinical prediction validated: false | Patient simulation ready: false')
                click.echo(LIMITATION)
            if report['status']=='phase_checkpoint_failed':raise click.exceptions.Exit(1)
        except (ValueError,OSError,UnicodeError) as exc:raise click.ClickException(str(exc)) from exc
