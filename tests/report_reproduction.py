"""Comparing a regenerated locked check report with the committed one.

The committed reports were produced on Linux, the CI platform, and must reproduce there exactly, byte for byte in
value. Other platforms (macOS) can differ in the last floating-point digits of long simulations, because their maths
libraries round differently. There, every key, string, classification, count and input checksum must still match
exactly; only floating-point numbers may differ, by at most REL_TOL relative to their size; and the report's own
digest is not compared, since it is a hash over those numbers. The committed report's digest is still checked against
its committed body by the tests that do so.

Set MARLO_EXACT_REPORTS=1 to require exact reproduction on any platform.
"""
import json
import math
import os
import sys

REL_TOL = 1e-12
ABS_TOL = 1e-15
# Digests computed over the report's own numbers; input pins (plan, extracts, observed data) are compared exactly.
OWN_DIGEST_KEYS = frozenset({'report_sha256'})


def exact_platform():
    return sys.platform.startswith('linux') or os.environ.get('MARLO_EXACT_REPORTS') == '1'


def _differences(fresh, committed, path, out):
    if isinstance(fresh, dict) and isinstance(committed, dict):
        if set(fresh) != set(committed):
            out.append(f'{path}: keys differ ({sorted(set(fresh) ^ set(committed))})')
            return
        for key in committed:
            if key in OWN_DIGEST_KEYS:
                continue
            _differences(fresh[key], committed[key], f'{path}.{key}', out)
    elif isinstance(fresh, list) and isinstance(committed, list):
        if len(fresh) != len(committed):
            out.append(f'{path}: length {len(fresh)} != {len(committed)}')
            return
        for i, (a, b) in enumerate(zip(fresh, committed)):
            _differences(a, b, f'{path}[{i}]', out)
    elif isinstance(fresh, float) or isinstance(committed, float):
        numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (fresh, committed))
        if not numeric or not math.isclose(fresh, committed, rel_tol=REL_TOL, abs_tol=ABS_TOL):
            out.append(f'{path}: {fresh!r} != {committed!r}')
    elif fresh != committed or type(fresh) is not type(committed):
        out.append(f'{path}: {fresh!r} != {committed!r}')


def differences(fresh, committed):
    """Differences beyond floating-point rounding, as readable paths; empty when the reports agree."""
    out = []
    _differences(json.loads(json.dumps(fresh, allow_nan=False)), committed, '$', out)
    return out


def assert_reproduces(test, fresh, committed):
    """Exact on the CI platform; within REL_TOL for floating-point numbers elsewhere."""
    fresh = json.loads(json.dumps(fresh, allow_nan=False))
    if exact_platform():
        test.assertEqual(fresh, committed)
        return
    found = differences(fresh, committed)
    test.assertEqual(found, [], f'regenerated report differs beyond floating-point rounding (first: {found[:5]})')
