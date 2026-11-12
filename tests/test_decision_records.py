"""Architecture decision records in docs/decisions/ (rule added 11 November 2026)."""
import re
import unittest
from pathlib import Path

DECISIONS = Path(__file__).resolve().parents[1] / 'docs' / 'decisions'
HEADINGS = ('## Problem', '## Options', '## Decision', '## Revisit when')


class DecisionRecords(unittest.TestCase):
    def test_every_record_is_numbered_and_has_the_four_headings(self):
        records = sorted(DECISIONS.glob('*.md'))
        self.assertTrue(records)
        for i, path in enumerate(records, start=1):
            self.assertRegex(path.name, rf'^{i:04d}-[a-z0-9-]+\.md$')
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.startswith(f'# {i:04d} — '), path.name)
            self.assertRegex(text, r'\*\*Status:\*\* (proposed|accepted|superseded)')
            for heading in HEADINGS:
                self.assertIn(heading, text, f'{path.name}: {heading}')


if __name__ == '__main__':
    unittest.main()
