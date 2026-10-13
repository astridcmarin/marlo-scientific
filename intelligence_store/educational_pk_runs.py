"""Immutable educational calculation snapshots; never clinical validation records."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import click
from sqlalchemy import DateTime, ForeignKey, JSON, String, event, inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column
from .extensions import db
from .patient_state import digest
from .patient_state_revisions import read_revision, _positive_id
from .educational_pk import calculate_educational_pk
from .treatment_requests import _read_json, validate_treatment_request
from .pk_model_inputs import validate_model_inputs
from .covariate_estimation import to_hughes_model_inputs, WEIGHT_BASES
from .estimated_pk import calculate_estimated_pk, PREDICTION_TYPE

SCHEMA='saved-educational-pk-run-v1'
# v2 adds the covariate estimate that produced the model inputs (Patient Lab 2.0d).
SCHEMA_V2='saved-educational-pk-run-v2'
SCHEMAS=(SCHEMA,SCHEMA_V2)


class EducationalPKRun(db.Model):
    __tablename__='educational_pk_run'
    id: Mapped[int]=mapped_column(primary_key=True)
    revision_id: Mapped[int]=mapped_column(ForeignKey('patient_state_revision.id',ondelete='RESTRICT'),index=True)
    title: Mapped[str]=mapped_column(String(160))
    created_at_utc: Mapped[datetime]=mapped_column(DateTime)
    schema_version: Mapped[str]=mapped_column(String(40))
    report_sha256: Mapped[str]=mapped_column(String(64))
    payload_sha256: Mapped[str]=mapped_column(String(64))
    save_key: Mapped[str]=mapped_column(String(64),unique=True)
    payload: Mapped[dict]=mapped_column(JSON)


@event.listens_for(EducationalPKRun,'before_update')
@event.listens_for(EducationalPKRun,'before_delete')
def _immutable_run(mapper,connection,target):
    raise ValueError('Saved educational PK runs cannot be updated or deleted through the ORM; save a new run.')


def runs_ready():
    if not inspect(db.engine).has_table(EducationalPKRun.__tablename__):
        raise ValueError('Educational PK run table is missing. Apply the Step 45 migration with db upgrade.')


def _hashed(payload,label):
    if not isinstance(payload,dict):raise ValueError(f'{label} format is invalid.')
    body=copy.deepcopy(payload);sha=body.pop('report_sha256',None)
    if not isinstance(sha,str) or digest(body)!=sha:raise ValueError(f'{label} checksum failed.')
    return sha


def read_pk_run(run_id):
    """Check frozen content and source anchors without loading current model catalogs or solving."""
    _positive_id(run_id,'Run ID');runs_ready()
    row=db.session.get(EducationalPKRun,run_id)
    if row is None:return None
    try:
        p=row.payload;report=p['report'];review=report['preflight_review'];binding=review['binding']
        revision=read_revision(row.revision_id)
        if revision is None:raise ValueError('Saved run patient-state anchor is missing.')
        report_sha=_hashed(report,'Saved calculation')
        review_sha=_hashed(review,'Saved preflight review')
        treatment=review['treatment_request_preview']
        _hashed(treatment,'Saved treatment request preview')
        inputs=review['explicit_model_inputs'];request=treatment['request']
        if (row.schema_version not in SCHEMAS or p['schema_version']!=row.schema_version
            or p['revision_id']!=row.revision_id or p['title']!=row.title
            or p['saved_at_utc']!=row.created_at_utc.isoformat()+'Z'
            or digest(p)!=row.payload_sha256 or report_sha!=row.report_sha256
            or report['preflight_report_sha256']!=review_sha
            or review['binding_sha256']!=digest(binding)
            or binding['revision_id']!=revision.id
            or binding['revision_payload_sha256']!=revision.payload_sha256
            or binding['state_sha256']!=revision.state_sha256
            or binding['scenario_id']!=revision.scenario_id
            or binding['scenario_payload_sha256']!=revision.payload['scenario_payload_sha256']
            or review['captured_state']!=revision.payload['state']
            or binding['model_inputs_sha256']!=digest(inputs)
            or validate_model_inputs(inputs)!=inputs
            or validate_treatment_request(request)!=request
            or binding['treatment_request_sha256']!=digest(request)
            or treatment['request_sha256']!=digest(request)
            or review['declared_disease_context']['code']!=binding['declared_disease_code']
            or report['status']!='completed_educational_calculation'
            or report['simulation_status']!='completed_educational_calculation'
            or report['clinical_prediction_validated'] is not False
            or report['ready_for_patient_simulation'] is not False
            or not isinstance(report['points'],list) or not report['points']
            or report['execution_blockers']!=[]
            or p['identity']!={'revision_id':row.revision_id,'title':row.title,'report_sha256':report_sha}
            or digest(p['identity'])!=row.save_key):
            raise ValueError('Saved educational run format, source anchor or integrity check failed.')
        if row.schema_version==SCHEMA_V2:_verify_estimate(p,inputs,revision)
    except (KeyError,TypeError,AttributeError,RecursionError) as exc:
        raise ValueError('Saved educational run format or integrity check failed.') from exc
    return row


def _verify_estimate(payload,inputs,revision):
    """A v2 run must carry the unmodified estimate that produced its inputs, bound to the same revision state."""
    estimate=payload['covariate_estimate']
    _hashed(estimate,'Saved covariate estimate')
    if (estimate.get('state_sha256')!=revision.state_sha256
        or payload['weight_basis']!=estimate['weight_basis']
        or payload['prediction_type']!=PREDICTION_TYPE
        or to_hughes_model_inputs(estimate)!=inputs):
        raise ValueError('Saved covariate estimate does not match the run inputs or patient-state anchor.')


def _title(title):
    if not isinstance(title,str) or not 1<=len(title.strip())<=160 or any(ord(c)<32 for c in title):
        raise ValueError('Enter a one-line title of 1–160 characters.')
    return title.strip()


def save_pk_run(revision_id,inputs,request,disease_code,*,title='Educational PK run'):
    """Calculate from explicit inputs; refuse blocked reports and caller-supplied report imports."""
    _positive_id(revision_id,'Revision ID');runs_ready()
    title=_title(title)
    report=calculate_educational_pk(revision_id,inputs,request,disease_code)
    return _store(revision_id,title,report,SCHEMA,{})


def save_estimated_pk_run(revision_id,weight_basis,request,disease_code,*,title='Estimated educational PK run'):
    """Estimate covariates from the revision, calculate, and archive the estimate with the run (v2)."""
    _positive_id(revision_id,'Revision ID');runs_ready()
    title=_title(title)
    result=calculate_estimated_pk(revision_id,weight_basis,request,disease_code)
    if result['calculation'] is None:
        raise ValueError('Calculation blocked; no run saved: missing estimator inputs '+', '.join(result['covariate_estimate']['missing_fields']))
    return _store(revision_id,title,result['calculation'],SCHEMA_V2,
                  {'covariate_estimate':copy.deepcopy(result['covariate_estimate']),'weight_basis':weight_basis,
                   'prediction_type':result['prediction_type']})


def _store(revision_id,title,report,schema,extra):
    if report['status']!='completed_educational_calculation':
        raise ValueError('Calculation blocked; no run saved: '+', '.join(b['code'] for b in report['execution_blockers']))
    identity={'revision_id':revision_id,'title':title,'report_sha256':report['report_sha256']}
    key=digest(identity)
    existing=db.session.scalar(select(EducationalPKRun).where(EducationalPKRun.save_key==key))
    if existing is not None:return read_pk_run(existing.id)
    created=datetime.now(timezone.utc).replace(tzinfo=None)
    payload={'schema_version':schema,'revision_id':revision_id,'title':title,'saved_at_utc':created.isoformat()+'Z',
             'identity':identity,'report':copy.deepcopy(report),
             'scope_note':'Immutable synthetic educational calculation snapshot. Saving does not establish clinical validity.',
             **extra}
    row=EducationalPKRun(revision_id=revision_id,title=title,created_at_utc=created,schema_version=schema,
        report_sha256=report['report_sha256'],payload_sha256=digest(payload),save_key=key,payload=payload)
    db.session.add(row)
    try:db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        existing=db.session.scalar(select(EducationalPKRun).where(EducationalPKRun.save_key==key))
        if existing is not None:return read_pk_run(existing.id)
        raise ValueError('Educational run save conflicted; no replacement was performed.') from exc
    except SQLAlchemyError:
        db.session.rollback();raise
    return row


def export_pk_run(run_id):
    row=read_pk_run(run_id)
    if row is None:raise ValueError('Saved educational PK run does not exist.')
    return {'run_id':row.id,'payload_sha256':row.payload_sha256,'payload':copy.deepcopy(row.payload)}


def register_educational_pk_run_commands(app):
    @app.cli.command('patient-pk-save')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--inputs-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--treatment-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--disease-code',type=click.Choice(('MM','CLL','AML','ALL','OTHER','UNKNOWN')),required=True)
    @click.option('--title',default='Educational PK run',show_default=True)
    def save_command(revision_id,inputs_file,treatment_file,disease_code,title):
        """Calculate and explicitly save an immutable educational result."""
        try:row=save_pk_run(revision_id,_read_json(inputs_file),_read_json(treatment_file),disease_code,title=title)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:
            db.session.rollback();raise click.ClickException(str(exc)) from exc
        click.echo(f'Educational PK run ID: {row.id}\nPatient-state record ID: {row.revision_id}\nReport SHA256: {row.report_sha256}\nClinical prediction validated: false')

    @app.cli.command('patient-pk-save-estimated')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    @click.option('--weight-basis',type=click.Choice(WEIGHT_BASES),required=True)
    @click.option('--treatment-file',type=click.Path(exists=True,dir_okay=False,path_type=Path),required=True)
    @click.option('--disease-code',type=click.Choice(('MM','CLL','AML','ALL','OTHER','UNKNOWN')),required=True)
    @click.option('--title',default='Estimated educational PK run',show_default=True)
    def save_estimated_command(revision_id,weight_basis,treatment_file,disease_code,title):
        """Estimate covariates from the revision, calculate, and save the run with its estimate."""
        try:row=save_estimated_pk_run(revision_id,weight_basis,_read_json(treatment_file),disease_code,title=title)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:
            db.session.rollback();raise click.ClickException(str(exc)) from exc
        click.echo(f'Educational PK run ID: {row.id}\nPatient-state record ID: {row.revision_id}\nWeight basis: {weight_basis}\nReport SHA256: {row.report_sha256}\nClinical prediction validated: false')

    @app.cli.command('patient-pk-list')
    @click.option('--revision-id',type=click.IntRange(min=1),required=True)
    def list_command(revision_id):
        """List verified saved runs for one patient-state record."""
        try:
            runs_ready()
            if read_revision(revision_id) is None:raise ValueError('Patient-state revision does not exist.')
            rows=list(db.session.scalars(select(EducationalPKRun).where(EducationalPKRun.revision_id==revision_id).order_by(EducationalPKRun.id)))
            for row in rows:read_pk_run(row.id)
        except (ValueError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
        for row in rows:click.echo(f'Run #{row.id} | {row.title} | {row.created_at_utc.isoformat()}Z | educational only')
        click.echo(f'{len(rows)} saved educational runs. Clinical prediction validated: false.')

    @app.cli.command('patient-pk-export')
    @click.option('--id','run_id',type=click.IntRange(min=1),required=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def export_command(run_id,output):
        """Export a verified frozen run without rerunning the solver."""
        try:
            result=export_pk_run(run_id)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(result,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported saved educational PK run: {output}')
            else:click.echo(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
