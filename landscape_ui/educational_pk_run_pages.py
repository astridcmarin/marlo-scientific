"""Archived educational runs; view/export without parameter catalogs or solver calls."""
import json
import re
from flask import Response, abort, request
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.educational_pk_runs import EducationalPKRun,read_pk_run,export_pk_run,runs_ready
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.saved_scenarios import read_scenario
from .educational_pk_pages import _charts
from .pk_compartment_timeline import build_compartment_timeline
from .workspace_pages import _response
from .scenario_pages import _error


def _context(scenario_id,revision_id):
    scenario=read_scenario(scenario_id);revision=read_revision(revision_id)
    if scenario is None or revision is None or revision.scenario_id!=scenario_id:abort(404)
    runs_ready()
    return scenario,revision


def register_educational_pk_run_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/pk-runs')
    def saved_pk_runs(scenario_id,revision_id):
        if set(request.args)-{'page'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        raw=request.args.get('page','1')
        if not re.fullmatch(r'[1-9][0-9]{0,4}',raw):abort(400)
        page=int(raw)
        try:
            scenario,revision=_context(scenario_id,revision_id)
            count=db.session.scalar(select(func.count()).select_from(EducationalPKRun).where(EducationalPKRun.revision_id==revision_id))
            pages=max(1,(count+24)//25)
            if page>pages:abort(404)
            rows=list(db.session.scalars(select(EducationalPKRun).where(EducationalPKRun.revision_id==revision_id)
                       .order_by(EducationalPKRun.id.desc()).offset((page-1)*25).limit(25)))
            for row in rows:read_pk_run(row.id)
            return _response('landscape_saved_pk_runs.html',scenario=scenario,revision=revision,runs=rows,count=count,page=page,pages=pages)
        except ValueError as exc:return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback();return _error('Saved educational run storage is temporarily unavailable.',503)

    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/pk-runs/<int:run_id>')
    def saved_pk_run(scenario_id,revision_id,run_id):
        if set(request.args)-{'format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        try:
            scenario,revision=_context(scenario_id,revision_id)
            # Check ownership before opening an unrelated archived payload.
            row=db.session.get(EducationalPKRun,run_id)
            if row is None or row.revision_id!=revision_id:abort(404)
            row=read_pk_run(run_id)
            if output=='json':
                return Response(json.dumps(export_pk_run(run_id),indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',
                    headers={'Content-Disposition':f'attachment; filename="saved-educational-pk-run-{run_id}.json"',
                             'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            report=row.payload['report'];review=report['preflight_review']
            response=_response('landscape_saved_pk_run.html',scenario=scenario,revision=revision,run=row,
                report=report,review=review,timeline=build_compartment_timeline(report),charts=_charts(report),inputs_json=json.dumps(review['explicit_model_inputs'],indent=2),
                request_json=json.dumps(review['treatment_request_preview']['request'],indent=2))
            response.headers['X-Content-Type-Options']='nosniff'
            return response
        except ValueError as exc:return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback();return _error('Saved educational run storage is temporarily unavailable.',503)
