"""The Alembic chain is complete and a fresh `db upgrade` builds exactly the schema the models define."""
import ast
from pathlib import Path
import contextlib
import sqlite3
import tempfile
import unittest

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / 'intelligence_migrations' / 'versions'


def _assignment(path, name):
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f'{path.name} has no {name}')


def _schema(path):
    # sqlite3's own context manager only commits; closing() also closes the connection.
    with contextlib.closing(sqlite3.connect(path)) as connection:
        tables = [r[0] for r in connection.execute(
            "select name from sqlite_master where type='table' and name not in ('alembic_version','sqlite_sequence')")]
        return {t: sorted(c[1] for c in connection.execute(f'pragma table_info({t})')) for t in tables}


class MigrationChainTests(unittest.TestCase):
    def test_single_linear_chain_without_missing_parents(self):
        revisions = {}
        for path in VERSIONS.glob('*.py'):
            revisions[_assignment(path, 'revision')] = _assignment(path, 'down_revision')
        parents = list(revisions.values())
        self.assertEqual(parents.count(None), 1, 'Exactly one base migration expected.')
        for revision, parent in revisions.items():
            if parent is not None:
                self.assertIn(parent, revisions, f'{revision} points to missing parent {parent}.')
        children = [p for p in parents if p is not None]
        self.assertEqual(len(children), len(set(children)), 'Branching migration history.')

    def test_fresh_upgrade_matches_models(self):
        from flask_migrate import upgrade
        from intelligence_store import init_storage
        from intelligence_store.extensions import db
        with tempfile.TemporaryDirectory() as tmp:
            migrated, modelled = Path(tmp) / 'migrated.db', Path(tmp) / 'modelled.db'
            app = Flask(__name__)
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{migrated}'
            init_storage(app)
            with app.app_context():
                upgrade()
                db.engine.dispose()
            reference = Flask(__name__)
            reference.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{modelled}'
            init_storage(reference)
            with reference.app_context():
                db.create_all()
                db.engine.dispose()
            self.assertEqual(_schema(migrated), _schema(modelled))


if __name__ == '__main__':
    unittest.main()
