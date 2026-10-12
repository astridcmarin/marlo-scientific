import json,math
from flask import Response,abort,render_template,request
from intelligence_store.bortezomib_timecourse import build_timecourse

def charts(report):
    rows=report['points'];end=report['reference']['regimen']['end_time_h']
    def coords(kind):
        values=[]
        for r in rows:
            if kind=='pk':
                if r['concentration_nm']<=0:continue
                y=230-200*(math.log10(r['concentration_nm'])+2)/5
            else:y=230-2*r['activity_percent']
            values.append(f"{60+680*r['time_h']/end:.2f},{y:.2f}")
        return ' '.join(values)
    return {'pk':coords('pk'),'pd':coords('pd')}

def register_bortezomib_timecourse_pages(bp):
    @bp.get('/simulation-lab/bortezomib-timecourse')
    def bortezomib_timecourse():
        if set(request.args)-{'format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        fmt=request.args.get('format','html')
        if fmt not in ('html','json'):abort(400)
        try:report=build_timecourse()
        except ValueError:abort(503,'Model source unavailable or altered; calculation withheld.')
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if fmt=='json':
            headers['Content-Disposition']='attachment; filename="bortezomib-timecourse-candidate.json"'
            return Response(json.dumps(report,indent=2,allow_nan=False),mimetype='application/json',headers=headers)
        return Response(render_template('landscape_bortezomib_timecourse.html',report=report,charts=charts(report)),headers=headers)
