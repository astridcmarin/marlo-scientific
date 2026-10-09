"""Local diagnostic dashboard; no repairs, catalog refresh or saved data writes."""
import json
from flask import Response,abort,render_template,request
from sqlalchemy import select,inspect
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort
from intelligence_store.validation import validate_platform,LIMITATION

def register_validation_pages(bp):
    @bp.get('/validation')
    def validation_dashboard():
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        try:
            cohorts=list(db.session.scalars(select(AnalysisCohort).where(AnalysisCohort.status=='COMPLETE').order_by(AnalysisCohort.id.desc()))) if inspect(db.engine).has_table(AnalysisCohort.__tablename__) else []
            raw=request.args.get('cohort_id','')
            if raw:
                try:cohort_id=int(raw)
                except ValueError:abort(400)
                if cohort_id<1:abort(400)
            else:cohort_id=cohorts[0].id if cohorts else None
            report=validate_platform(cohort_id) if cohort_id else None
            if output=='json':
                if report is None:abort(400)
                response=Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),mimetype='application/json')
                response.headers['Content-Disposition']=f'attachment; filename="platform_validation_cohort_{cohort_id}.json"'
            else:response=Response(render_template('landscape_validation.html',report=report,cohorts=cohorts,cohort_id=cohort_id,limitation=LIMITATION))
            response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
            return response
        except SQLAlchemyError:
            db.session.rollback()
            return Response(render_template('landscape_message.html',message='Validation storage is unavailable. Check database configuration and migrations.'),status=503,headers={'Cache-Control':'no-store'})
