"""Browser-bound append forms and frozen synthetic state views."""
import copy
import json
from flask import Response, abort, redirect, request, url_for
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.patient_state import (UNITS, digest, state_from_scenario, validate_patient_state)
from intelligence_store.patient_state_revisions import (PatientStateRevision, revisions_ready,
    read_revision, save_revision, export_revision)
from intelligence_store.saved_scenarios import read_scenario
from .workspace_pages import COOKIE, TTL, _form_token, _validate_token, _signer, _response
from .scenario_pages import _error

LABELS = {'age_years':'Age', 'biological_sex':'Biological sex', 'weight':'Weight', 'height':'Height',
    'egfr_indexed':'Indexed eGFR', 'creatinine_clearance':'Creatinine clearance',
    'serum_creatinine':'Serum creatinine', 'alt':'ALT', 'ast':'AST',
    'albumin':'Albumin', 'total_bilirubin':'Total bilirubin'}
GROUPS = [('Patient descriptors',['age_years','biological_sex','weight','height']),
          ('Renal measures',['egfr_indexed','creatinine_clearance','serum_creatinine']),
          ('Laboratory values',['alt','ast','albumin','total_bilirubin'])]


def scenario_state_summary(scenario_id):
    """A bad state must not hide the original saved reference report."""
    try:
        revisions_ready()
        count=db.session.scalar(select(func.count()).select_from(PatientStateRevision)
                                .where(PatientStateRevision.scenario_id==scenario_id))
        latest=db.session.scalar(select(PatientStateRevision).where(PatientStateRevision.scenario_id==scenario_id)
                                 .order_by(PatientStateRevision.revision_number.desc()).limit(1))
        if latest:
            read_revision(latest.id)
        return {'available':True,'count':count,'latest':latest,'error':None}
    except ValueError as exc:
        return {'available':False,'count':None,'latest':None,'error':str(exc)}
    except SQLAlchemyError:
        db.session.rollback()
        return {'available':False,'count':None,'latest':None,'error':'Patient-state storage is temporarily unavailable.'}


def _scenario(scenario_id):
    row=read_scenario(scenario_id)
    if row is None:
        abort(404)
    return row


def _base(scenario, parent_id):
    if parent_id is None:
        return state_from_scenario(scenario.payload['analysis']['report']['profile']),None
    parent=read_revision(parent_id)
    if parent is None or parent.scenario_id!=scenario.id:
        abort(404)
    return copy.deepcopy(parent.payload['state']),parent


def _ticket(scenario,base,parent):
    return _signer().dumps({'purpose':'append-patient-state','scenario_id':scenario.id,
        'scenario_sha256':scenario.payload_sha256,'parent_id':parent.id if parent else None,
        'parent_sha256':parent.payload_sha256 if parent else None,'base_sha256':digest(base)})


