"""Local workspace pages with signed, browser-bound save submissions."""
import hmac
import json
import os
from pathlib import Path
import secrets
from flask import Response, abort, current_app, redirect, render_template, request, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort
from intelligence_store.workspace_models import IntelligenceBrief
from intelligence_store.workspaces import (SECTIONS, METRIC_LABELS, validate_inputs, workspace_ready,
    save_brief,read_brief,brief_tables)

COOKIE='intelligence_workspace_nonce'
TTL=7200


def _signer():
    secret=current_app.config.get('INTELLIGENCE_WORKSPACE_SECRET')
    if not secret:
        root=Path(__file__).resolve().parent.parent/'instance'
        root.mkdir(exist_ok=True)
        path=root/'workspace_secret.key'
        if not path.exists():
            try:
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(32))
            except FileExistsError:pass
        secret=path.read_text().strip()
        if len(secret)<32:raise ValueError('Workspace signing key is invalid.')
        current_app.config['INTELLIGENCE_WORKSPACE_SECRET']=secret
    return URLSafeTimedSerializer(secret,salt='intelligence-workspace-v1')


def _form_token():
    nonce=request.cookies.get(COOKIE) or secrets.token_hex(32)
    token=_signer().dumps({'nonce':nonce,'save_key':secrets.token_hex(32)})
    return nonce,token


def _validate_token():
    origin=request.headers.get('Origin')
    if origin and origin!=request.host_url.rstrip('/'):abort(403)
    try:data=_signer().loads(request.form.get('form_token',''),max_age=TTL)
    except (BadSignature,SignatureExpired):abort(403)
    nonce=request.cookies.get(COOKIE,'')
    if not nonce or not hmac.compare_digest(data.get('nonce',''),nonce):abort(403)
    return data['save_key']


def _response(template,**context):
    response=Response(render_template(template,**context))
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response


def register_workspace_pages(bp):
    @bp.route('/workspace',methods=['GET','POST'])
    def workspace():
        inputs={'title':'','notes':'','cohort_id':request.args.get('cohort_id',''),
            'compare_id':'','pinned':'','sections':['landscape','regulatory']}
        error=None
        try:
            workspace_ready()
            if request.method=='POST':
                if request.content_length is None or request.content_length>65536:abort(413)
                save_key=_validate_token()
                inputs={k:request.form.get(k,'') for k in ('title','notes','cohort_id','compare_id','pinned')}
                inputs['sections']=['landscape',*request.form.getlist('sections')]
                try:
                    ids=[int(inputs['cohort_id'])]
                    if inputs['compare_id']:ids.append(int(inputs['compare_id']))
                    parsed=validate_inputs(inputs['title'],inputs['notes'],ids,inputs['sections'],inputs['pinned'])
                    saved=save_brief(parsed,save_key)
                    return redirect(url_for('landscape.workspace_brief',brief_id=saved.id),code=303)
                except ValueError as exc:error=str(exc)
            cohorts=list(db.session.scalars(select(AnalysisCohort).where(AnalysisCohort.status=='COMPLETE').order_by(AnalysisCohort.id.desc())))
            if not inputs['cohort_id'] and cohorts:inputs['cohort_id']=str(cohorts[0].id)
            page=request.args.get('page',1,type=int)
            if not page or page<1:abort(404)
            from sqlalchemy import func
            count=db.session.scalar(select(func.count()).select_from(IntelligenceBrief))
            if page>max(1,(count+19)//20):abort(404)
            saved=list(db.session.scalars(select(IntelligenceBrief).order_by(IntelligenceBrief.id.desc()).offset((page-1)*20).limit(20)))
            nonce,token=_form_token()
            response=_response('landscape_workspace.html',inputs=inputs,error=error,cohorts=cohorts,
                briefs=saved,sections=SECTIONS,form_token=token,count=count,page=page,
                previous_url=url_for('landscape.workspace',page=page-1) if page>1 else None,
                next_url=url_for('landscape.workspace',page=page+1) if page*20<count else None)
            response.status_code=400 if error else 200
            response.set_cookie(COOKIE,nonce,max_age=TTL,httponly=True,secure=request.is_secure,samesite='Strict',path='/landscape/workspace')
            return response
        except ValueError as exc:
            return Response(render_template('landscape_message.html',message=str(exc)),status=409,headers={'Cache-Control':'no-store'})
        except (SQLAlchemyError,OSError):
            db.session.rollback()
            return Response(render_template('landscape_message.html',message='Workspace storage is temporarily unavailable.'),status=503,headers={'Cache-Control':'no-store'})

    @bp.get('/workspace/brief/<int:brief_id>')
    def workspace_brief(brief_id):
        output=request.args.get('format','html')
        if output not in ('html','json','pdf'):abort(400)
        try:
            brief=read_brief(brief_id)
            if brief is None:abort(404)
            if output=='json':
                response=Response(json.dumps({'brief_id':brief.id,'payload_sha256':brief.payload_sha256,'payload':brief.payload},indent=2,ensure_ascii=False,allow_nan=False),mimetype='application/json')
            elif output=='pdf':
                try:
                    from intelligence_store.brief_pdf import render_brief_pdf
                except ImportError:
                    return Response('Install the Step 19 ReportLab dependency to download PDFs.',status=503)
                response=Response(render_brief_pdf(brief),mimetype='application/pdf')
            else:
                return _response('landscape_workspace_brief.html',brief=brief,payload=brief.payload,tables=brief_tables,
                    metric_labels=METRIC_LABELS,overlap=(len(set(brief.payload['cohorts'][0]['summary']['evidence'])&set(brief.payload['cohorts'][1]['summary']['evidence'])) if len(brief.payload['cohorts'])==2 else None))
            response.headers['Content-Disposition']=f'attachment; filename="intelligence_brief_{brief.id}.{output}"'
            response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
            return response
        except ValueError as exc:
            return Response(render_template('landscape_message.html',message=str(exc)),status=409,headers={'Cache-Control':'no-store'})
        except (SQLAlchemyError,OSError):
            db.session.rollback()
            return Response(render_template('landscape_message.html',message='Saved brief is temporarily unavailable.'),status=503,headers={'Cache-Control':'no-store'})
