"""Explicit, transient clearance perturbations; no archive or patient writes."""
import json
import re
from flask import Response,abort,request
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.educational_pk_runs import EducationalPKRun,read_pk_run
from intelligence_store.educational_pk_sensitivity import clearance_sensitivity,LIMITATION
from .educational_pk_run_pages import _context
from .workspace_pages import COOKIE,TTL,_form_token,_validate_token,_response
from .scenario_pages import _error
from .transit_pages import _chart


def sensitivity_charts(report):
    if not report or not report['points']:return []
    points=report['points'];times=[p['time_h'] for p in points];charts=[]
    for title,unit,baseline,changed in [
        ('Central concentration sensitivity','ng/mL','analytic_baseline_concentration_ng_ml','perturbed_concentration_ng_ml'),
        ('Cumulative exposure sensitivity','ng·h/mL','analytic_baseline_auc_0_t_ng_h_ml','perturbed_auc_0_t_ng_h_ml')]:
        chart=_chart(title,unit,times,[
            {'label':'Analytic baseline','color':'#007b83','dash':'','values':[p[baseline] for p in points]},
            {'label':'Invented clearance variation','color':'#8b5b92','dash':'6 3','values':[p[changed] for p in points]}])
        chart['time_ticks']=[{'x':70+670*i/4,'label':f'{times[-1]*i/4:g}'} for i in range(5)]
        charts.append(chart)
    return charts


def register_educational_pk_sensitivity_pages(bp):
    @bp.route('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/pk-runs/<int:run_id>/sensitivity',methods=['GET','POST'])
    def saved_pk_sensitivity(scenario_id,revision_id,run_id):
        if request.args:abort(400)
        if request.content_length and request.content_length>20000:abort(413)
        try:
            scenario,revision=_context(scenario_id,revision_id)
            row=db.session.get(EducationalPKRun,run_id)
            if row is None or row.revision_id!=revision_id:abort(404)
            row=read_pk_run(run_id)
            factor_text='';note='';report=None;error=None;status=200
            if request.method=='POST':
                allowed={'form_token','action','clearance_factor','assumption_note'}
                if set(request.form)!=allowed or any(len(request.form.getlist(k))!=1 for k in request.form):abort(400)
                _validate_token()
                action=request.form['action']
                if action not in ('calculate','download'):abort(400)
                factor_text=request.form['clearance_factor'];note=request.form['assumption_note']
                try:
                    if len(factor_text)>40 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',factor_text.strip()):
                        raise ValueError('Enter a decimal clearance factor from 0.5 to 2.0.')
                    report=clearance_sensitivity(run_id,float(factor_text),note)
                except (ValueError,OverflowError) as exc:error=str(exc);status=400
                if report is not None and action=='download':
                    return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',
                        headers={'Content-Disposition':f'attachment; filename="educational-clearance-sensitivity-{run_id}.json"',
                            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            nonce,token=_form_token()
            response=_response('landscape_saved_pk_sensitivity.html',scenario=scenario,revision=revision,run=row,
                factor_text=factor_text,note=note,report=report,error=error,form_token=token,
                charts=sensitivity_charts(report),limitation=LIMITATION)
            response.status_code=status
            response.set_cookie(COOKIE,nonce,max_age=TTL,httponly=True,secure=request.is_secure,samesite='Strict',path='/landscape/workspace')
            return response
        except ValueError as exc:return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback();return _error('Clearance sensitivity storage context is temporarily unavailable.',503)
