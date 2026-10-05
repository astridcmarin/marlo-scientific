"""Step 1: evidence storage only; normalized analytical tables come next."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Text
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


class NormalizedTrial(db.Model):
    """One current structured trial row, linked to its source snapshot.

    Registry strings are retained without title-casing. SQL NULL means
    missing/invalid data; zero and explicitly empty lists retain their meaning.
    These rows are NOT a complete condition-specific landscape cohort.
    """

    __tablename__ = "normalized_trial"
    __table_args__ = (
        CheckConstraint("length(nct_id) = 11", name="nct_id_length"),
        CheckConstraint(
            "enrollment_count IS NULL OR enrollment_count >= 0",
            name="enrollment_nonnegative",
        ),
    )

    nct_id: Mapped[str] = mapped_column(String(11), primary_key=True)
    brief_title: Mapped[Optional[str]] = mapped_column(Text)
    official_title: Mapped[Optional[str]] = mapped_column(Text)
    overall_status: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    study_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    phases: Mapped[Optional[list[str]]] = mapped_column(JSON(none_as_null=True))
    conditions: Mapped[Optional[list[str]]] = mapped_column(JSON(none_as_null=True))
    enrollment_count: Mapped[Optional[int]] = mapped_column()
    enrollment_type: Mapped[Optional[str]] = mapped_column(String(32))
    # These refer only to the registry lead sponsor, never to collaborators.
    lead_sponsor_name: Mapped[Optional[str]] = mapped_column(Text)
    lead_sponsor_class: Mapped[Optional[str]] = mapped_column(String(64))
    start_date: Mapped[Optional[str]] = mapped_column(String(10))
    start_date_type: Mapped[Optional[str]] = mapped_column(String(32))
    primary_completion_date: Mapped[Optional[str]] = mapped_column(String(10))
    primary_completion_date_type: Mapped[Optional[str]] = mapped_column(String(32))
    completion_date: Mapped[Optional[str]] = mapped_column(String(10))
    completion_date_type: Mapped[Optional[str]] = mapped_column(String(32))
    source_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("trial_snapshot.id"), index=True
    )
    source_retrieved_at_utc: Mapped[datetime] = mapped_column(DateTime)
    normalization_version: Mapped[str] = mapped_column(String(32))
    normalized_at_utc: Mapped[datetime] = mapped_column(DateTime)


class AnalysisCohort(db.Model):
    """One independently retrieved query run; never inferred from search pages."""

    __tablename__ = "analysis_cohort"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETE', 'PARTIAL', 'FAILED')",
            name="status_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    condition: Mapped[str] = mapped_column(Text)
    api_url: Mapped[str] = mapped_column(Text)
    query_params: Mapped[dict[str, Any]] = mapped_column(JSON)
    query_version: Mapped[str] = mapped_column(String(32))
    normalization_version: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(32))
    max_pages: Mapped[int] = mapped_column()
    start_year: Mapped[Optional[int]] = mapped_column()
    end_year: Mapped[Optional[int]] = mapped_column()
    started_at_utc: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at_utc: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING", index=True)
    expected_count: Mapped[Optional[int]] = mapped_column()
    retrieved_count: Mapped[int] = mapped_column(default=0)
    pages_fetched: Mapped[int] = mapped_column(default=0)
    page_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)


class CohortTrial(db.Model):
    """Freeze a run's trial membership and its exact retained study snapshot."""

    __tablename__ = "cohort_trial"

    cohort_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_cohort.id"), primary_key=True
    )
    nct_id: Mapped[str] = mapped_column(String(11), primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("trial_snapshot.id"), index=True
    )
