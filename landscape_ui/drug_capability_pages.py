"""Read-only searchable model capability inventory, independent of saved cohorts."""
import json
from flask import Response, abort, render_template, request
from intelligence_store.drug_capabilities import capability_inventory


def register_drug_capability_pages(bp):
    @bp.get('/patient-lab/model-library')
    def drug_capability_library():
        if set(request.args)-{'q','capability','format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        q = request.args.get('q','').strip()
        capability = request.args.get('capability','all')
        output = request.args.get('format','html')
        if len(q)>120 or capability not in ('all','exposure','efficacy','toxicity') or output not in ('html','json'):
            abort(400)
        try:
            report = capability_inventory()
        except ValueError:
            return Response('Drug capability inventory unavailable: the identity catalog could not be verified.',
                            status=503, mimetype='text/plain', headers={'Cache-Control':'no-store'})
        rows = [r for r in report['entries'] if not q or
                any(q.casefold() in name.casefold() for name in [r['label']]+r['aliases'])]
        if capability != 'all':
            rows = [r for r in rows if r['capabilities'][capability]['status']=='implemented_educational']
        if output == 'json':
            # Export the complete source-bound inventory; filters are explicitly separate.
            payload = {'inventory':report,'selection':{'query':q,'capability':capability,
                       'entity_ids':[r['entity_id'] for r in rows]}}
            response = Response(json.dumps(payload,indent=2,allow_nan=False)+'\n',mimetype='application/json')
            response.headers['Content-Disposition']='attachment; filename="drug-capability-library.json"'
        else:
            response = Response(render_template('landscape_drug_capabilities.html', report=report, rows=rows,
                                q=q,capability=capability))
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
