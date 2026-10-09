"""Explicit, transient educational PK calculations in the existing workspace."""
import json
from flask import Response, abort, request, redirect, url_for
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.patient_state_revisions import read_revision
from intelligence_store.saved_scenarios import read_scenario
from intelligence_store.educational_pk import calculate_educational_pk
from intelligence_store.educational_pk_runs import save_pk_run
from intelligence_store.pk_model_inputs import model_input_example, _no_duplicate_keys
from intelligence_store.treatment_requests import treatment_request_example
from .workspace_pages import COOKIE, TTL, _form_token, _validate_token, _response
from .scenario_pages import _error
from .transit_pages import _chart
from .educational_pk_input_builder import BUILDER_FIELDS, build_synthetic_inputs


def _json_input(text):
    if len(text.encode('utf-8')) > 65536:
        raise ValueError('Each JSON input must be at most 64 KiB.')
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON number.')))
    except (json.JSONDecodeError, RecursionError):
        raise ValueError('Supply valid JSON objects in both input boxes.') from None


def _charts(report):
    if not report or not report['points']:
        return []
    points=report['points']; times=[p['time_h'] for p in points]
    charts=[]
    for title,unit,key in [('Central concentration','ng/mL','concentration_ng_ml'),
                           ('Cumulative exposure','ng·h/mL','auc_0_t_ng_h_ml')]:
        chart=_chart(title,unit,times,[{'label':title,'color':'#007b83','dash':'',
                                     'values':[p[key] for p in points]}])
        chart['time_ticks']=[{'x':70+670*i/4,'label':f'{times[-1]*i/4:g}'} for i in range(5)]
        charts.append(chart)
    return charts


def register_educational_pk_pages(bp):
    @bp.route('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/educational-pk',methods=['GET','POST'])
    def educational_pk(scenario_id,revision_id):
        if request.args:abort(400)
        if request.content_length and request.content_length>160000:abort(413)
        try:
            scenario=read_scenario(scenario_id); revision=read_revision(revision_id)
            if scenario is None or revision is None or revision.scenario_id!=scenario_id:abort(404)
            inputs_text=''; treatment_text=''; disease='UNKNOWN'; report=None; error=None; status=200; title=''
            builder={key:'' for key in BUILDER_FIELDS}; built=False
            if request.method=='POST':
                allowed={'form_token','action','inputs','treatment','disease'}
                builder_allowed=BUILDER_FIELDS|{'form_token','action','disease'}
                if set(request.form) not in (allowed,allowed|{'title'},builder_allowed) or any(len(request.form.getlist(k))!=1 for k in request.form):abort(400)
                _validate_token()
                action=request.form['action']
                if action not in ('example','calculate','download','save','build'):abort(400)
                title=request.form.get('title','')
                if action=='save' and 'title' not in request.form:abort(400)
                inputs_text=request.form.get('inputs',''); treatment_text=request.form.get('treatment',''); disease=request.form['disease']
                if disease not in ('UNKNOWN','MM','CLL','AML','ALL','OTHER'):abort(400)
                if (action=='build') != (set(request.form)==builder_allowed):abort(400)
                if action=='build':
                    builder={key:request.form[key] for key in BUILDER_FIELDS}
                    try:
                        inputs,treatment=build_synthetic_inputs(builder)
                        inputs_text=json.dumps(inputs,indent=2); treatment_text=json.dumps(treatment,indent=2)
                        built=True
                    except ValueError as exc:
                        error=str(exc);status=400
                elif action=='example':
                    inputs_text=json.dumps(model_input_example(),indent=2)
                    treatment_text=json.dumps(treatment_request_example(),indent=2)
                    # Filling examples does not declare disease or execute a model.
                else:
                    try:
                        if action=='save':
                            row=save_pk_run(revision_id,_json_input(inputs_text),_json_input(treatment_text),disease,title=title)
                            return redirect(url_for('landscape.saved_pk_run',scenario_id=scenario_id,revision_id=revision_id,run_id=row.id),code=303)
                        report=calculate_educational_pk(revision_id,_json_input(inputs_text),_json_input(treatment_text),disease)
                    except (ValueError,OverflowError) as exc:
                        error=str(exc);status=400
                    if report is not None and action=='download':
                        return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',
                            headers={'Content-Disposition':f'attachment; filename="educational-pk-revision-{revision_id}.json"',
                                     'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            nonce,token=_form_token()
            response=_response('landscape_educational_pk.html',scenario=scenario,revision=revision,form_token=token,
                inputs_text=inputs_text,treatment_text=treatment_text,title=title,disease=disease,report=report,error=error,charts=_charts(report),builder=builder,built=built)
            response.status_code=status
            response.headers['X-Content-Type-Options']='nosniff'
            response.set_cookie(COOKIE,nonce,max_age=TTL,httponly=True,secure=request.is_secure,samesite='Strict',path='/landscape/workspace')
            return response
        except ValueError as exc:return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Educational PK storage context is temporarily unavailable.',503)

    # Register the bounded archive-variation workflow without changing the blueprint initializer.
    from .educational_pk_variation_pages import register_educational_pk_variation_pages
    register_educational_pk_variation_pages(bp)
