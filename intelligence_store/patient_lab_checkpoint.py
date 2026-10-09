"""Read-only software/mathematical checkpoint; no clinical-readiness inference."""
import json
from pathlib import Path
import click
from sqlalchemy import inspect,text
from sqlalchemy.exc import SQLAlchemyError
from .extensions import db
from .saved_scenarios import read_scenario
from .patient_state_revisions import read_revision
from .educational_pk_runs import read_pk_run
from .educational_pk_audit import audit_pk_run
from .educational_pk_metrics import summarize_pk_run
from .educational_pk_sensitivity import clearance_sensitivity
from .validation import validate_platform
from .patient_state import digest

METHOD='patient-lab-software-checkpoint-v1.0'
LIMITATION='Checks storage names, selected source lineage, platform integrity and educational mathematics. Does not establish clinical validation, verified covariates, observed-data fit, uncertainty coverage, label currency, security or deployment readiness.'


def patient_lab_checkpoint(cohort_id,scenario_id,revision_id,run_id,*,clearance_factor=None,assumption_note=None):
    ids={'cohort_id':cohort_id,'scenario_id':scenario_id,'revision_id':revision_id,'run_id':run_id}
    if any(type(value) is not int or value<1 for value in ids.values()):
        raise ValueError('Supply positive integer cohort, scenario, revision and run IDs.')
    if (clearance_factor is None)!=(assumption_note is None):
        raise ValueError('Optional sensitivity requires both clearance_factor and assumption_note.')
    report={'schema_version':'patient-lab-software-checkpoint-v1','method_version':METHOD,'selected':ids,
        'checks':[],'migration_heads':None,'source_hashes':None,'platform':None,'audit':None,'metrics':None,
        'sensitivity':None,'sensitivity_requested':clearance_factor is not None,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'ode_solver_rerun':False,'database_writes_performed':False,'network_refresh_performed':False,
        'limitation':LIMITATION,'migration_check_scope':'Recorded database revisions only; migration files, graph, types, constraints and indexes are not validated.'}
    def add(code,status,detail):report['checks'].append({'code':code,'status':status,'detail':detail})
    def finish():
        statuses=[c['status'] for c in report['checks']]
        report['status']='software_checkpoint_failed' if 'failed' in statuses else 'software_checkpoint_passed_with_warnings' if 'warning' in statuses else 'software_checkpoint_passed'
        report['report_sha256']=digest(report)
        return report
    try:
        inspector=inspect(db.engine);tables=set(inspector.get_table_names())
        missing_tables=[];missing_columns={}
        for table in db.metadata.sorted_tables:
            if table.name not in tables:missing_tables.append(table.name);continue
            absent=sorted(set(table.columns.keys())-{c['name'] for c in inspector.get_columns(table.name)})
            if absent:missing_columns[table.name]=absent
        if missing_tables or missing_columns:
            add('model_storage_names','failed',{'missing_tables':missing_tables,'missing_columns':missing_columns})
            return finish()
        add('model_storage_names','passed',f'{len(db.metadata.tables)} required model tables and their model column names are present. Types, indexes and constraints are not implied.')
        if 'alembic_version' in tables and 'version_num' in {c['name'] for c in inspector.get_columns('alembic_version')}:
            report['migration_heads']=sorted(db.session.scalars(text('SELECT version_num FROM alembic_version')))
            add('recorded_migration_revisions','passed' if report['migration_heads'] else 'warning',
                'Recorded database revision values were read; they are not compared against migration files or an expected head.')
        else:add('recorded_migration_revisions','warning','No readable Alembic revision metadata. Model table/column presence does not prove migration completion.')
        scenario=read_scenario(scenario_id)
        if scenario is None:raise ValueError('Selected scenario does not exist.')
        if scenario.payload['inputs']['cohort_id']!=cohort_id:
            raise ValueError('Selected scenario is not anchored to the selected cohort.')
        revision=read_revision(revision_id)
        if revision is None or revision.scenario_id!=scenario_id:
            raise ValueError('Selected patient-state record does not belong to the selected scenario.')
        run=read_pk_run(run_id)
        if run is None or run.revision_id!=revision_id:
            raise ValueError('Selected educational run does not belong to the selected patient-state record.')
        report['source_hashes']={'scenario_payload_sha256':scenario.payload_sha256,
            'revision_payload_sha256':revision.payload_sha256,'state_sha256':revision.state_sha256,
            'run_payload_sha256':run.payload_sha256,'run_report_sha256':run.report_sha256}
        add('selected_source_lineage','passed','Chosen scenario, revision and archive verified with their stored lineage; no latest record was substituted.')
        platform=validate_platform(cohort_id);report['platform']=platform
        add('platform_integrity','failed' if platform['status']=='failed' else 'warning' if platform['status']=='passed_with_warnings' else 'passed',
            'Full platform-check included. Its saved-record integrity checks can inspect records beyond the selected workflow.')
        audit=audit_pk_run(run_id);report['audit']=audit
        add('selected_run_mathematics','passed' if audit['status']=='mathematical_checks_passed' else 'failed',audit['status'])
        metrics=summarize_pk_run(run_id);report['metrics']=metrics
        add('selected_run_sampled_metrics','passed' if metrics['status']=='sampled_metrics_available' else 'failed',metrics['status'])
        if clearance_factor is not None:
            sensitivity=clearance_sensitivity(run_id,clearance_factor,assumption_note);report['sensitivity']=sensitivity
            add('declared_clearance_sensitivity','passed' if sensitivity['status']=='sensitivity_available' else 'failed',sensitivity['status'])
        else:add('declared_clearance_sensitivity','not_requested','No assumption or factor was invented for this checkpoint.')
    except (ValueError,KeyError,TypeError) as exc:add('checkpoint_execution','failed',str(exc))
    except SQLAlchemyError:
        db.session.rollback();add('checkpoint_execution','failed','Storage could not be read. No repair or migration was attempted.')
    return finish()


def register_patient_lab_checkpoint_commands(app):
    @app.cli.command('patient-lab-checkpoint')
    @click.option('--cohort-id',type=click.IntRange(min=1),required=True)
    @click.option('--scenario-id',type=click.IntRange(min=1),required=True)
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--run-id',type=click.IntRange(min=1),required=True)
    @click.option('--clearance-factor',type=float)
    @click.option('--assumption-note')
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(cohort_id,scenario_id,revision_id,run_id,clearance_factor,assumption_note,json_output,output):
        """Check an explicit educational workflow without changing stored records."""
        try:
            report=patient_lab_checkpoint(cohort_id,scenario_id,revision_id,run_id,
                clearance_factor=clearance_factor,assumption_note=assumption_note)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported Patient Lab checkpoint: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Patient Lab | {report['status']} | Cohort #{cohort_id}, scenario #{scenario_id}, record #{revision_id}, run #{run_id}")
                for check in report['checks']:click.echo(f"[{check['status'].upper()}] {check['code']}: {check['detail']}")
                click.echo(f"Recorded migration revisions: {report['migration_heads']}")
                click.echo(LIMITATION)
            if report['status']=='software_checkpoint_failed':raise click.exceptions.Exit(1)
        except (ValueError,OSError,UnicodeError) as exc:raise click.ClickException(str(exc)) from exc
