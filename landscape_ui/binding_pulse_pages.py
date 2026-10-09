"""Fixed invented pulse visualization; no application storage or patient PK calls."""
import hashlib
import json
import math
import re
from flask import Response, abort, render_template, request, url_for
from intelligence_store.target_binding_schedule import calculate_binding_schedule


def register_binding_pulse_pages(bp):
    @bp.get('/patient-lab/binding-pulse-demo')
    def binding_pulse_demo():
        if set(request.args)-{'time_h','format'} or any(len(request.args.getlist(k))!=1 for k in request.args):
            abort(400,description='Only one time_h and format value are accepted. No patient or PK links are accepted.')
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400,description='Format must be html or json.')
        raw=request.args.get('time_h','4')
        if len(raw)>40 or not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',raw):
            abort(400,description='Selected time requires a nonnegative number in hours.')
        selected=float(raw)
        if not math.isfinite(selected) or not 0<=selected<=24:
            abort(400,description='Selected time must be between 0 and 24 h.')
        phases=[{'start_time_h':0,'free_concentration_nm':10},{'start_time_h':4,'free_concentration_nm':0}]
        # Include the exact switch, independently of regular display samples.
        times=sorted(set([24*i/200 for i in range(201)]+[4.0]))
        examples=[]
        for label,kon,koff in [('Slower binding system',.01,.1),('Faster binding system',.1,1)]:
            common=dict(phases=phases,kon_nm_inv_h_inv=kon,koff_h_inv=koff,initial_fraction=0)
            curve=calculate_binding_schedule(times_h=times,**common)
            selection=calculate_binding_schedule(times_h=sorted(set([0.0,selected,24.0])),**common)
            point=next(p for p in selection['points'] if p['time_h']==selected)
            examples.append({'label':label,'curve_report':curve,'selection_report':selection,'selected_point':point})
        report={'schema_version':'invented-binding-pulse-page-v1','purpose':'synthetic_educational',
            'examples':examples,'display':{'selected_time_h':selected,'horizon_h':24,'switch_time_h':4,
            'curve_points':len(times),'sample_concentration_convention':'new phase at switch'},
            'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
            'scope':'Fixed invented free-site concentration pulse. No drug, target, patient or PK archive association.'}
        report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="invented-binding-pulse-demo.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        series=[]
        for example,color,dash in zip(examples,['#007b83','#805693'],['','7 4']):
            series.append({'label':example['label'],'color':color,'dash':dash,
                'polyline':' '.join(f"{70+670*p['time_h']/24:.3f},{250-220*p['fraction_bound']:.3f}" for p in example['curve_report']['points']),
                'selected_y':250-220*example['selected_point']['fraction_bound'],
                'selected_fraction':example['selected_point']['fraction_bound']})
        chart={'series':series,'selected_x':70+670*selected/24,'switch_x':70+670*4/24,
            'concentration_y':250-220*(10 if selected<4 else 0)/10,
            'x_ticks':[{'x':70+670*i/4,'label':i*6} for i in range(5)],
            'binding_ticks':[{'y':250-220*i/4,'label':i/4} for i in range(5)],
            'concentration_ticks':[{'y':250-220*i/2,'label':i*5} for i in range(3)]}
        export_url=url_for('landscape.binding_pulse_demo',time_h=f'{selected:.17g}',format='json')
        return Response(render_template('landscape_binding_pulse_demo.html',report=report,chart=chart,
            selected=selected,export_url=export_url),headers=headers)
