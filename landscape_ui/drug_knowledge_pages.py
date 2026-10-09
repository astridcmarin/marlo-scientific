"""Drug reference inventory and a unified, evidence-linked detail page."""
import json
from flask import Response,abort,request,render_template
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.summaries import summarize_cohort
from intelligence_store.drug_knowledge import build_drug_knowledge


def register_drug_knowledge_pages(bp,choose_cohort,complete_cohorts):
    def page(entity=None):
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        try:
            cohort_id=choose_cohort()
            cohorts=complete_cohorts()
            report=build_drug_knowledge(summarize_cohort(cohort_id)) if cohort_id else None
            entry=None
            if entity:
                if report is None:abort(404)
                entry=next((r for r in report['entries'] if r['entity_id']==entity),None)
                if entry is None:abort(404)
            if output=='json':
                if report is None:abort(400)
                # Export the complete inventory, even when the HTML gap table is filtered/paged.
                response=Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),mimetype='application/json')
                response.headers['Content-Disposition']=f'attachment; filename="drug_knowledge_cohort_{cohort_id}.json"'
            else:
                q=request.args.get('q','').strip()
                if len(q)>120:abort(400)
                rows=[{'nct_id':nct,**ref} for nct,ref in entry['evidence'].items()] if entry else report['unmapped_groups'] if report else []
                if q and not entry:rows=[r for r in rows if q.casefold() in r['label'].casefold() or any(q.casefold() in v['label'].casefold() for v in r['variants'])]
                number=request.args.get('page',1,type=int)
                pages=max(1,(len(rows)+49)//50)
                if not number or number<1 or number>pages:abort(404)
                response=Response(render_template('landscape_drug_detail.html' if entity else 'landscape_drug_knowledge.html',
                    report=report,entry=entry,cohorts=cohorts,cohort_id=cohort_id,rows=rows[(number-1)*50:number*50],
                    filtered_count=len(rows),q=q,page=number,page_count=pages))
            response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
            return response
        except ValueError as exc:
            return Response(render_template('landscape_message.html',message=str(exc)),status=409,headers={'Cache-Control':'no-store'})
        except SQLAlchemyError:
            db.session.rollback()
            return Response(render_template('landscape_message.html',message='Drug knowledge evidence is temporarily unavailable.'),status=503,headers={'Cache-Control':'no-store'})
    @bp.get('/drugs')
    def drug_knowledge():return page()
    @bp.get('/drugs/<entity>')
    def drug_knowledge_detail(entity):return page(entity)
