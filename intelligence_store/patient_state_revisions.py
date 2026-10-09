"""Append-only state revisions attached to existing immutable synthetic scenarios."""
import copy
from datetime import datetime, timezone
import json

import click
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, UniqueConstraint, event, inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column

from .extensions import db
from .patient_state import (VALIDATION_VERSION, digest,
                            state_from_scenario, validate_patient_state, _read_json)
from .saved_scenarios import read_scenario

REVISION_SCHEMA = 'saved-patient-state-revision-v1'


class PatientStateRevision(db.Model):
    __tablename__ = 'patient_state_revision'
    __table_args__ = (
        UniqueConstraint('scenario_id', 'revision_number', name='uq_state_scenario_revision'),
        CheckConstraint('revision_number > 0', name='ck_state_positive_revision'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey('saved_patient_scenario.id', ondelete='RESTRICT'))
    revision_number: Mapped[int] = mapped_column()
    parent_revision_id: Mapped[int | None] = mapped_column(ForeignKey('patient_state_revision.id', ondelete='RESTRICT'))
    title: Mapped[str] = mapped_column(String(160))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime)
    schema_version: Mapped[str] = mapped_column(String(40))
    state_sha256: Mapped[str] = mapped_column(String(64))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    save_key: Mapped[str] = mapped_column(String(64), unique=True)


@event.listens_for(PatientStateRevision, 'before_update')
@event.listens_for(PatientStateRevision, 'before_delete')
def _immutable_revision(mapper, connection, target):
    raise ValueError('Saved patient-state revisions cannot be updated or deleted through the ORM; append a revision.')


def revisions_ready():
    if not inspect(db.engine).has_table(PatientStateRevision.__tablename__):
        raise ValueError('Patient-state revision table is missing. Apply the Step 30 migration before saving states.')


def _positive_id(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f'{label} must be a positive integer.')


def _scenario(scenario_id):
    _positive_id(scenario_id, 'Scenario ID')
    row = read_scenario(scenario_id)
    if row is None:
        raise ValueError('Saved scenario does not exist. Save a scenario from Patient Lab first.')
    return row


def read_revision(revision_id):
    """Verify the stored state, scenario anchor and complete parent chain."""
    _positive_id(revision_id, 'Revision ID')
    revisions_ready()
    row = db.session.get(PatientStateRevision, revision_id)
    if row is None:
        return None
    scenario = _scenario(row.scenario_id)
    current, seen = row, set()
    while current is not None:
        if current.id in seen:
            raise ValueError('Patient-state revision lineage contains a cycle.')
        seen.add(current.id)
        p = current.payload
        if (not isinstance(p, dict) or current.schema_version != REVISION_SCHEMA
                or p.get('schema_version') != REVISION_SCHEMA
                or p.get('scenario_id') != row.scenario_id or current.scenario_id != row.scenario_id
                or p.get('scenario_payload_sha256') != scenario.payload_sha256
                or p.get('revision_number') != current.revision_number
                or p.get('parent_revision_id') != current.parent_revision_id
                or p.get('title') != current.title or digest(p) != current.payload_sha256
                or p.get('saved_at_utc') != current.created_at_utc.isoformat() + 'Z'
                or not isinstance(p.get('state'), dict)
                or not isinstance(p.get('validation_version'), str)
                or not p['validation_version'].strip()
                or p.get('state_sha256') != current.state_sha256
                or digest(p['state']) != current.state_sha256
                or validate_patient_state(p['state']) != p['state']
                or digest(p.get('inputs')) != current.save_key):
            raise ValueError('Saved patient-state format, source anchor or integrity check failed.')
        expected_inputs = {'scenario_id': current.scenario_id,
                           'scenario_payload_sha256': scenario.payload_sha256,
                           'parent_revision_id': current.parent_revision_id,
                           'title': current.title, 'state_sha256': current.state_sha256}
        if p.get('inputs') != expected_inputs:
            raise ValueError('Saved patient-state input provenance differs from its payload.')
        if current.parent_revision_id is None:
            if current.revision_number != 1 or p.get('parent_payload_sha256') is not None:
                raise ValueError('Patient-state first revision has invalid lineage.')
            break
        parent = db.session.get(PatientStateRevision, current.parent_revision_id)
        if (parent is None or parent.scenario_id != current.scenario_id
                or parent.revision_number != current.revision_number - 1
                or p.get('parent_payload_sha256') != parent.payload_sha256):
            raise ValueError('Patient-state parent revision is missing or inconsistent.')
        current = parent
    return row


