"""Independent hypothetical binding-to-turnover browser experiment."""
import json
import math
import re
from flask import Response, abort, render_template, request, url_for
from intelligence_store.binding_turnover import calculate_binding_turnover

CONTROLS={'free_concentration_nm':(10,0,100),'pulse_duration_h':(4,.1,23.9),
    'loss_rate_h_inv':(.2,.001,1),'hypothetical_gain':(4,0,10),'time_h':(4,0,24)}


def register_binding_turnover_pages(bp):
    @bp.get('/patient-lab/binding-turnover-experiment')
    def binding_turnover_experiment():
        if set(request.args)-(set(CONTROLS)|{'format'}) or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        controls={}
        for name,(default,low,high) in CONTROLS.items():
            raw=request.args.get(name,str(default))
            if len(raw)>40 or not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',raw):abort(400)
            value=float(raw)
            if not math.isfinite(value) or not low<=value<=high:abort(400)
            controls[name]=value
        selected=controls['time_h']
        times=sorted(set([i*.12 for i in range(201)]+[selected,controls['pulse_duration_h']]))
        report=calculate_binding_turnover(**{k:v for k,v in controls.items() if k!='time_h'},times_h=times)
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="hypothetical-binding-turnover.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        series=[]
        for (name,example),color,dash in zip(report['examples'].items(),['#007b83','#805693'],['','7 4']):
            point=next(p for p in example['points'] if p['time_h']==selected)
            series.append({'label':name.replace('_',' ').title(),'color':color,'dash':dash,'selected':point,
                'binding_line':' '.join(f"{70+670*p['time_h']/24:.3f},{250-220*p['fraction_bound']:.3f}" for p in example['points']),
                'amount_line':' '.join(f"{70+670*p['time_h']/24:.3f},{250-220*p['relative_amount']:.3f}" for p in example['points'])})
        return Response(render_template('landscape_binding_turnover_experiment.html',report=report,controls=controls,
            series=series,selected_x=70+670*selected/24,switch_x=70+670*controls['pulse_duration_h']/24,
            export_url=url_for('landscape.binding_turnover_experiment',**controls,format='json')),headers=headers)
