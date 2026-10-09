"""Read-only generic binding demo. No patient, PK archive or database input."""
import hashlib
import json
import math
import re
from flask import Response, abort, render_template, request, url_for
from intelligence_store.target_occupancy import calculate_target_occupancy


def _input(name,default,minimum,maximum):
    raw=request.args.get(name,str(default))
    if len(raw)>40 or not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',raw):
        abort(400,description=f'{name} requires a nonnegative numeric value in nM.')
    value=float(raw)
    if not math.isfinite(value) or not minimum<=value<=maximum:
        abort(400,description=f'{name} is outside the supported demonstration bounds.')
    return value


def register_target_occupancy_pages(bp):
    @bp.get('/patient-lab/target-occupancy-demo')
    def target_occupancy_demo():
        if set(request.args)-{'kd_nm','max_nm','selected_nm','format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        kd=_input('kd_nm',10,1e-12,1e12)
        maximum=_input('max_nm',100,1e-12,1e12)
        selected=_input('selected_nm',min(10,maximum),0,maximum)
        curve=calculate_target_occupancy(kd_nm=kd,free_concentrations_nm=[maximum*i/200 for i in range(201)])
        selection=calculate_target_occupancy(kd_nm=kd,free_concentrations_nm=[selected])
        report={'schema_version':'generic-target-occupancy-page-v1','curve_report':curve,'selection_report':selection,
            'display':{'max_free_concentration_nm':maximum,'curve_points':201,'horizontal_scale':'linear','vertical_scale':'fraction_0_to_1'}}
        report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,
            separators=(',', ':'),allow_nan=False).encode()).hexdigest()
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="generic-target-occupancy-demo.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        chart={'polyline':' '.join(f"{70+670*p['free_concentration_nm']/maximum:.3f},{250-220*p['fraction_bound']:.3f}" for p in curve['points']),
            'x_ticks':[{'x':70+670*i/4,'label':f'{maximum*i/4:.4g}'} for i in range(5)],
            'y_ticks':[{'y':250-220*i/4,'label':f'{i/4:g}'} for i in range(5)],
            'selected_x':70+670*selected/maximum,'selected_y':250-220*selection['points'][0]['fraction_bound']}
        export_url=url_for('landscape.target_occupancy_demo',kd_nm=f'{kd:.17g}',max_nm=f'{maximum:.17g}',selected_nm=f'{selected:.17g}',format='json')
        return Response(render_template('landscape_target_occupancy_demo.html',report=report,chart=chart,
            kd=kd,maximum=maximum,selected=selected,fraction=selection['points'][0]['fraction_bound'],export_url=export_url),headers=headers)
