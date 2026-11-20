"""Write the NCT01801436 observed file for the locked blind check (Simulation 3.0n).

Reads the ClinicalTrials.gov record (JSON with posted results) held in the owner's folder, checks its SHA-256,
selects the outcomes named in bortezomib_pk_nct01801436_check_plan_v1.json by exact title, and writes only those
endpoints: mean, SD and n. Day 1 clearance and Day 1 AUC to infinity are never selected. Nothing is typed by hand.

    python3 scripts/build_nct01801436_observed.py "<path to the record JSON>"

Run only after the plan is locked. The owner checks the written file against the record before the check is run.
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'intelligence_store' / 'data' / 'bortezomib_pk_nct01801436_observed_v1.json'
RECORD_SHA256 = 'aebff81cbec28cca698cf3c117560d2cf96fb1f3758740810fa4d126bbb5177e'
RECORD_NAME = ('NCT01801436 - Post-approval bortezomib pharmacokinetic study in multiple myeloma, '
               'ClinicalTrials.gov record with posted results [NCT01801436].json')
N = 10
_AUC = ('Area Under the Plasma Concentration-Time Curve From Time Zero to Time at Last Observed Quantifiable '
        'Concentration (AUC[0-t]) of Bortezomib on Day {} of Cycle 1')
ENDPOINTS = {
    'auc_last_day11': (_AUC.format(11), 'hour*ng per ml'),
    'cmax_day11': ('Maximum Observed Plasma Concentration (Cmax) of Bortezomib on Day 11 of Cycle 1', 'ng per ml'),
    'cl_day11': ('Systemic Clearance (CL) of Bortezomib on Day 11 of Cycle 1', 'liter per hour'),
    'vss_day11': ('Volume of Distribution at Steady-State (Vss) of Bortezomib on Day 11 of Cycle 1', 'liter'),
    'half_life_day11': ('Elimination Half-Life Period (T1/2) of Bortezomib on Day 11 of Cycle 1', 'hours'),
    'cmax_day1': ('Maximum Observed Plasma Concentration (Cmax) of Bortezomib on Day 1 of Cycle 1',
                  'nanogram per millileter (ng per ml)'),
    'auc_last_day1': (_AUC.format(1), 'hour*ng per ml'),
    'vss_day1': ('Volume of Distribution at Steady-State (Vss) of Bortezomib on Day 1 of Cycle 1', 'liter'),
}
NEVER_SELECTED = ('Systemic Clearance (CL) of Bortezomib on Day 1 of Cycle 1',
                  'Area Under the Plasma Concentration-Time Curve From Time Zero to Infinite Time (AUC[0-infinity]) '
                  'of Bortezomib on Day 1 of Cycle 1')


def extract(raw, expected_sha256=RECORD_SHA256):
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Record checksum does not match the ledger; nothing was written.')
    outcomes = json.loads(raw)['resultsSection']['outcomeMeasuresModule']['outcomeMeasures']
    by_title = {}
    for o in outcomes:
        by_title.setdefault(o['title'], []).append(o)
    out = {}
    for key, (title, unit) in ENDPOINTS.items():
        if title in NEVER_SELECTED:
            raise ValueError(f'{title} is excluded by the plan.')
        found = by_title.get(title, [])
        if len(found) != 1:
            raise ValueError(f'{key}: expected one outcome titled "{title}", found {len(found)}.')
        o = found[0]
        if o.get('unitOfMeasure', '').strip().lower() != unit:
            raise ValueError(f'{key}: unit {o.get("unitOfMeasure")!r}, expected {unit!r}.')
        if o.get('paramType') != 'MEAN' or o.get('dispersionType') != 'Standard Deviation':
            raise ValueError(f'{key}: not a mean with SD.')
        if len(o.get('groups', [])) != 1 or len(o.get('denoms', [])) != 1:
            raise ValueError(f'{key}: expected one group and one denominator.')
        n = int(o['denoms'][0]['counts'][0]['value'])
        meas = [m for c in o['classes'] for cat in c['categories'] for m in cat['measurements']]
        if len(meas) != 1:
            raise ValueError(f'{key}: expected one measurement, found {len(meas)}.')
        if n != N:
            raise ValueError(f'{key}: n = {n}; the plan fixes n = {N}.')
        out[key] = {'mean': float(meas[0]['value']), 'sd': float(meas[0]['spread']), 'n': n,
                    'unit_as_posted': o['unitOfMeasure'], 'title': title}
    return out


def build(raw, extracted_on, expected_sha256=RECORD_SHA256):
    return {'schema_version': 'external-observed-values-v1',
            'dataset': 'nct01801436_bortezomib_pk_unread',
            'source': {'name': RECORD_NAME, 'sha256': hashlib.sha256(raw).hexdigest(), 'registry': 'ClinicalTrials.gov',
                       'section': 'resultsSection.outcomeMeasuresModule', 'population': 'per-protocol, n = 10'},
            'extracted_on': extracted_on,
            'method': 'scripts/build_nct01801436_observed.py: exact outcome titles; posted mean and SD as written.',
            'excluded_never_extracted': list(NEVER_SELECTED),
            'reviewed_by_owner': False,
            'endpoints': extract(raw, expected_sha256)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('record', type=Path)
    ap.add_argument('--output', type=Path, default=OUTPUT)
    args = ap.parse_args(argv)
    if args.output.exists():
        sys.exit(f'{args.output} exists; a pinned file is never rewritten.')
    raw = args.record.read_bytes()
    payload = json.dumps(build(raw, date.today().isoformat()), indent=2, ensure_ascii=False) + '\n'
    args.output.write_text(payload, encoding='utf-8')
    print(f'Wrote {args.output}\nSHA256 {hashlib.sha256(payload.encode()).hexdigest()}')


if __name__ == '__main__':
    main()
