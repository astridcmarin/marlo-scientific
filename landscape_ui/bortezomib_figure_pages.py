"""Read-only provisional figure review."""
import json
from flask import Response,abort,render_template,request
from intelligence_store.bortezomib_figure_review import build_figure_review

def register_bortezomib_figure_pages(bp):
    @bp.get('/simulation-lab/bortezomib-figure-review')
    def bortezomib_figure_review():
        if set(request.args)-{'format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        try:report=build_figure_review()
        except ValueError:abort(503,'Source extraction missing or altered; review withheld.')
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="bortezomib-figure-review.json"'
            return Response(json.dumps(report,indent=2,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        return Response(render_template('landscape_bortezomib_figures.html',report=report),headers=headers)
