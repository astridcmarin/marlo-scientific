"""Fixed invented repeat-dose example using linear superposition, not a drug model."""
import json
import math
from pathlib import Path
import click
from .patient_state import digest
from .transit_kernel import transit_demo

METHOD_VERSION = 'generic-transit-superposition-v1.0'


def transit_regimen_demo():
    """Exactly three invented 1 mg additions at 0, 8 and 16 h; fixed 24 h display."""
    single = transit_demo()
    basis = single['points']
    # Offsets are explicit integer indices on the fixed 0.1 h grid, not rounded
    # matches against arbitrary treatment times. No general regimen API is implied.
    events = [{'time_h': float(t), 'amount_mg': 1.0, 'grid_index': t*10}
              for t in (0, 8, 16)]
    def state(index, before_event=False):
        active = [e for e in events if e['grid_index'] < index or
                  (e['grid_index'] == index and not before_event)]
        contributions = [basis[index-e['grid_index']] for e in active]
        transit = [math.fsum(p['transit_amounts_mg'][j] for p in contributions) for j in range(3)]
        central = math.fsum(p['central_amount_mg'] for p in contributions)
        eliminated = math.fsum(p['eliminated_amount_mg'] for p in contributions)
        return {'time_h': basis[index]['time_h'], 'transit_amounts_mg': transit,
                'central_amount_mg': central, 'eliminated_amount_mg': eliminated,
                'concentration_ng_ml': math.fsum(p['concentration_ng_ml'] for p in contributions),
                'auc_0_t_ng_h_ml': math.fsum(p['auc_0_t_ng_h_ml'] for p in contributions),
                'cumulative_administered_mg': math.fsum(e['amount_mg'] for e in active)}
    points = [state(i) for i in range(len(basis))]
    boundaries = [{'time_h': e['time_h'], 'amount_mg': e['amount_mg'],
                   'before': state(e['grid_index'], True), 'after': state(e['grid_index'])}
                  for e in events]
    error = max(abs(math.fsum(p['transit_amounts_mg'] +
                             [p['central_amount_mg'],p['eliminated_amount_mg']]) -
                    p['cumulative_administered_mg']) for p in points)
    if error > 3e-9:
        raise ValueError('Repeat-dose amount balance failed.')
    result = {'schema_version': 'generic-transit-regimen-demo-v1', 'method_version': METHOD_VERSION,
              'model_kind': 'invented_mathematical_example', 'drug': None,
              'patient_revision_id': None, 'ready_for_patient_simulation': False,
              'inputs': dict(single['inputs']), 'events': events,
              'basis': {'method_version': single['method_version'],
                        'report_sha256': single['report_sha256'],
                        'solver': single['solver'],
                        'role': 'Fixed 1 mg single-addition response, shifted by each event time and summed.'},
              'points': points, 'event_boundaries': boundaries,
              'single_dose_reference_points': basis,
              'amount_balance': {'max_absolute_error_at_display_points_mg': error,
                                'tolerance_mg': 3e-9,
                                'basis_internal_step_max_absolute_error_mg': single['amount_balance']['max_absolute_error_mg']},
              'total_administered_mg': 3.0,
              'auc_0_horizon_ng_h_ml': points[-1]['auc_0_t_ng_h_ml'],
              'analytic_auc_0_infinity_ng_h_ml': 3*single['analytic_auc_0_infinity_ng_h_ml'],
              'assumptions': [
                  'Fixed invented 1 mg additions at 0, 8 and 16 h into the first transit stage.',
                  'Linear time-invariant equations: each shifted single-addition response can be summed.',
                  'Same constant clearance, volume and transfer rates for all contributions.',
                  'No saturation, interactions, bioavailability adjustment, patient covariates or physiological feedback.',
                  'At an addition, first-stage and administered amounts jump; central concentration and AUC are continuous.',
                  'Display values at event times are after the addition; before/after states are separately recorded.'],
              'limitation': 'Fixed invented repeat-dose mathematical example. No drug, real patient, steady-state claim, efficacy, toxicity, dose recommendation or published-model reproduction is established. Superposition requires linear time-invariant equations.'}
    result['report_sha256'] = digest(result)
    return result


def register_transit_regimen_commands(app):
    @app.cli.command('transit-regimen-demo')
    @click.option('--json', 'json_output', is_flag=True)
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(json_output, output):
        """Compare fixed invented single and repeated additions; no patient model."""
        try:
            report = transit_regimen_demo()
            if output:
                with output.open('x', encoding='utf-8') as handle:
                    json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
                    handle.write('\n')
                click.echo(f'Saved generic repeat-dose example: {output}')
            elif json_output:
                click.echo(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
            else:
                click.echo('Generic repeated-dose example | Invented parameters | No patient model')
                click.echo('Additions: 1 mg at 0, 8 and 16 h | Total: 3 mg')
                click.echo(f"AUC 0–24 h: {report['auc_0_horizon_ng_h_ml']:.6g} ng·h/mL")
                click.echo(f"Max display-point amount-balance error: {report['amount_balance']['max_absolute_error_at_display_points_mg']:.3g} mg")
                click.echo('Patient simulation ready: false')
                click.echo(report['limitation'])
        except (ValueError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
