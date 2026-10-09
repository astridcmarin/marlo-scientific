"""Two fixed invented binding systems, constant free concentration, no patient link."""
import hashlib
import json
import math
import re
from flask import Response,abort,render_template,request,url_for
from intelligence_store.target_binding_kinetics import calculate_binding_kinetics


def _input(name,default,minimum,maximum,unit):
    raw=request.args.get(name,str(default))
    if len(raw)>40 or not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',raw):
        abort(400,description=f'{name} requires a nonnegative numeric value ({unit}).')
    value=float(raw)
    if not math.isfinite(value) or not minimum<=value<=maximum:
        abort(400,description=f'{name} must be within {minimum:g} to {maximum:g} {unit} for this demonstration.')
    return value


def register_binding_kinetics_pages(bp):
    @bp.get('/patient-lab/binding-kinetics-demo')
    def binding_kinetics_demo():
        if set(request.args)-{'concentration_nm','initial_fraction','horizon_h','time_h','format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        output=request.args.get('format','html')
        if output not in ('html','json'):abort(400)
        concentration=_input('concentration_nm',10,0,1e6,'nM')
        initial=_input('initial_fraction',0,0,1,'dimensionless')
        horizon=_input('horizon_h',24,1e-9,72,'h')
        selected=_input('time_h',min(1,horizon),0,horizon,'h')
        examples=[]
        for label,kon,koff,color,dash in [('Slower relaxation',.01,.1,'#007b83',''),('Faster relaxation',.1,1,'#805693','7 4')]:
            common=dict(free_concentration_nm=concentration,kon_nm_inv_h_inv=kon,koff_h_inv=koff,initial_fraction=initial)
            curve=calculate_binding_kinetics(times_h=[horizon*i/200 for i in range(201)],**common)
            selection=calculate_binding_kinetics(times_h=[0,selected] if selected else [0],**common)
            examples.append({'label':label,'curve_report':curve,'selection_report':selection})
        report={'schema_version':'invented-binding-kinetics-page-v1','purpose':'synthetic_educational',
            'examples':examples,'display':{'horizon_h':horizon,'selected_time_h':selected,'curve_points':201,'horizontal_scale':'linear'},
            'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
            'scope':'Invented fixed-rate systems under constant free concentration; no drug, patient or PK archive association.'}
        report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()).hexdigest()
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if output=='json':
            headers['Content-Disposition']='attachment; filename="invented-binding-kinetics-demo.json"'
            return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers=headers)
        series=[]
        for example,color,dash in zip(examples,['#007b83','#805693'],['','7 4']):
            points=example['curve_report']['points'];fraction=example['selection_report']['points'][-1]['fraction_bound']
            series.append({'label':example['label'],'color':color,'dash':dash,
                'polyline':' '.join(f"{70+670*p['time_h']/horizon:.3f},{250-220*p['fraction_bound']:.3f}" for p in points),
                'selected_y':250-220*fraction,'selected_fraction':fraction})
        chart={'series':series,'selected_x':70+670*selected/horizon,
            'x_ticks':[{'x':70+670*i/4,'label':f'{horizon*i/4:.4g}'} for i in range(5)],
            'y_ticks':[{'y':250-220*i/4,'label':f'{i/4:g}'} for i in range(5)]}
        export_url=url_for('landscape.binding_kinetics_demo',concentration_nm=f'{concentration:.17g}',
            initial_fraction=f'{initial:.17g}',horizon_h=f'{horizon:.17g}',time_h=f'{selected:.17g}',format='json')
        return Response(render_template('landscape_binding_kinetics_demo.html',report=report,chart=chart,
            concentration=concentration,initial=initial,horizon=horizon,selected=selected,export_url=export_url),headers=headers)