def _history(scenario_id,page):
    count=db.session.scalar(select(func.count()).select_from(PatientStateRevision)
                            .where(PatientStateRevision.scenario_id==scenario_id))
    pages=max(1,(count+24)//25)
    if page<1 or page>pages:
        abort(404)
    rows=list(db.session.scalars(select(PatientStateRevision).where(PatientStateRevision.scenario_id==scenario_id)
              .order_by(PatientStateRevision.revision_number.desc()).offset((page-1)*25).limit(25)))
    for row in rows:
        read_revision(row.id)
    return rows,count,pages


def _editor(scenario,base,parent,*,inputs=None,title='Patient state',error=None,status=200,ticket=None,page=1):
    history,count,pages=_history(scenario.id,page)
    nonce,token=_form_token()
    response=_response('landscape_patient_state_editor.html',scenario=scenario,
        fields=inputs if inputs is not None else base['fields'],labels=LABELS,units=UNITS,groups=GROUPS,
        parent=parent,title=title,error=error,ticket=ticket or _ticket(scenario,base,parent),form_token=token,
        history=history,count=count,page=page,pages=pages)
    response.status_code=status
    response.set_cookie(COOKIE,nonce,max_age=TTL,httponly=True,secure=request.is_secure,
                        samesite='Strict',path='/landscape/workspace')
    return response


def _form_state():
    allowed={'ticket','form_token','title'}|{f'{prefix}__{name}' for prefix in ('value','origin','time','source') for name in UNITS}
    if set(request.form)!=allowed or any(len(request.form.getlist(key))!=1 for key in request.form):
        raise ValueError('The form contains unsupported or duplicate fields. Reload the editor.')
    fields={}
    for name,unit in UNITS.items():
        value=request.form.get('value__'+name,'').strip()
        fields[name]={'value':value if value else None,'unit':unit,
            'origin':request.form.get('origin__'+name,'unknown') if value else 'unknown',
            'observed_at':request.form.get('time__'+name,'').strip() or None,
            'source_ref':request.form.get('source__'+name,'').strip() or None}
    return {'schema_version':'synthetic-patient-state-v1','purpose':'synthetic_educational','fields':fields}


def register_patient_state_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state')
    def patient_state_edit(scenario_id):
        try:
            revisions_ready();scenario=_scenario(scenario_id)
            latest=db.session.scalar(select(PatientStateRevision).where(PatientStateRevision.scenario_id==scenario_id)
                                     .order_by(PatientStateRevision.revision_number.desc()).limit(1))
            base,parent=_base(scenario,latest.id if latest else None)
            try:page=int(request.args.get('page','1'))
            except ValueError:abort(400)
            return _editor(scenario,base,parent,page=page)
        except ValueError as exc:
            return _error(exc)
        except (SQLAlchemyError,OSError):
            db.session.rollback()
            return _error('Patient-state storage is temporarily unavailable.',503)

    @bp.post('/workspace/scenarios/<int:scenario_id>/patient-state/save')
    def patient_state_save(scenario_id):
        if request.content_length is None or request.content_length>32768:
            abort(413)
        _validate_token()
        try:
            revisions_ready();scenario=_scenario(scenario_id)
            try:ticket=_signer().loads(request.form.get('ticket',''),max_age=TTL)
            except (BadSignature,SignatureExpired):abort(403)
            expected={'purpose','scenario_id','scenario_sha256','parent_id','parent_sha256','base_sha256'}
            if not isinstance(ticket,dict) or set(ticket)!=expected or ticket['purpose']!='append-patient-state' or ticket['scenario_id']!=scenario_id:
                abort(403)
            base,parent=_base(scenario,ticket['parent_id'])
            if (ticket['scenario_sha256']!=scenario.payload_sha256 or ticket['base_sha256']!=digest(base)
                    or ticket['parent_sha256']!=(parent.payload_sha256 if parent else None)):
                return _error('The captured source state changed. Reload the editor.',409)
            inputs=copy.deepcopy(base['fields']);title=request.form.get('title','Patient state')
            try:
                raw=_form_state();inputs=raw['fields'];canonical=validate_patient_state(raw)
                for name,field in canonical['fields'].items():
                    if field['origin']=='legacy_scenario' and field!=base['fields'][name]:
                        raise ValueError(f'{LABELS[name]}: changed copied inputs require synthetic_input or assumption origin.')
                saved=save_revision(scenario_id,canonical,parent_revision_id=ticket['parent_id'],title=title)
                return redirect(url_for('landscape.patient_state_detail',scenario_id=scenario_id,revision_id=saved.id),code=303)
            except ValueError as exc:
                status=409 if str(exc).startswith(('Stale parent','Another revision')) else 400
                return _editor(scenario,base,parent,inputs=inputs,title=title,error=str(exc),
                               status=status,ticket=request.form.get('ticket'))
        except ValueError as exc:
            return _error(exc)
        except (SQLAlchemyError,OSError):
            db.session.rollback()
            return _error('Patient-state save is temporarily unavailable.',503)

    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>')
    def patient_state_detail(scenario_id,revision_id):
        output=request.args.get('format','html')
        if output not in ('html','json'):
            abort(400)
        try:
            scenario=_scenario(scenario_id);row=read_revision(revision_id)
            if row is None or row.scenario_id!=scenario_id:
                abort(404)
            if output=='json':
                response=Response(json.dumps(export_revision(revision_id),indent=2,ensure_ascii=False,allow_nan=False),mimetype='application/json')
                response.headers['Content-Disposition']=f'attachment; filename="patient_state_revision_{revision_id}.json"'
                response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
                return response
            return _response('landscape_patient_state_detail.html',scenario=scenario,revision=row,
                             payload=row.payload,labels=LABELS)
        except ValueError as exc:
            return _error(exc)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Patient-state revision is temporarily unavailable.',503)
