"""Read-only synthetic input comparison pages."""
import json
import re
from flask import Response, abort, request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.patient_state_revisions import PatientStateRevision, revisions_ready
from intelligence_store.patient_state_comparison import compare_revisions, LIMITATION
from intelligence_store.saved_scenarios import read_scenario
from .patient_state_pages import LABELS
from .workspace_pages import _response
from .scenario_pages import _error

CATEGORIES={'unchanged':'Unchanged','value_changed':'Value changed','became_known':'Unknown → known',
            'became_unknown':'Known → unknown','metadata_only':'Metadata only'}


def register_patient_state_compare_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/compare')
    def patient_state_compare(scenario_id):
        if set(request.args)-{'left','right','format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        left=request.args.get('left');right=request.args.get('right')
        if (left is None)!=(right is None):abort(400)
        if left is not None and (not re.fullmatch(r'[1-9][0-9]{0,9}',left) or not re.fullmatch(r'[1-9][0-9]{0,9}',right)):abort(400)
        try:
            scenario=read_scenario(scenario_id)
            if scenario is None:abort(404)
            revisions_ready()
            recent=list(db.session.scalars(select(PatientStateRevision).where(PatientStateRevision.scenario_id==scenario_id)
                         .order_by(PatientStateRevision.revision_number.desc()).limit(2)))
            if left is None and len(recent)==2:left,right=str(recent[1].id),str(recent[0].id)
            report=compare_revisions(int(left),int(right),scenario_id=scenario_id) if left is not None else None
            if output=='json':
                if report is None:abort(400)
                response=Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),mimetype='application/json')
                response.headers['Content-Disposition']=f'attachment; filename="patient_state_comparison_{left}_{right}.json"'
                response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
                return response
            return _response('landscape_patient_state_compare.html',scenario=scenario,report=report,
                             left=left or '',right=right or '',labels=LABELS,categories=CATEGORIES,limitation=LIMITATION)
        except ValueError as exc:return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Patient-state comparison storage is temporarily unavailable.',503)
