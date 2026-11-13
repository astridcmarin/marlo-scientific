"""Run the unit tests where SQLAlchemy and Flask-SQLAlchemy cannot be installed (for example a cloud workspace whose
package installs are blocked).

    PYTHONPATH=. python3 scripts/run_tests_without_db.py                      # every test
    PYTHONPATH=. python3 scripts/run_tests_without_db.py tests.test_x ...     # selected modules

It skips intelligence_store/__init__.py and replaces sqlalchemy, flask_sqlalchemy, flask_migrate and alembic with
empty stand-ins, so database-backed code is not exercised: about 300 tests that need the database (pages, CLI, the
store) end in errors here, which is expected. Compare against a run on main before your change, and rely on GitHub
CI (the full requirements) for those tests. Never use it to decide that a database-backed test passes.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

root = Path.cwd()
sys.path.insert(0, str(root))
pkg = types.ModuleType('intelligence_store')
pkg.__path__ = [str(root / 'intelligence_store')]
sys.modules['intelligence_store'] = pkg


def _module(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: mock.MagicMock(name=f'{name}.{attr}')
    return m


exc = types.ModuleType('sqlalchemy.exc')


class SQLAlchemyError(Exception):
    pass


exc.SQLAlchemyError = SQLAlchemyError
for _n in ('IntegrityError', 'OperationalError', 'NoResultFound', 'ProgrammingError'):
    setattr(exc, _n, type(_n, (SQLAlchemyError,), {}))
sa = _module('sqlalchemy')
sa.exc = exc
sys.modules['sqlalchemy'] = sa
sys.modules['sqlalchemy.exc'] = exc
for sub in ('sqlalchemy.orm', 'sqlalchemy.engine', 'sqlalchemy.types', 'sqlalchemy.sql', 'sqlalchemy.ext',
            'sqlalchemy.dialects', 'flask_sqlalchemy', 'flask_migrate', 'alembic'):
    sys.modules[sub] = _module(sub)

if __name__ == '__main__':
    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv) > 1 else loader.discover('tests')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(not result.wasSuccessful())
