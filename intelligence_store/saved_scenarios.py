"""Explicitly saved synthetic analyses, read without consulting live source data."""
import copy
from datetime import datetime, timezone
import json
import re
import click
from sqlalchemy import DateTime, JSON, String, inspect, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import SQLAlchemyError
from .extensions import db
from .models import TrialSnapshot, utc_now
from .summaries import summarize_cohort
from .patient_scenarios import summarize_scenario, validate_scenario
from .regulatory import digest

SCHEMA_VERSION = 'saved-synthetic-scenario-v1.0'


class SavedPatientScenario(db.Model):
    __tablename__ = 'saved_patient_scenario'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    schema_version: Mapped[str] = mapped_column(String(40))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    save_key: Mapped[str] = mapped_column(String(64), unique=True)


def scenarios_ready():
    if not inspect(db.engine).has_table(SavedPatientScenario.__tablename__):
        raise ValueError('Saved scenario table is missing. Generate and apply the Step 21 migration in START_HERE.md.')


def analyze_for_save(cohort_id, profile):
    if type(cohort_id) is not int or cohort_id < 1:
        raise ValueError('Choose a complete saved cohort.')
    profile = validate_scenario(profile)
    summary = summarize_cohort(cohort_id)
    report = summarize_scenario(summary, profile)
    manifest = copy.deepcopy(summary['evidence'])
    ids = [ref['snapshot_id'] for ref in manifest.values()]
    snapshots = {s.id: s for s in db.session.scalars(select(TrialSnapshot).where(TrialSnapshot.id.in_(ids)))} if ids else {}
    for nct, ref in manifest.items():
        source = snapshots.get(ref['snapshot_id'])
        if source is None or source.nct_id != nct:
            raise ValueError('Retained scenario evidence is missing.')
        ref['raw_study_sha256'] = digest(source.raw_study)
    analysis = {'report': report, 'source_manifest': manifest,
                'source_manifest_sha256': digest(manifest)}
    if len(json.dumps(analysis, ensure_ascii=False, allow_nan=False).encode()) > 32 * 1024 * 1024:
        raise ValueError('Scenario analysis exceeds the 32 MiB saved-result limit.')
    return analysis


def read_scenario(scenario_id):
    scenarios_ready()
    row = db.session.get(SavedPatientScenario, scenario_id)
    if row is None:
        return None
    p = row.payload
    if (not isinstance(p, dict) or row.schema_version != SCHEMA_VERSION
            or p.get('schema_version') != SCHEMA_VERSION or row.title != p.get('title')
            or digest(p) != row.payload_sha256):
        raise ValueError('Saved scenario format or integrity check failed. Its output is unavailable.')
    return row


def save_scenario(title, cohort_id, profile, expected_analysis_sha256, save_key):
    scenarios_ready()
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160 or any(ord(c) < 32 for c in title):
        raise ValueError('Enter a one-line scenario title between 1 and 160 characters.')
    for value in (save_key, expected_analysis_sha256):
        if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
            raise ValueError('Invalid save submission. Prepare this scenario again.')
    # The web form supplies normalized inputs from a signed preparation ticket.
    # Compare retries before loading current catalogs: a saved result is frozen.
    inputs = {'title': title.strip(), 'cohort_id': cohort_id, 'profile': copy.deepcopy(profile),
              'prepared_analysis_sha256': expected_analysis_sha256}

    def retry(existing):
        saved = read_scenario(existing.id)
        if saved.payload['inputs'] != inputs:
            raise ValueError('This form already saved a different scenario. Prepare a new save from Patient Lab.')
        return saved

    existing = db.session.scalar(select(SavedPatientScenario).where(SavedPatientScenario.save_key == save_key))
    if existing:
        return retry(existing)
    analysis = analyze_for_save(cohort_id, profile)
    if analysis['report']['profile'] != profile or digest(analysis) != expected_analysis_sha256:
        raise ValueError('The analysis changed after preparation. Return to Patient Lab and prepare the save again.')
    payload = {'schema_version': SCHEMA_VERSION, 'title': title.strip(), 'inputs': inputs,
               'saved_at_utc': datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
               'analysis': analysis,
               'scope_note': 'Saved synthetic reference analysis only. PK curves and patient-pool assumptions are not included. Source links may now show newer information.'}
    row = SavedPatientScenario(title=payload['title'], schema_version=SCHEMA_VERSION,
                               payload=payload, payload_sha256=digest(payload), save_key=save_key)
    db.session.add(row)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        existing = db.session.scalar(select(SavedPatientScenario).where(SavedPatientScenario.save_key == save_key))
        if existing:
            return retry(existing)
        raise
    return row


def register_saved_scenario_commands(app):
    @app.cli.command('saved-scenarios-check')
    def saved_scenarios_check():
        try:
            scenarios_ready()
            count = 0
            for row in db.session.scalars(select(SavedPatientScenario).order_by(SavedPatientScenario.id)):
                read_scenario(row.id)
                count += 1
        except (ValueError, SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f'Saved scenarios ready. Saved synthetic scenarios: {count}; payload integrity checks passed.')
