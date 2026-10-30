"""Patient Lab 2.1f: view and export a saved Kim 2026 run; integrity-checked, never re-run."""
import json
from flask import Response, abort, request
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.kim_pk_runs import KimPKRun, export_kim_pk_run, kim_runs_ready, read_kim_pk_run
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.run_record import RESULT_TYPES, record_for_kim_run
from intelligence_store.saved_scenarios import read_scenario
from .transit_pages import _chart
from .workspace_pages import _response
from .scenario_pages import _error


def _kim_chart(report):
    times = report['times_h']
    chart = _chart('Kim 2026 typical-value concentration', 'ng/mL', times, [
        {'label': 'Total', 'color': '#b5651d', 'dash': '', 'values': report['total_concentration_ng_ml']},
        {'label': 'Unbound', 'color': '#b5651d', 'dash': '6 4', 'values': report['unbound_concentration_ng_ml']}])
    chart['time_ticks'] = [{'x': 70 + 670 * i / 4, 'label': f'{times[-1] * i / 4:g}'} for i in range(5)]
    return chart


def register_kim_pk_run_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/kim-runs/<int:run_id>')
    def saved_kim_run(scenario_id, revision_id, run_id):
        if set(request.args) - {'format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        output = request.args.get('format', 'html')
        if output not in ('html', 'json'):
            abort(400)
        try:
            scenario, revision = read_scenario(scenario_id), read_revision(revision_id)
            if scenario is None or revision is None or revision.scenario_id != scenario_id:
                abort(404)
            kim_runs_ready()
            # Check ownership before opening an unrelated archived payload.
            row = db.session.get(KimPKRun, run_id)
            if row is None or row.revision_id != revision_id:
                abort(404)
            row = read_kim_pk_run(run_id)
            if output == 'json':
                return Response(json.dumps(export_kim_pk_run(run_id), indent=2, ensure_ascii=False, allow_nan=False) + '\n',
                                mimetype='application/json',
                                headers={'Content-Disposition': f'attachment; filename="saved-kim-run-{run_id}.json"',
                                         'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
            report = row.payload['report']
            # Phase 2.5b: runs saved before the model scope existed carry no scope; evaluate the current scope for
            # display only (the archived run is not changed or re-run).
            if 'model_scope' in report:
                scope, scope_saved = report['model_scope'], True
            else:
                from intelligence_store.lenalidomide_scope import kim_scope
                scope, scope_saved = kim_scope(revision.payload['state'], report['declared_disease_code']), False
            response = _response('landscape_saved_kim_run.html', scenario=scenario, revision=revision, run=row,
                                 scope=dict(scope['scope_evaluation'], observed=scope['observed']), scope_saved=scope_saved,
                                 report=report, estimate=report['covariate_estimate'], chart=_kim_chart(report),
                                 request_json=json.dumps(report['treatment_request'], indent=2),
                                 result_type=RESULT_TYPES['typical_value_pk'], record=record_for_kim_run(row))
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        except ValueError as exc:
            return _error(exc, 409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Saved Kim run storage is temporarily unavailable.', 503)
