"""Patient Lab 2.1f: immutable saved Kim 2026 runs, verified on every read without re-running the model.

Kim runs live in their own table rather than in educational_pk_run, whose readers and pages expect the
Hughes report structure (preflight review, binding, transit points). A saved Kim run archives the full
report, which itself carries the covariate estimate, the CL/F equation reading and its evidence, and every
warning shown at save time. Saving never establishes clinical validity.
"""
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
from .treatment_requests import _read_json, validate_treatment_request
from .kim_model import CL_FORMS, PREDICTION_TYPE, RUN_SCHEMA, calculate_kim_pk

SCHEMA = 'saved-kim-pk-run-v1'
SCOPE_NOTE = ('Immutable synthetic educational Kim 2026 calculation. The CL/F equation reading is an unresolved '
              'assumption recorded with the run. Saving does not establish clinical validity.')


class KimPKRun(db.Model):
    __tablename__ = 'kim_pk_run'
    id: Mapped[int] = mapped_column(primary_key=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey('patient_state_revision.id', ondelete='RESTRICT'), index=True)
    title: Mapped[str] = mapped_column(String(160))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime)
    schema_version: Mapped[str] = mapped_column(String(40))
    report_sha256: Mapped[str] = mapped_column(String(64))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    save_key: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)


@event.listens_for(KimPKRun, 'before_update')
@event.listens_for(KimPKRun, 'before_delete')
def _immutable_run(mapper, connection, target):
    raise ValueError('Saved Kim runs cannot be updated or deleted through the ORM; save a new run.')


def kim_runs_ready():
    if not inspect(db.engine).has_table(KimPKRun.__tablename__):
        raise ValueError('Kim run table is missing. Apply the Patient Lab 2.1f migration with db upgrade.')


def _hashed(payload, label):
    if not isinstance(payload, dict):
        raise ValueError(f'{label} format is invalid.')
    body = copy.deepcopy(payload)
    sha = body.pop('report_sha256', None)
    if not isinstance(sha, str) or digest(body) != sha:
        raise ValueError(f'{label} checksum failed.')
    return sha


def _title(title):
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160 or any(ord(c) < 32 for c in title):
        raise ValueError('Enter a one-line title of 1–160 characters.')
    return title.strip()


def read_kim_pk_run(run_id):
    """Check the frozen run against its checksums and its patient-state anchor; never re-run the model."""
    _positive_id(run_id, 'Run ID')
    kim_runs_ready()
    row = db.session.get(KimPKRun, run_id)
    if row is None:
        return None
    try:
        p = row.payload
        report = p['report']
        estimate = report['covariate_estimate']
        revision = read_revision(row.revision_id)
        if revision is None:
            raise ValueError('Saved Kim run patient-state anchor is missing.')
        report_sha = _hashed(report, 'Saved Kim calculation')
        estimate_sha = _hashed(estimate, 'Saved Kim covariate estimate')
        request = report['treatment_request']
        if (row.schema_version != SCHEMA or p['schema_version'] != SCHEMA
                or p['revision_id'] != row.revision_id or p['title'] != row.title
                or p['saved_at_utc'] != row.created_at_utc.isoformat() + 'Z'
                or digest(p) != row.payload_sha256 or report_sha != row.report_sha256
                or report['schema_version'] != RUN_SCHEMA or report['revision_id'] != row.revision_id
                or report['covariate_estimate_sha256'] != estimate_sha
                or estimate['state_sha256'] != revision.state_sha256
                or report['cl_form'] not in CL_FORMS or p['cl_form'] != report['cl_form']
                or report['prediction_type'] != PREDICTION_TYPE
                or validate_treatment_request(request) != request
                or report['status'] != 'completed' or report['execution_blockers'] != []
                or report['clinical_prediction_validated'] is not False
                or report['ready_for_patient_simulation'] is not False
                or not report['times_h'] or len(report['times_h']) != len(report['total_concentration_ng_ml'])
                or len(report['times_h']) != len(report['unbound_concentration_ng_ml'])
                or p['identity'] != {'revision_id': row.revision_id, 'title': row.title, 'report_sha256': report_sha}
                or digest(p['identity']) != row.save_key):
            raise ValueError('Saved Kim run format, source anchor or integrity check failed.')
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError('Saved Kim run format or integrity check failed.') from exc
    return row


