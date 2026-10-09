"""Qualitative mechanism evidence within the existing Patient Lab."""
import json
from flask import Response,abort,render_template,request,url_for
from intelligence_store.mechanism_evidence import build_mechanism_map


def register_mechanism_map_pages(bp):
    @bp.get('/patient-lab/lenalidomide-mechanism')
    def mechanism_map_demo():
        if set(request.args)-{'format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        try:report=build_mechanism_map()
        except (OSError,ValueError):
            abort(503,description='Mechanism evidence packet is missing or incompatible. Restore the Step 84 packet and review its integrity before continuing.')
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="lenalidomide-qualitative-mechanism.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        return Response(render_template('landscape_mechanism_map_demo.html',report=report,
            export_url=url_for('landscape.mechanism_map_demo',format='json')),headers=headers)
