"""Published aggregate observations and model-bound review, without patient data."""
import json
from flask import Response,abort,render_template,request
from intelligence_store.bortezomib_evidence_review import build_evidence_review


def register_bortezomib_evidence_pages(bp):
    @bp.get('/simulation-lab/bortezomib-evidence')
    def bortezomib_evidence_review():
        if set(request.args)-{'format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        try:report=build_evidence_review()
        except ValueError:abort(503,'Source extraction missing or altered; evidence review withheld.')
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="bortezomib-evidence-review.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',
                mimetype='application/json',headers=headers)
        return Response(render_template('landscape_bortezomib_evidence.html',report=report),headers=headers)
