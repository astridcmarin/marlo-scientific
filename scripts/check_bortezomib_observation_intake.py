"""One verification command; require the intended tests rather than a zero-test pass."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT/'tests/test_bortezomib_observation_intake.py'
    if not path.is_file():
        print('Missing batch test file', file=sys.stderr)
        return 1
    suite = unittest.TestLoader().discover(str(ROOT/'tests'), pattern=path.name)
    count = suite.countTestCases()
    if count != 12:
        print('Expected 12 intake tests; found '+str(count), file=sys.stderr)
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    return subprocess.run([sys.executable, str(ROOT/'scripts/review_bortezomib_observation_intake.py')], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
