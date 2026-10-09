"""Separate mathematical verification from unresolved scientific validation."""
import json
from flask import Response,abort,request
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.educational_pk_runs import EducationalPKRun
from intelligence_store.educational_pk_audit import audit_pk_run
from .educational_pk_run_pages import _context
from .workspace_pages import _response
from .scenario_pages import _error


def register_educational_pk_audit_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/pk-runs/<int:run_id>/audit')
    def saved_pk_audit(scenario_id,revision_id,run_id):
        if set(request.args)-{'format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        try:
            scenario,revision=_context(scenario_id,revision_id)
            row=db.session.get(EducationalPKRun,run_id)
            if row is None or row.revision_id!=revision_id:abort(404)
            report=audit_pk_run(run_id)
            if output=='json':
                return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers={
                    'Content-Disposition':f'attachment; filename="educational-pk-audit-{run_id}.json"',
                    'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            return _response('landscape_saved_pk_audit.html',scenario=scenario,revision=revision,run=row,report=report)
        except ValueError as exc:return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback();return _error('Educational audit storage is temporarily unavailable.',503)
