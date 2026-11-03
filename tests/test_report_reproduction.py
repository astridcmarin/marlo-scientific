"""The comparison used by the locked-report reproduction tests (exact on Linux, last-digit tolerance elsewhere)."""
import json
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_reproduction as rr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _nudge(value, factor):
    """Every float multiplied by `factor`, as a different platform's last-digit rounding would do."""
    if isinstance(value, dict):
        return {k: _nudge(v, factor) for k, v in value.items()}
    if isinstance(value, list):
        return [_nudge(v, factor) for v in value]
    if isinstance(value, float):
        return value * factor
    return value


class Comparison(unittest.TestCase):
    def setUp(self):
        self.committed = json.loads((ROOT / 'docs/verification/kim_renal_group_check_v1.json').read_text())

    def test_identical_reports_agree(self):
        self.assertEqual(rr.differences(self.committed, self.committed), [])

    def test_last_digit_rounding_is_tolerated(self):
        fresh = _nudge(self.committed, 1 + 4e-16)
        fresh['report_sha256'] = '0' * 64
        self.assertEqual(rr.differences(fresh, self.committed), [])

    def test_real_numerical_change_is_caught(self):
        self.assertTrue(rr.differences(_nudge(self.committed, 1 + 1e-9), self.committed))

    def test_text_classification_and_input_pins_must_match_exactly(self):
        for key in ('plan_sha256', 'kim_extract_sha256'):
            fresh = dict(self.committed, **{key: 'f' * 64})
            self.assertEqual(len(rr.differences(fresh, self.committed)), 1, key)
        self.assertTrue(rr.differences({'a': 'consistent'}, {'a': 'model_under_predicts'}))
        self.assertTrue(rr.differences({'a': 1}, {'a': 2}))
        self.assertTrue(rr.differences({'a': True}, {'a': 1}))
        self.assertTrue(rr.differences({'a': 1.0}, {'a': '1.0'}))

    def test_structure_must_match(self):
        self.assertTrue(rr.differences({'a': 1, 'b': 2}, {'a': 1}))
        self.assertTrue(rr.differences({'a': [1.0, 2.0]}, {'a': [1.0]}))

    def test_exact_on_linux_or_when_asked(self):
        with mock.patch.object(rr.sys, 'platform', 'linux'):
            self.assertTrue(rr.exact_platform())
        with mock.patch.object(rr.sys, 'platform', 'darwin'), mock.patch.dict(rr.os.environ, {}, clear=True):
            self.assertFalse(rr.exact_platform())
        with mock.patch.object(rr.sys, 'platform', 'darwin'), mock.patch.dict(rr.os.environ, {'MARLO_EXACT_REPORTS': '1'}):
            self.assertTrue(rr.exact_platform())

    def test_assert_reproduces_is_exact_on_the_ci_platform(self):
        fresh = _nudge(self.committed, 1 + 4e-16)
        with mock.patch.object(rr, 'exact_platform', return_value=True):
            with self.assertRaises(AssertionError):
                rr.assert_reproduces(self, fresh, self.committed)
        with mock.patch.object(rr, 'exact_platform', return_value=False):
            rr.assert_reproduces(self, fresh, self.committed)