def save_revision(scenario_id, state, *, parent_revision_id=None, title='Patient state'):
    revisions_ready()
    scenario = _scenario(scenario_id)
    if parent_revision_id is not None:
        _positive_id(parent_revision_id, 'Parent revision ID')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160 or any(ord(c) < 32 for c in title):
        raise ValueError('Enter a one-line title of 1–160 characters.')
    title = title.strip()
    canonical = validate_patient_state(state)
    state_sha = digest(canonical)
    inputs = {'scenario_id': scenario_id, 'scenario_payload_sha256': scenario.payload_sha256,
              'parent_revision_id': parent_revision_id, 'title': title, 'state_sha256': state_sha}
    key = digest(inputs)
    existing = db.session.scalar(select(PatientStateRevision).where(PatientStateRevision.save_key == key))
    if existing is not None:
        return read_revision(existing.id)
    latest = db.session.scalar(select(PatientStateRevision).where(PatientStateRevision.scenario_id == scenario_id)
                               .order_by(PatientStateRevision.revision_number.desc()).limit(1))
    if (latest.id if latest else None) != parent_revision_id:
        raise ValueError('Stale parent revision. List this scenario’s revisions and use its latest revision ID.')
    parent = read_revision(parent_revision_id) if parent_revision_id is not None else None
    created = datetime.now(timezone.utc).replace(tzinfo=None)
    number = parent.revision_number + 1 if parent else 1
    payload = {'schema_version': REVISION_SCHEMA, 'scenario_id': scenario_id,
               'scenario_payload_sha256': scenario.payload_sha256, 'revision_number': number,
               'parent_revision_id': parent_revision_id,
               'parent_payload_sha256': parent.payload_sha256 if parent else None,
               'title': title, 'saved_at_utc': created.isoformat() + 'Z',
               'validation_version': VALIDATION_VERSION, 'state': copy.deepcopy(canonical),
               'state_sha256': state_sha, 'inputs': inputs,
               'scope_note': 'Saved synthetic input state only. No simulation, organ-function interpretation or patient prediction.'}
    row = PatientStateRevision(scenario_id=scenario_id, revision_number=number,
        parent_revision_id=parent_revision_id, title=title, created_at_utc=created,
        schema_version=REVISION_SCHEMA, state_sha256=state_sha,
        payload_sha256=digest(payload), payload=payload, save_key=key)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        existing = db.session.scalar(select(PatientStateRevision).where(PatientStateRevision.save_key == key))
        if existing is not None:
            return read_revision(existing.id)
        raise ValueError('Another revision was saved concurrently. List revisions and use the latest parent ID.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return row


def export_revision(revision_id):
    row = read_revision(revision_id)
    if row is None:
        raise ValueError('Patient-state revision does not exist.')
    return {'revision_id': row.id, 'payload_sha256': row.payload_sha256,
            'payload': copy.deepcopy(row.payload)}


def register_patient_state_revision_commands(app):
    @app.cli.command('patient-state-save')
    @click.option('--scenario-id', type=click.IntRange(min=1), required=True)
    @click.option('--state-file', type=click.Path(exists=True, dir_okay=False))
    @click.option('--parent-id', type=click.IntRange(min=1))
    @click.option('--title', default='Patient state', show_default=True)
    def save_state(scenario_id, state_file, parent_id, title):
        """Explicitly save state; default input is copied from the saved scenario."""
        try:
            scenario = _scenario(scenario_id)
            if state_file:
                state = _read_json(state_file)
                if isinstance(state, dict) and state.get('schema_version') == 'patient-state-preview-v1':
                    if 'state' not in state or state.get('state_sha256') != digest(state['state']):
                        raise ValueError('Preview state digest mismatch; edit raw input instead.')
                    state = state['state']
            else:
                state = state_from_scenario(scenario.payload['analysis']['report']['profile'])
            row = save_revision(scenario_id, state, parent_revision_id=parent_id, title=title)
        except (ValueError, OSError, UnicodeError, TypeError, KeyError, RecursionError, SQLAlchemyError) as exc:
            db.session.rollback()
            raise click.ClickException(str(exc)) from exc
        click.echo(f'Patient-state revision ID: {row.id}\nScenario ID: {row.scenario_id}\nRevision: {row.revision_number}\nState SHA256: {row.state_sha256}')

    @app.cli.command('patient-state-list')
    @click.option('--scenario-id', type=click.IntRange(min=1), required=True)
    def list_states(scenario_id):
        """List verified states for an existing saved scenario."""
        try:
            revisions_ready();_scenario(scenario_id)
            rows = list(db.session.scalars(select(PatientStateRevision).where(PatientStateRevision.scenario_id == scenario_id)
                                           .order_by(PatientStateRevision.revision_number)))
            for row in rows:
                read_revision(row.id)
            click.echo(f'Scenario {scenario_id}: {len(rows)} patient-state revisions')
            for row in rows:
                click.echo(f'ID {row.id} | revision {row.revision_number} | parent {row.parent_revision_id} | {row.title}')
        except (ValueError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc

    @app.cli.command('patient-state-export')
    @click.option('--id', 'revision_id', type=click.IntRange(min=1), required=True)
    def export_state(revision_id):
        """Print a verified frozen revision as complete JSON."""
        try:
            click.echo(json.dumps(export_revision(revision_id), indent=2, ensure_ascii=False, allow_nan=False))
        except (ValueError, TypeError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
