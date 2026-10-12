"""Search saved disease-query cohorts without merging runs or refreshing sources."""
import json
from datetime import timezone
from flask import Response, abort, render_template, request
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort, CohortTrial

PAGE_SIZE = 20


def _utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace('+00:00','Z')


def register_disease_library_pages(bp):
    @bp.get('/diseases')
    def disease_library():
        if set(request.args)-{'q','status','page','format'} or any(len(request.args.getlist(k))!=1 for k in request.args):
            abort(400)
        q=request.args.get('q','').strip()
        status=request.args.get('status','COMPLETE')
        raw_page=request.args.get('page','1')
        output=request.args.get('format','html')
        if len(q)>120 or status not in ('ALL','COMPLETE','PARTIAL','RUNNING','FAILED') or output not in ('html','json'):
            abort(400)
        if not raw_page.isascii() or not raw_page.isdigit() or len(raw_page)>6 or int(raw_page)<1:
            abort(400)
        page=int(raw_page)
        criteria=[]
        if q:
            criteria.append(AnalysisCohort.condition.icontains(q,autoescape=True))
        if status!='ALL':
            criteria.append(AnalysisCohort.status==status)
        try:
            count=db.session.scalar(select(func.count()).select_from(AnalysisCohort).where(*criteria))
            pages=max(1,(count+PAGE_SIZE-1)//PAGE_SIZE)
            if page>pages: abort(404)
            cohorts=list(db.session.scalars(select(AnalysisCohort).where(*criteria)
                         .order_by(AnalysisCohort.id.desc()).offset((page-1)*PAGE_SIZE).limit(PAGE_SIZE)))
            ids=[c.id for c in cohorts]
            members=dict(db.session.execute(select(CohortTrial.cohort_id,func.count())
                         .where(CohortTrial.cohort_id.in_(ids)).group_by(CohortTrial.cohort_id)).all()) if ids else {}
            rows=[]
            for c in cohorts:
                membership=members.get(c.id,0)
                consistent=c.expected_count is not None and c.expected_count==c.retrieved_count==membership
                rows.append({'cohort_id':c.id,'condition':c.condition,'status':c.status,'scope':c.scope,
                             'start_year':c.start_year,'end_year':c.end_year,
                             'finished_at_utc':_utc(c.finished_at_utc),'started_at_utc':_utc(c.started_at_utc),
                             'recorded_trial_count':c.retrieved_count,'expected_api_count':c.expected_count,
                             'membership_count':membership,'record_counts_consistent':consistent,
                             'open_analysis':c.status=='COMPLETE' and consistent,
                             'query_params':c.query_params,'api_url':c.api_url,
                             'query_version':c.query_version,'normalization_version':c.normalization_version})
        except SQLAlchemyError:
            db.session.rollback()
            return Response('Saved disease library unavailable. Check the local storage installation.',
                            status=503,mimetype='text/plain',headers={'Cache-Control':'no-store'})
        report={'schema_version':'saved-disease-library-v1','selection':{'query':q,'status':status},
                'page':page,'page_size':PAGE_SIZE,'page_count':pages,'matching_cohort_runs':count,'entries':rows,
                'scope':'Saved query runs, not a disease ontology or comprehensive disease coverage. Runs can overlap and are never summed as unique studies.',
                'checks':'Status and cohort/membership counts only; snapshot payloads, source currency and scientific suitability are not verified here.',
                'network_refresh_performed':False,'patient_simulation_performed':False}
        if output=='json':
            response=Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json')
            response.headers['Content-Disposition']='attachment; filename="saved-disease-cohorts-page.json"'
        else:
            response=Response(render_template('landscape_disease_library.html',report=report,q=q,status=status))
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
