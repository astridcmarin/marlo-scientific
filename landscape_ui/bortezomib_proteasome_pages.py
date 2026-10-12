"""Read-only published equation explorer; independent of patient/PK archives."""
import json
import math
from flask import Response, abort, render_template, request, url_for
from intelligence_store.bortezomib_proteasome import calculate_proteasome_activity


def register_bortezomib_proteasome_pages(bp):
    @bp.get('/simulation-lab/bortezomib-proteasome')
    def bortezomib_proteasome_demo():
        if set(request.args)-{'concentration_nm','format'} or any(len(request.args.getlist(k))!=1 for k in request.args):
            abort(400)
        output = request.args.get('format','html')
        if output not in ('html','json'):
            abort(400)
        raw = request.args.get('concentration_nm','1.79')
        if len(raw)>40:
            abort(400)
        try:
            selected = float(raw)
            if not math.isfinite(selected) or not 0<=selected<=100:
                raise ValueError()
        except ValueError:
            abort(400,'Use a concentration within the 0–100 nM teaching display window.')
        grid = sorted(set([i/4 for i in range(401)]+[1.79,selected]))
        try:
            report = calculate_proteasome_activity(plasma_concentrations_nm=grid)
        except ValueError:
            abort(503,'Published reference unavailable or altered; calculation blocked.')
        headers = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output == 'json':
            headers['Content-Disposition']='attachment; filename="bortezomib-proteasome-equation.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',
                            mimetype='application/json',headers=headers)
        point = next(p for p in report['points'] if p['plasma_concentration_nm']==selected)
        polyline = ' '.join(f"{65+6.6*p['plasma_concentration_nm']:.3f},{260-2.2*p['activity_percent_of_baseline']:.3f}" for p in report['points'])
        return Response(render_template('landscape_bortezomib_proteasome.html',report=report,
            selected=selected,point=point,polyline=polyline,
            export_url=url_for('landscape.bortezomib_proteasome_demo',concentration_nm=selected,format='json')),
            headers=headers)
