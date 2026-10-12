"""Continuous versus pulse site exposure, without patient or storage access."""
import json
import math
import re
from flask import Response, abort, render_template, request, url_for
from intelligence_store.site_exposure_response import calculate_site_response
from intelligence_store.target_binding_kinetics import _hash

PARAMS={'initial_concentration_nm':(10,0,100),'profile_time_h':(2,.1,23.9),
    'loss_rate_h_inv':(.2,.001,1),'hypothetical_gain':(4,0,10),'time_h':(4,0,24)}


def register_site_exposure_pages(bp):
    @bp.get('/patient-lab/site-exposure-experiment')
    def site_exposure_experiment():
        if set(request.args)-(set(PARAMS)|{'profile','format'}) or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        profile=request.args.get('profile','decay');output=request.args.get('format','html')
        if profile not in ('decay','pulse') or output not in ('html','json'):abort(400)
        controls={'profile':profile}
        for key,(default,low,high) in PARAMS.items():
            raw=request.args.get(key,str(default))
            if len(raw)>40 or not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',raw):abort(400)
            value=float(raw)
            if not math.isfinite(value) or not low<=value<=high:abort(400)
            controls[key]=value
        selected=controls['time_h']
        times=sorted(set([i*.12 for i in range(201)]+[selected,controls['profile_time_h']]))
        report=calculate_site_response(**{k:v for k,v in controls.items() if k!='time_h'},times_h=times)
        inspection={name:next(p for p in example['points'] if p['time_h']==selected) for name,example in report['examples'].items()}
        report.pop('report_sha256');report['inspection']={'time_h':selected,'points':inspection};report['report_sha256']=_hash(report)
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="hypothetical-site-exposure-response.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        series=[]
        for (name,example),color,dash in zip(report['examples'].items(),['#007b83','#805693'],['','7 4']):
            series.append({'label':name.replace('_',' ').title(),'color':color,'dash':dash,
                **{key:' '.join(f"{70+670*p['time_h']/24:.3f},{250-220*p[key]:.3f}" for p in example['points'])
                    for key in ('fraction_bound','relative_amount')}})
        first=next(iter(report['examples'].values()))['points']
        maximum=controls['initial_concentration_nm'] or 1
        exposure_line=' '.join(f"{70+670*p['time_h']/24:.3f},{250-220*p['free_concentration_nm']/maximum:.3f}" for p in first)
        # Draw the left limit at a pulse switch instead of a diagonal to the next sample.
        if profile=='pulse':exposure_line=f"70,30 {70+670*controls['profile_time_h']/24:.3f},30 {70+670*controls['profile_time_h']/24:.3f},250 740,250" if controls['initial_concentration_nm'] else '70,250 740,250'
        return Response(render_template('landscape_site_exposure_experiment.html',report=report,controls=controls,
            series=series,exposure_line=exposure_line,maximum=maximum,selected_x=70+670*selected/24,
            export_url=url_for('landscape.site_exposure_experiment',**controls,format='json')),headers=headers)
