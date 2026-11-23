import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PlatformFilesIndexTests(unittest.TestCase):
    def test_index_lists_every_tracked_file(self):
        """docs/PLATFORM_FILES.md must match what scripts/platform_files_index.py writes for the tracked files."""
        result = subprocess.run([sys.executable, 'scripts/platform_files_index.py', '--check'], cwd=ROOT)
        self.assertEqual(result.returncode, 0, 'docs/PLATFORM_FILES.md is out of date: run python3 scripts/platform_files_index.py')


if __name__ == '__main__':
    unittest.main()