def save_kim_pk_run(revision_id, request, disease_code, cl_form, *, title='Kim 2026 educational run'):
    """Calculate with Kim 2026 for a saved revision and archive the full report; blocked runs are not saved."""
    _positive_id(revision_id, 'Revision ID')
    kim_runs_ready()
    title = _title(title)
    report = calculate_kim_pk(revision_id, request, disease_code, cl_form)
    if report['status'] != 'completed':
        raise ValueError('Calculation blocked; no run saved: ' + ', '.join(b['code'] for b in report['execution_blockers']))
    identity = {'revision_id': revision_id, 'title': title, 'report_sha256': report['report_sha256']}
    key = digest(identity)
    existing = db.session.scalar(select(KimPKRun).where(KimPKRun.save_key == key))
    if existing is not None:
        return read_kim_pk_run(existing.id)
    created = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {'schema_version': SCHEMA, 'revision_id': revision_id, 'title': title,
               'saved_at_utc': created.isoformat() + 'Z', 'identity': identity, 'cl_form': cl_form,
               'report': copy.deepcopy(report), 'scope_note': SCOPE_NOTE}
    row = KimPKRun(revision_id=revision_id, title=title, created_at_utc=created, schema_version=SCHEMA,
                   report_sha256=report['report_sha256'], payload_sha256=digest(payload), save_key=key, payload=payload)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        existing = db.session.scalar(select(KimPKRun).where(KimPKRun.save_key == key))
        if existing is not None:
            return read_kim_pk_run(existing.id)
        raise ValueError('Kim run save conflicted; no replacement was performed.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return row


def export_kim_pk_run(run_id):
    row = read_kim_pk_run(run_id)
    if row is None:
        raise ValueError('Saved Kim run does not exist.')
    return {'run_id': row.id, 'payload_sha256': row.payload_sha256, 'payload': copy.deepcopy(row.payload)}


def register_kim_pk_run_commands(app):
    @app.cli.command('patient-pk-save-kim')
    @click.option('--revision-id', type=click.IntRange(min=1), required=True)
    @click.option('--treatment-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
    @click.option('--disease-code', type=click.Choice(('MM', 'CLL', 'AML', 'ALL', 'OTHER', 'UNKNOWN')), required=True)
    @click.option('--cl-form', type=click.Choice(CL_FORMS), required=True, help='Kim CL/F equation reading; no default.')
    @click.option('--title', default='Kim 2026 educational run', show_default=True)
    def save_command(revision_id, treatment_file, disease_code, cl_form, title):
        """Calculate with Kim 2026 and save an immutable run with its estimate and assumption."""
        try:
            row = save_kim_pk_run(revision_id, _read_json(treatment_file), disease_code, cl_form, title=title)
        except (ValueError, OSError, UnicodeError, SQLAlchemyError) as exc:
            db.session.rollback()
            raise click.ClickException(str(exc)) from exc
        click.echo(f'Kim run ID: {row.id}\nPatient-state record ID: {row.revision_id}\nCL/F reading: {cl_form}\n'
                   f'Report SHA256: {row.report_sha256}\nClinical prediction validated: false')

    @app.cli.command('patient-pk-export-kim')
    @click.option('--id', 'run_id', type=click.IntRange(min=1), required=True)
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def export_command(run_id, output):
        """Export a verified saved Kim run without re-running the model."""
        try:
            result = export_kim_pk_run(run_id)
            text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if output:
                with output.open('x', encoding='utf-8') as handle:
                    handle.write(text)
                click.echo(f'Exported saved Kim run: {output}')
            else:
                click.echo(text, nl=False)
        except (ValueError, OSError, UnicodeError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
