"""Consolidation docs stay in step with the repository: the data-file index and the status-by-drug page."""
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DataFileIndex(unittest.TestCase):
    def test_index_is_current(self):
        spec = importlib.util.spec_from_file_location('data_file_index', ROOT / 'scripts' / 'data_file_index.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual((ROOT / 'docs' / 'DATA_FILES.md').read_text(), mod.render(),
                         'docs/DATA_FILES.md is out of date: run python3 scripts/data_file_index.py')


class StatusByDrug(unittest.TestCase):
    def test_every_finding_appears_and_every_reference_exists(self):
        from intelligence_store.check_findings import load_findings
        ids = {f['id'] for f in load_findings()['findings']}
        text = (ROOT / 'docs' / 'STATUS_BY_DRUG.md').read_text()
        cited = set(re.findall(r'\(finding: ([a-z0-9_]+)\)', text))
        self.assertEqual(cited - ids, set(), 'STATUS_BY_DRUG.md cites a finding that does not exist')
        self.assertEqual(ids - cited, set(), 'a finding is missing from STATUS_BY_DRUG.md')


if __name__ == '__main__':
    unittest.main()
