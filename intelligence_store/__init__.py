"""Add the v2 storage foundation to an existing Flask application."""

import os
from pathlib import Path

import click
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db, migrate
from .models import NormalizedTrial, TrialSnapshot
from .normalization import register_normalization_commands
from .cohorts import register_cohort_commands


def init_storage(app):
    """Configure extensions and CLI only. Do not create tables on startup."""
    if "sqlalchemy" in app.extensions:
        raise RuntimeError(
            "This app already has SQLAlchemy. Integrate with its existing db "
            "object instead of initializing a second extension."
        )

    project_root = Path(__file__).resolve().parent.parent
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        configured_url = os.environ.get("DATABASE_URL", "").strip()
        if configured_url:
            app.config["SQLALCHEMY_DATABASE_URI"] = configured_url
        else:
            database_folder = project_root / "instance"
            database_folder.mkdir(parents=True, exist_ok=True)
            database_path = (database_folder / "intelligence.db").as_posix()
            app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)
    migrate.init_app(app, db, directory=str(project_root / "intelligence_migrations"))
    register_normalization_commands(app)
    register_cohort_commands(app)

    @app.cli.command("db-check")
    def db_check():
        """Check connectivity and the migrated evidence table without writing."""
        try:
            if not inspect(db.engine).has_table(TrialSnapshot.__tablename__):
                raise click.ClickException(
                    "Evidence table is missing. Run the initial migration and upgrade."
                )
            count = db.session.scalar(select(func.count()).select_from(TrialSnapshot))
            if not inspect(db.engine).has_table(NormalizedTrial.__tablename__):
                raise click.ClickException(
                    "Normalized trial table is missing. Generate the Step 3 migration "
                    "and run db upgrade."
                )
            trial_count = db.session.scalar(
                select(func.count()).select_from(NormalizedTrial)
            )
        except SQLAlchemyError as exc:
            raise click.ClickException(
                "Database check failed. Verify configuration and run db upgrade."
            ) from exc
        click.echo(f"Database ready. Stored trial snapshots: {count}")
        click.echo(f"Normalized unique trials: {trial_count}")
