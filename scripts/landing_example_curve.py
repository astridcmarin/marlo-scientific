"""Generate the example concentration curve shown on the landing page (app/data/landing_example_curve_v1.json).

The curve is the platform's own Hughes 2019 typical-value calculation for one synthetic record, run through the
same code path as the Patient Lab page. It uses the test suite's in-memory fixture to create that record, so the
file can be regenerated and compared exactly (tests/test_landing_page.py does this).

Run from the repository root:  PYTHONPATH=.:tests python scripts/landing_example_curve.py
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'app' / 'data' / 'landing_example_curve_v1.json'
STATE = dict(age_years=65, biological_sex='FEMALE', weight=70, height=165, serum_creatinine=80)
WEIGHT_BASIS = 'ideal_body_weight_devine'
DOSE_MG = 25.0
HORIZON_H = 24.0


def build():
    import test_kim_pk_runs as fixtures
    from intelligence_store.estimated_pk import calculate_estimated_pk
    from intelligence_store.patient_state_revisions import save_revision
    case = fixtures.KimPKRunTests('test_save_and_read_back') if hasattr(fixtures.KimPKRunTests, 'test_save_and_read_back') \
        else fixtures.KimPKRunTests([n for n in dir(fixtures.KimPKRunTests) if n.startswith('test')][0])
    case.setUp()
    try:
        revision = save_revision(case.scenario.id, fixtures.full_state(**STATE), parent_revision_id=case.revision.id,
                                 title='Landing page example record')
        request = fixtures.request_mg(DOSE_MG)
        request['events'] = request['events'][:1]
        request['horizon']['value'] = HORIZON_H
        report = calculate_estimated_pk(revision.id, WEIGHT_BASIS, request, 'MM')
        calc = report['calculation']
        if calc['status'] != 'completed_educational_calculation':
            raise ValueError(f"Example calculation did not complete: {calc['execution_blockers']}")
        estimate = report['covariate_estimate']
        points = [[p['time_h'], round(p['concentration_ng_ml'], 2)] for p in calc['points']]
        peak = max(points, key=lambda p: p[1])
        return {
            'schema_version': 'landing-example-curve-v1',
            'what': 'Typical-value lenalidomide concentration curve from the Hughes 2019 population PK model, for one synthetic record.',
            'not': 'Not a measurement, a prediction for any person, or a dosing illustration.',
            'synthetic_record': STATE,
            'derived_covariates': {k: round(v['value'], 1) for k, v in estimate['estimates'].items()},
            'weight_basis': WEIGHT_BASIS,
            'request': {'single_dose_mg': DOSE_MG, 'horizon_h': HORIZON_H, 'disease_context': 'MM'},
            'method_version': calc['method_version'],
            'parameters': {k: round(v, 6) for k, v in calc['parameters'].items() if isinstance(v, (int, float))},
            'peak': {'time_h': peak[0], 'concentration_ng_ml': peak[1]},
            'auc_0_24_ng_h_ml': round(calc['auc_0_horizon_ng_h_ml'], 1),
            'generated_by': 'scripts/landing_example_curve.py',
            'points_time_h_concentration_ng_ml': points,
        }
    finally:
        case.tearDown()


if __name__ == '__main__':
    data = build()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8')
    print(f"Wrote {OUT} (peak {data['peak']}, AUC0-24 {data['auc_0_24_ng_h_ml']})", file=sys.stderr)
