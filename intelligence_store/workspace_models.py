"""Immutable, locally saved intelligence briefs; registered for Alembic."""
from datetime import datetime
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from .extensions import db
from .models import utc_now


class IntelligenceBrief(db.Model):
    __tablename__ = 'intelligence_brief'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    schema_version: Mapped[str] = mapped_column(String(40))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    # Retried submissions return the same saved brief instead of duplicating it.
    save_key: Mapped[str] = mapped_column(String(64), unique=True)
