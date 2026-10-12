import json
from flask import Response,abort,render_template,request
from intelligence_store.bortezomib_assumption_sensitivity import build_assumption_sensitivity
from .bortezomib_timecourse_pages import charts

def register_bortezomib_assumption_pages(bp):
    @bp.get('/simulation-lab/bortezomib-assumptions')
    def bortezomib_assumptions():
        if set(request.args)-{'format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        fmt=request.args.get('format','html')
        if fmt not in ('html','json'):abort(400)
        try:report=build_assumption_sensitivity()
        except ValueError:abort(503,'Source or calculation unavailable; comparison withheld.')
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if fmt=='json':
            headers['Content-Disposition']='attachment; filename="bortezomib-assumption-sensitivity.json"'
            return Response(json.dumps(report,indent=2,allow_nan=False),mimetype='application/json',headers=headers)
        return Response(render_template('landscape_bortezomib_assumptions.html',report=report,
            curves=[charts(s['run']) for s in report['scenarios']],colors=['#087f8c','#a13c77','#9b6100']),headers=headers)
