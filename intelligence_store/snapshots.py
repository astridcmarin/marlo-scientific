"""Save retrieved study objects before display formatting or normalization."""

from dataclasses import dataclass
from datetime import date
import re

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import TrialSnapshot, utc_now
from .normalization import upsert_trial_from_snapshot


@dataclass(frozen=True)
class SnapshotSaveResult:
    saved: int = 0
    skipped: int = 0
    failed: bool = False


def _reported_update_date(status):
    """Keep the source's ISO date precision. Unknown stays null."""
    if not isinstance(status, dict):
        return None
    date_info = status.get("lastUpdatePostDateStruct")
    if not isinstance(date_info, dict):
        return None
    value = date_info.get("date")
    if not isinstance(value, str):
        return None
    if not re.fullmatch(r"[0-9]{4}(?:-[0-9]{2}){0,2}", value):
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


def save_trial_snapshots(studies):
    """Append one snapshot per valid NCT ID in this retrieved page.

    This does not represent a complete search cohort or a read-through cache.
    A new API retrieval may append another snapshot for an existing NCT ID.
    The page is committed as one transaction. Database failures are logged
    and rolled back so the existing trial-search response can still render.
    """
    if not isinstance(studies, list):
        current_app.logger.warning(
            "Trial snapshot storage skipped: study list is invalid."
        )
        return SnapshotSaveResult(failed=True)
    if not studies:
        return SnapshotSaveResult()

    retrieved_at = utc_now()
    rows = []
    seen = set()
    skipped = 0
    for study in studies:
        snapshot = make_trial_snapshot(study, retrieved_at)
        if snapshot is None:
            skipped += 1
            continue
        if snapshot.nct_id in seen:
            skipped += 1
            continue
        seen.add(snapshot.nct_id)
        rows.append(snapshot)

    if skipped:
        current_app.logger.warning(
            "Skipped %s invalid or repeated study records while saving this page.",
            skipped,
        )
    if not rows:
        return SnapshotSaveResult(skipped=skipped)

    try:
        db.session.add_all(rows)
        # Allocate snapshot IDs, then save structured rows in the SAME transaction.
        db.session.flush()
        for snapshot in rows:
            upsert_trial_from_snapshot(snapshot)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning(
            "Trial evidence/normalization storage failed; no records from this page were saved. "
            "Search results will still be displayed. Check database configuration "
            "and migrations."
        )
        return SnapshotSaveResult(skipped=skipped, failed=True)

    return SnapshotSaveResult(saved=len(rows), skipped=skipped)


def make_trial_snapshot(study, retrieved_at=None):
    """Build a valid evidence row; the caller owns persistence/transaction scope."""
    protocol = study.get("protocolSection") if isinstance(study, dict) else None
    identification = (
        protocol.get("identificationModule") if isinstance(protocol, dict) else None
    )
    nct_id = identification.get("nctId") if isinstance(identification, dict) else None
    if not isinstance(nct_id, str) or not re.fullmatch(r"NCT[0-9]{8}", nct_id):
        return None
    return TrialSnapshot(
        nct_id=nct_id,
        source="ClinicalTrials.gov",
        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
        source_last_update_date=_reported_update_date(protocol.get("statusModule")),
        retrieved_at_utc=retrieved_at if retrieved_at is not None else utc_now(),
        raw_study=study,
    )
