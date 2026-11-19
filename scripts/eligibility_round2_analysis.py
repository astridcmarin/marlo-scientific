"""Eligibility second annotation, round two: the analysis plan v2.1 prescribes, on the two pinned records.

Run once on 19 November 2026, after both records were pinned (previous commit). It calls the executable committed
with the plan, agreement() in intelligence_store/eligibility_second_annotation.py, with plan v2.1 passed so the
bootstrap seed, resample count, bar and trial order come from that plan. Nothing here computes a statistic itself.

- primary: owner (A) against annotator B, comparison v2, the plan's rule on the lower bound.
- secondary: the same under comparison v1; each reader's v3 reading against the pinned v2 annotation (comparison v2,
  the comparison this plan pins). Per type, Wilson intervals, kappa and the descriptive extractor figures are inside
  each report, as agreement() builds them.

Writes docs/verification/eligibility_second_annotation_v2.json and prints only aggregate figures.
Usage (repo root): PYTHONPATH=. python3 scripts/eligibility_round2_analysis.py [--output PATH]
"""
import argparse
import json
from pathlib import Path

from intelligence_store import eligibility_second_annotation as sa
from intelligence_store.patient_state import digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'verification' / 'eligibility_second_annotation_v2.json'
PLAN = 'eligibility-second-annotation-plan-v2.1'


def build():
    plan = sa.load_plan(sa.PLANS[PLAN][0])
    rec = {r: sa.load_round_2_record(r) for r in ('owner', 'annotator_b')}
    page = {r: sa.page_payload(plan, r) for r in rec}
    for r in rec:
        problems, _ = sa.validate_record(rec[r], page[r], reader=r, plan=plan)
        if problems:
            raise ValueError(problems)
    comparison = plan['inputs']['comparison']
    primary = sa.agreement(rec['annotator_b'], page['annotator_b'], record_a=rec['owner'], comparison=comparison,
                           plan=plan, p_a=page['owner'])
    as_written = sa.agreement(rec['annotator_b'], page['annotator_b'], record_a=rec['owner'], comparison='v1',
                              plan=plan, p_a=page['owner'])
    against_v2 = {r: sa.agreement(rec[r], page[r], comparison=comparison, plan=plan) for r in rec}
    report = {
        'schema_version': 'eligibility-second-annotation-round-report-v1',
        'plan_version': plan['plan_version'], 'plan_sha256': sa.plan_sha256(plan),
        'records': {r: {'file': str(Path(p).relative_to(ROOT)), 'sha256': s, 'locked_at': rec[r]['locked_at'],
                        'page_sha256': rec[r]['page_sha256'], 'annotator_code': rec[r]['annotator']['code']}
                    for r, (p, s) in sa.ROUND_2_RECORDS.items()},
        'rule': plan['analysis']['rule'],
        'reading_rule': plan['analysis']['reading_rule'],
        'primary': primary,
        'secondary': {
            'comparison_v1_as_written': as_written,
            'owner_v3_against_pinned_v2_annotation': against_v2['owner'],
            'annotator_b_v3_against_pinned_v2_annotation': against_v2['annotator_b'],
        },
        'notes': [
            'agreement() names reader B as `annotator` in each report: in the primary and the comparison-v1 reports that '
            'is annotator B against the owner\'s record; in the two reports against the pinned v2 annotation it is the '
            'reader whose record was passed.',
            'The extractor figures inside each report are descriptive only, on 50 trials, as the plan states.',
            'The owner annotated all 200 trials in the original pass, so she is not a naive reader; B is. Reported, not '
            'corrected (plan limitation).',
        ],
        'clinical_prediction_validated': False,
    }
    report['report_sha256'] = digest(report)
    return report


def summary(report):
    def line(r):
        o = r['overall']
        return (f"{o['exact_agreement']}/{o['pairs']} = {o['exact_rate']}, bootstrap 95% {o['exact_trial_bootstrap_95']}, "
                f"detection kappa {o['detection_kappa']}")
    p = report['primary']
    out = [f"primary (A vs B, comparison {p.get('comparison', 'v1')}): {line(p)}",
           f"  rule: lower bound {p['reliability_reading']['value']} vs bar {p['reliability_reading']['bar']} -> "
           f"{p['reliability_reading']['reading']}",
           '  per type: ' + '; '.join(f"{t} {v['exact_agreement']}/{v['trials']} {v['exact_wilson_95']} kappa {v['detection_kappa']}"
                                    for t, v in p['per_type'].items()),
           f"  disagreements for adjudication: {len(p['disagreements_for_adjudication'])}"]
    for k, r in report['secondary'].items():
        out.append(f"{k}: {line(r)}")
    for k in ('primary',):
        ex = report[k]['extractors_on_sample_descriptive']
        out.append('extractors (descriptive): ' + json.dumps({ref: {m: {kk: vv for kk, vv in s.items() if not isinstance(vv, (dict, list))}
                                                                    for m, s in d.items()} for ref, d in ex.items()}))
    out.append(f"report_sha256 {report['report_sha256']}")
    return '\n'.join(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default=str(OUT))
    args = ap.parse_args()
    report = build()
    Path(args.output).write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    print(summary(report))
