"""Independent fixed teaching example; no patient or PK archive access."""
import json
import math
import re
from flask import Response, abort, render_template, request, url_for
from intelligence_store.protein_turnover import turnover_example


def register_protein_turnover_pages(bp):
    from .bortezomib_assumption_pages import register_bortezomib_assumption_pages
    register_bortezomib_assumption_pages(bp)
    from .bortezomib_timecourse_pages import register_bortezomib_timecourse_pages
    register_bortezomib_timecourse_pages(bp)
    from .bortezomib_figure_pages import register_bortezomib_figure_pages
    register_bortezomib_figure_pages(bp)
    from .bortezomib_evidence_pages import register_bortezomib_evidence_pages
    register_bortezomib_evidence_pages(bp)
    from .bortezomib_proteasome_pages import register_bortezomib_proteasome_pages
    register_bortezomib_proteasome_pages(bp)
    from .disease_library_pages import register_disease_library_pages
    register_disease_library_pages(bp)
    from .drug_capability_pages import register_drug_capability_pages
    register_drug_capability_pages(bp)
    from .renal_pk_evidence_pages import register_renal_pk_evidence_pages
    register_renal_pk_evidence_pages(bp)
    from .simulation_lab_pages import register_simulation_lab_pages
    register_simulation_lab_pages(bp)
    from .site_exposure_response_pages import register_site_exposure_pages
    register_site_exposure_pages(bp)
    from .binding_turnover_pages import register_binding_turnover_pages
    register_binding_turnover_pages(bp)
    from .protein_turnover_experiment_pages import register_turnover_experiment_pages
    register_turnover_experiment_pages(bp)
    @bp.get('/patient-lab/protein-turnover-demo')
    def protein_turnover_demo():
        if set(request.args)-{'time_h','format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        output = request.args.get('format','html')
        if output not in ('html','json'): abort(400)
        raw = request.args.get('time_h','4')
        if len(raw)>40 or not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',raw): abort(400)
        selected = float(raw)
        if not math.isfinite(selected) or not 0 <= selected <= 24: abort(400)
        times = sorted(set([i*.12 for i in range(201)]+[4.,selected]))
        examples = turnover_example(times)
        series = []
        for (name,report),color,dash in zip(examples.items(),['#007b83','#805693'],['','7 4']):
            point = next(p for p in report['points'] if p['time_h']==selected)
            series.append({'label':name.replace('_',' ').title(), 'color':color,'dash':dash,
                'polyline':' '.join(f"{70+670*p['time_h']/24:.3f},{250-220*p['relative_amount']:.3f}" for p in report['points']),
                'selected_amount':point['relative_amount'], 'selected_y':250-220*point['relative_amount']})
        headers = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output == 'json':
            headers['Content-Disposition']='attachment; filename="invented-protein-turnover.json"'
            return Response(json.dumps(examples,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        return Response(render_template('landscape_protein_turnover_demo.html',examples=examples,
            series=series,selected=selected,selected_x=70+670*selected/24,
            export_url=url_for('landscape.protein_turnover_demo',time_h=f'{selected:.17g}',format='json')),headers=headers)
