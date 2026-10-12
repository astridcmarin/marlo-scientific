"""Adjustable hypothetical production/loss comparison, independent of storage."""
import json
import math
import re
from flask import Response, abort, render_template, request, url_for
from intelligence_store.protein_turnover_experiments import compare_turnover_mechanisms

PARAMETERS = {'loss_rate_h_inv':(.2,.001,10), 'strength':(4,1,20),
    'pulse_duration_h':(4,.1,23.9), 'time_h':(4,0,24)}


def register_turnover_experiment_pages(bp):
    @bp.get('/patient-lab/turnover-experiment')
    def turnover_experiment():
        if set(request.args)-(set(PARAMETERS)|{'format'}) or any(len(request.args.getlist(k))!=1 for k in request.args):
            abort(400,description='Only explicit hypothetical turnover controls are accepted; no patient or PK links.')
        output = request.args.get('format','html')
        if output not in ('html','json'): abort(400)
        controls = {}
        for name,(default,low,high) in PARAMETERS.items():
            raw = request.args.get(name,str(default))
            if len(raw)>40 or not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',raw):
                abort(400,description=f'{name} must be a number between {low} and {high}.')
            value = float(raw)
            if not math.isfinite(value) or not low<=value<=high:
                abort(400,description=f'{name} must be between {low} and {high}.')
            controls[name] = value
        selected = controls['time_h'];duration = controls['pulse_duration_h']
        times = sorted(set([i*.12 for i in range(201)]+[duration,selected]))
        report = compare_turnover_mechanisms(loss_rate_h_inv=controls['loss_rate_h_inv'],
            strength=controls['strength'],pulse_duration_h=duration,times_h=times)
        series = []
        for (name,example),color,dash in zip(report['examples'].items(),['#007b83','#805693'],['','7 4']):
            point = next(p for p in example['points'] if p['time_h']==selected)
            series.append({'label':name.replace('_',' ').title(), 'color':color,'dash':dash,
                'polyline':' '.join(f"{70+670*p['time_h']/24:.3f},{250-220*p['relative_amount']:.3f}" for p in example['points']),
                'selected_amount':point['relative_amount'],'selected_y':250-220*point['relative_amount'],
                'pulse_production':example['inputs']['phases'][0]['production_multiplier'],
                'pulse_loss':example['inputs']['phases'][0]['loss_multiplier']})
        headers = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="hypothetical-turnover-experiment.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        return Response(render_template('landscape_turnover_experiment.html',report=report,
            controls=controls,series=series,selected_x=70+670*selected/24,switch_x=70+670*duration/24,
            export_url=url_for('landscape.turnover_experiment',**controls,format='json')),headers=headers)
