"""Step 1: evidence storage only; normalized analytical tables come next."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .extensions import db


def utc_now() -> datetime:
    # Store UTC without an offset consistently across SQLite and PostgreSQL.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TrialSnapshot(db.Model):
    """One retrieved study JSON object, with source and retrieval metadata.

    Multiple snapshots may reference the same NCT ID. Refreshes will append
    records so previous evidence is retained. Missing source values stay null.
    """

    __tablename__ = "trial_snapshot"
    __table_args__ = (CheckConstraint("length(nct_id) = 11", name="nct_id_length"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nct_id: Mapped[str] = mapped_column(String(11), index=True)
    source: Mapped[str] = mapped_column(String(64), default="ClinicalTrials.gov")
    source_url: Mapped[str] = mapped_column(Text)
    # Preserve YYYY, YYYY-MM, or YYYY-MM-DD exactly as reported.
    source_last_update_date: Mapped[Optional[str]] = mapped_column(String(10))
    retrieved_at_utc: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    raw_study: Mapped[dict[str, Any]] = mapped_column(JSON)
