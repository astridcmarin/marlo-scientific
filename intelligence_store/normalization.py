"""Versioned extraction of trial fields from retained source evidence."""

from datetime import date
import re

import click
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import NormalizedTrial, TrialSnapshot, utc_now

NORMALIZATION_VERSION = "trial-fields-v1.0"


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_list(value):
    if not isinstance(value, list):
        return None
    if not all(_text(item) is not None for item in value):
        return None
    # Deduplicate exact strings only. Drug/corporate alias resolution comes later.
    return list(dict.fromkeys(item.strip() for item in value))


def _source_date(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}(?:-[0-9]{2}){0,2}", value
    ):
        return None
    parts = [int(part) for part in value.split("-")]
    try:
        date(
            parts[0],
            parts[1] if len(parts) > 1 else 1,
            parts[2] if len(parts) > 2 else 1,
        )
    except ValueError:
        return None
    return value


def upsert_trial_from_snapshot(snapshot):
    """Stage an insert/update; the caller owns the transaction.

    Receipt time determines recency, with snapshot ID breaking timestamp ties.
    Older receipts never overwrite the current source. Latest registry status
    is not a historical status as of a selected landscape date range.
    """
    raw = _mapping(snapshot.raw_study)
    protocol = _mapping(raw.get("protocolSection"))
    identification = _mapping(protocol.get("identificationModule"))
    nct_id = identification.get("nctId")
    if (
        not isinstance(nct_id, str)
        or not re.fullmatch(r"NCT[0-9]{8}", nct_id)
        or nct_id != snapshot.nct_id
        or snapshot.id is None
    ):
        return "invalid"

    trial = db.session.get(NormalizedTrial, nct_id)
    if trial is not None:
        incoming = (snapshot.retrieved_at_utc, snapshot.id)
        existing = (trial.source_retrieved_at_utc, trial.source_snapshot_id)
        if incoming < existing:
            return "older"
        if (
            incoming == existing
            and trial.normalization_version == NORMALIZATION_VERSION
        ):
            return "unchanged"

    status = _mapping(protocol.get("statusModule"))
    design = _mapping(protocol.get("designModule"))
    enrollment = _mapping(design.get("enrollmentInfo"))
    sponsor_module = _mapping(protocol.get("sponsorCollaboratorsModule"))
    lead_sponsor = _mapping(sponsor_module.get("leadSponsor"))
    conditions = _mapping(protocol.get("conditionsModule"))
    count = enrollment.get("count")
    count = count if type(count) is int and count >= 0 else None

    if trial is None:
        trial = NormalizedTrial(nct_id=nct_id)
        db.session.add(trial)
    trial.brief_title = _text(identification.get("briefTitle"))
    trial.official_title = _text(identification.get("officialTitle"))
    trial.overall_status = _text(status.get("overallStatus"))
    trial.study_type = _text(design.get("studyType"))
    trial.phases = _string_list(design.get("phases"))
    trial.conditions = _string_list(conditions.get("conditions"))
    trial.enrollment_count = count
    trial.enrollment_type = _text(enrollment.get("type"))
    trial.lead_sponsor_name = _text(lead_sponsor.get("name"))
    trial.lead_sponsor_class = _text(lead_sponsor.get("class"))
    for field, source_field in [
        ("start_date", "startDateStruct"),
        ("primary_completion_date", "primaryCompletionDateStruct"),
        ("completion_date", "completionDateStruct"),
    ]:
        date_info = _mapping(status.get(source_field))
        setattr(trial, field, _source_date(date_info.get("date")))
        setattr(trial, field + "_type", _text(date_info.get("type")))
    trial.source_snapshot_id = snapshot.id
    trial.source_retrieved_at_utc = snapshot.retrieved_at_utc
    trial.normalization_version = NORMALIZATION_VERSION
    trial.normalized_at_utc = utc_now()
    return "updated"


def register_normalization_commands(app):
    @app.cli.command("normalize-trials")
    def normalize_trials():
        """Backfill structured trial rows from existing evidence snapshots."""
        invalid = 0
        processed = 0
        try:
            snapshots = db.session.scalars(
                select(TrialSnapshot)
                .order_by(TrialSnapshot.retrieved_at_utc, TrialSnapshot.id)
                .execution_options(yield_per=200)
            )
            for snapshot in snapshots:
                outcome = upsert_trial_from_snapshot(snapshot)
                processed += 1
                invalid += outcome == "invalid"
            db.session.commit()
            count = db.session.scalar(select(func.count()).select_from(NormalizedTrial))
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise click.ClickException(
                "Normalization failed. Check database configuration and run db upgrade."
            ) from exc
        click.echo(f"Processed snapshots: {processed}")
        click.echo(f"Normalized unique trials: {count}")
        click.echo(f"Invalid snapshots skipped: {invalid}")
