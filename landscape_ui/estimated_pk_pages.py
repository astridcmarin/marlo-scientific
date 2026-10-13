"""Patient Lab 2.0d page: covariates estimated from the saved record drive the educational curve."""
import json
from flask import Response, abort, redirect, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.saved_scenarios import read_scenario
from intelligence_store.covariate_estimation import WEIGHT_BASES, load_weight_basis_assessment
from intelligence_store.estimated_pk import (calculate_estimated_pk, compare_estimated_pk, estimate_for_revision,
                                             primary_weight_basis, DISEASE_CODES)
from intelligence_store.educational_pk_runs import save_estimated_pk_run
from intelligence_store.population_pk import calculate_population_pk
from .workspace_pages import COOKIE, TTL, _form_token, _validate_token, _response
from .scenario_pages import _error
from .transit_pages import _chart
from .educational_pk_pages import _charts
from .educational_pk_input_builder import TREATMENT_FIELDS, build_treatment_request

ACTIONS = ('calculate', 'compare', 'population', 'download', 'save')
FORM_FIELDS = TREATMENT_FIELDS | {'form_token', 'action', 'weight_basis', 'disease'}
BASIS_COLORS = {'ideal_body_weight_devine': '#007b83', 'adjusted_body_weight_0_4': '#b5651d',
                'total_body_weight': '#6a4c93'}
BASIS_LABELS = {'ideal_body_weight_devine': 'Ideal body weight (Devine)',
                'adjusted_body_weight_0_4': 'Adjusted body weight (IBW + 0.4 × excess)',
                'total_body_weight': 'Total body weight'}


def _basis_options():
    assessment = load_weight_basis_assessment()
    primary = assessment['decision']['primary_assumption']
    options = []
    for basis in WEIGHT_BASES:
        evidence = assessment['basis_evidence'][basis]['evidence_level'].replace('_', ' ').replace('table1', 'Table 1')
        role = f'primary assumption · {evidence} · unresolved' if basis == primary else f'sensitivity branch · {evidence}'
        options.append({'value': basis, 'label': f'{BASIS_LABELS[basis]} — {role}'})
    return options


def _overlay(comparison):
    """Concentration curves for each basis on one chart; values stay in the report and table."""
    series = []
    times = None
    for basis, result in comparison['results'].items():
        calc = result['calculation']
        if calc is None or not calc['points']:
            return []
        times = [p['time_h'] for p in calc['points']]
        series.append({'label': BASIS_LABELS[basis], 'color': BASIS_COLORS[basis], 'dash': '',
                       'values': [p['concentration_ng_ml'] for p in calc['points']]})
    chart = _chart('Central concentration by weight basis', 'ng/mL', times, series)
    chart['time_ticks'] = [{'x': 70 + 670 * i / 4, 'label': f'{times[-1] * i / 4:g}'} for i in range(5)]
    return [chart]


def _band_chart(population):
    """Shaded 5–95% and 25–75% bands, population median and typical curve on one axis."""
    if not population or not population['band']:
        return None
    times = population['times_h']
    band = population['band']
    top = max(max(b['p95'] for b in band), max(population['typical_concentration_ng_ml'])) * 1.1 or 1.0
    x = lambda t: 70 + 670 * t / times[-1]
    y = lambda v: 250 - 220 * v / top
    def area(lo, hi):
        upper = [f'{x(b["time_h"]):.3f},{y(b[hi]):.3f}' for b in band]
        lower = [f'{x(b["time_h"]):.3f},{y(b[lo]):.3f}' for b in reversed(band)]
        return ' '.join(upper + lower)
    line = lambda values: ' '.join(f'{x(t):.3f},{y(v):.3f}' for t, v in zip(times, values))
    return {'title': 'Concentration across virtual patients with these covariates', 'unit': 'ng/mL',
            'outer': area('p05', 'p95'), 'inner': area('p25', 'p75'),
            'median': line([b['p50'] for b in band]), 'typical': line(population['typical_concentration_ng_ml']),
            'ticks': [{'y': 250 - 220 * i / 4, 'label': f'{top * i / 4:.3g}'} for i in range(5)],
            'time_ticks': [{'x': 70 + 670 * i / 4, 'label': f'{times[-1] * i / 4:g}'} for i in range(5)]}


def register_estimated_pk_pages(bp):
    @bp.route('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/estimated-pk',
              methods=['GET', 'POST'])
    def estimated_pk(scenario_id, revision_id):
        if request.args:
            abort(400)
        if request.content_length and request.content_length > 20000:
            abort(413)
        try:
            scenario = read_scenario(scenario_id)
            revision = read_revision(revision_id)
            if scenario is None or revision is None or revision.scenario_id != scenario_id:
                abort(404)
            form = {'weight_basis': primary_weight_basis(), 'disease': 'UNKNOWN', 'horizon': '24',
                    'events': '0, 25', 'source_ref': '', 'title': ''}
            report = comparison = population = None
            error = None
            status = 200
            if request.method == 'POST':
                if set(request.form) not in (FORM_FIELDS, FORM_FIELDS | {'title'}) or any(
                        len(request.form.getlist(k)) != 1 for k in request.form):
                    abort(400)
                _validate_token()
                action = request.form['action']
                if action not in ACTIONS or (action == 'save') != ('title' in request.form):
                    abort(400)
                form.update({k: request.form[k] for k in request.form if k in form})
                if form['weight_basis'] not in WEIGHT_BASES or form['disease'] not in DISEASE_CODES:
                    abort(400)
                try:
                    treatment = build_treatment_request({k: form[k] for k in TREATMENT_FIELDS})
                    if action == 'save':
                        row = save_estimated_pk_run(revision_id, form['weight_basis'], treatment, form['disease'],
                                                    title=form['title'])
                        return redirect(url_for('landscape.saved_pk_run', scenario_id=scenario_id,
                                                revision_id=revision_id, run_id=row.id), code=303)
                    if action == 'compare':
                        comparison = compare_estimated_pk(revision_id, treatment, form['disease'])
                    elif action == 'population':
                        population = calculate_population_pk(revision_id, form['weight_basis'], treatment, form['disease'])
                    else:
                        report = calculate_estimated_pk(revision_id, form['weight_basis'], treatment, form['disease'])
                except (ValueError, OverflowError) as exc:
                    error = str(exc)
                    status = 400
                if action == 'download' and report is not None:
                    return Response(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
                                    mimetype='application/json',
                                    headers={'Content-Disposition': f'attachment; filename="estimated-pk-revision-{revision_id}.json"',
                                             'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
            estimate = (report or population or {}).get('covariate_estimate') or estimate_for_revision(revision_id, form['weight_basis'])
            calculation = report['calculation'] if report else None
            nonce, token = _form_token()
            response = _response('landscape_estimated_pk.html', scenario=scenario, revision=revision, form_token=token,
                                 form=form, basis_options=_basis_options(), disease_codes=('UNKNOWN', 'MM', 'CLL', 'AML', 'ALL', 'OTHER'),
                                 estimate=estimate, report=report, calculation=calculation,
                                 charts=_charts(calculation), comparison=comparison,
                                 overlay=_overlay(comparison) if comparison else [], population=population,
                                 band_chart=_band_chart(population), error=error)
            response.status_code = status
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.set_cookie(COOKIE, nonce, max_age=TTL, httponly=True, secure=request.is_secure,
                                samesite='Strict', path='/landscape/workspace')
            return response
        except ValueError as exc:
            return _error(exc, 409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Estimated PK storage context is temporarily unavailable.', 503)
