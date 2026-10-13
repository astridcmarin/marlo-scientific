"""Watchlist forms and source views using the existing workspace CSRF boundary."""
from functools import wraps
import json
from flask import Response,abort,redirect,render_template,request,url_for
from sqlalchemy import select,func
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort
from intelligence_store.watchlists import (TrialWatchlist,WatchlistTrial,STATES,ready,get_watchlist,create_watchlist,
    add_trials,get_trial,checked_trial,update_review,export_watchlist,ReviewConflict)
from .workspace_pages import _form_token,_validate_token,COOKIE,TTL


def _page(template,**context):
    nonce,token=_form_token()
    response=Response(render_template(template,form_token=token,states=STATES,**context))
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.set_cookie(COOKIE,nonce,max_age=TTL,httponly=True,secure=request.is_secure,samesite='Strict',path='/landscape/workspace')
    return response


def _guard(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        try:
            ready()
            if request.method=='POST':
                if request.content_length is None or request.content_length>65536:abort(413)
                key=_validate_token()
                return fn(*args,save_key=key,**kwargs)
            return fn(*args,**kwargs)
        except ValueError as exc:
            db.session.rollback()
            return Response(render_template('landscape_message.html',message=str(exc)),status=409,headers={'Cache-Control':'no-store'})
        except (SQLAlchemyError,OSError):
            db.session.rollback()
            return Response(render_template('landscape_message.html',message='Watchlist storage is temporarily unavailable.'),status=503,headers={'Cache-Control':'no-store'})
    return wrapped


def _pagination(count):
    raw=request.args.get('page','1')
    try:page=int(raw)
    except ValueError:abort(404)
    if not 1<=page<=max(1,(count+24)//25):abort(404)
    return page


def register_watchlist_pages(bp):
    @bp.route('/workspace/watchlists',methods=['GET','POST'])
    @_guard
    def watchlists(save_key=None):
        title='';selected=request.args.get('cohort_id','');error=None
        if request.method=='POST':
            title=request.form.get('title','');selected=request.form.get('cohort_id','')
            try:
                row=create_watchlist(title,int(selected),save_key)
                return redirect(url_for('landscape.watchlist',list_id=row.id),code=303)
            except ValueError as exc:error=str(exc)
        cohorts=list(db.session.scalars(select(AnalysisCohort).where(AnalysisCohort.status=='COMPLETE').order_by(AnalysisCohort.id.desc())))
        count=db.session.scalar(select(func.count()).select_from(TrialWatchlist));page=_pagination(count)
        rows=list(db.session.scalars(select(TrialWatchlist).order_by(TrialWatchlist.id.desc()).offset((page-1)*25).limit(25)))
        response=_page('landscape_watchlists.html',title=title,selected=selected,error=error,cohorts=cohorts,lists=rows,count=count,page=page,has_next=page*25<count)
        if error:response.status_code=400
        return response

    @bp.route('/workspace/watchlists/<int:list_id>',methods=['GET','POST'])
    @_guard
    def watchlist(list_id,save_key=None):
        row=get_watchlist(list_id)
        if row is None:abort(404)
        error=None;draft=''
        if request.method=='POST':
            draft=request.form.get('nct_ids','')
            try:
                add_trials(list_id,draft)
                return redirect(url_for('landscape.watchlist',list_id=list_id),code=303)
            except ValueError as exc:error=str(exc)
        output=request.args.get('format','html')
        if output=='json':
            if request.method!='GET':abort(400)
            response=Response(json.dumps(export_watchlist(list_id),indent=2,ensure_ascii=False,allow_nan=False),mimetype='application/json')
            response.headers['Content-Disposition']=f'attachment; filename="trial_watchlist_{list_id}.json"'
            response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
            return response
        if output!='html':abort(400)
        state=request.args.get('state','all')
        if state!='all' and state not in STATES:abort(400)
        counts={s:0 for s in STATES}
        for status,total in db.session.execute(select(WatchlistTrial.review_status,func.count()).where(WatchlistTrial.watchlist_id==list_id).group_by(WatchlistTrial.review_status)):counts[status]=total
        selected_count=sum(counts.values()) if state=='all' else counts[state];page=_pagination(selected_count)
        query=select(WatchlistTrial).where(WatchlistTrial.watchlist_id==list_id)
        if state!='all':query=query.where(WatchlistTrial.review_status==state)
        entries=[checked_trial(r,row) for r in db.session.scalars(query.order_by(WatchlistTrial.nct_id).offset((page-1)*25).limit(25))]
        response=_page('landscape_watchlist.html',watchlist=row,entries=entries,counts=counts,total=sum(counts.values()),state=state,page=page,has_next=page*25<selected_count,error=error,draft=draft)
        if error:response.status_code=400
        return response

    @bp.route('/workspace/watchlists/<int:list_id>/trial/<nct_id>',methods=['GET','POST'])
    @_guard
    def watchlist_trial(list_id,nct_id,save_key=None):
        watchlist=get_watchlist(list_id)
        if watchlist is None:abort(404)
        row=get_trial(list_id,nct_id)
        if row is None:abort(404)
        draft={'notes':row.notes,'review_status':row.review_status};error=None;conflict=False
        if request.method=='POST':
            draft={k:request.form.get(k,'') for k in ('notes','review_status')}
            try:
                update_review(list_id,nct_id,draft['review_status'],draft['notes'],int(request.form.get('version','')))
                return redirect(url_for('landscape.watchlist_trial',list_id=list_id,nct_id=nct_id),code=303)
            except ValueError as exc:
                error=str(exc);conflict=isinstance(exc,ReviewConflict)
                row=get_trial(list_id,nct_id)
        response=_page('landscape_watchlist_trial.html',watchlist=watchlist,row=row,draft=draft,error=error,conflict=conflict)
        if error:response.status_code=409 if conflict else 400
        return response
