"""Shared extensions; importing this file does not open a database."""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import sqlite3

from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


db = SQLAlchemy(model_class=Base)
migrate = Migrate()


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _connection_record):
    """Enforce evidence links on SQLite; PostgreSQL enforces them itself."""
    if not isinstance(connection, sqlite3.Connection):
        return
    supports_autocommit = hasattr(connection, "autocommit")
    previous_autocommit = getattr(connection, "autocommit", None)
    if supports_autocommit:
        connection.autocommit = True
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
        if supports_autocommit:
            connection.autocommit = previous_autocommit
