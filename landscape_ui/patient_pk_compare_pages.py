"""Select two scenarios, their states and their compatible archived PK runs."""
import json
import re
from flask import Response, abort, request
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.saved_scenarios import SavedPatientScenario, read_scenario
from intelligence_store.patient_state_revisions import PatientStateRevision, read_revision, revisions_ready
from intelligence_store.educational_pk_runs import EducationalPKRun, runs_ready
from intelligence_store.patient_pk_comparison import compare_patient_pk
from .educational_pk_compare_pages import _run_choices
from .patient_state_pages import LABELS
from .patient_state_compare_pages import CATEGORIES
from .workspace_pages import _response
from .scenario_pages import _error
from .transit_pages import _chart


def register_patient_pk_compare_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/exposure-compare')
    def patient_pk_compare(scenario_id):
        keys = {'right_scenario','left_revision','right_revision','left_run','right_run','format'}
        if set(request.args)-keys or any(len(request.args.getlist(k))!=1 for k in request.args):
            abort(400)
        output = request.args.get('format','html')
        if output not in ('html','json'):
            abort(400)
        ids = {}
        for key in keys-{'format'}:
            raw = request.args.get(key)
            if raw in (None,''):
                ids[key] = None
            elif not re.fullmatch(r'[1-9][0-9]{0,9}',raw):
                abort(400)
            else:
                ids[key] = int(raw)
        ids['right_scenario'] = ids['right_scenario'] or scenario_id
        try:
            scenarios = {'left':read_scenario(scenario_id), 'right':read_scenario(ids['right_scenario'])}
            if any(row is None for row in scenarios.values()):
                abort(404)
            revisions_ready(); runs_ready()
            scenario_choices = list(db.session.execute(select(SavedPatientScenario.id,SavedPatientScenario.title)
                .order_by(SavedPatientScenario.id.desc()).limit(100)).mappings())
            for row in scenarios.values():
                if row.id not in {r['id'] for r in scenario_choices}:
                    scenario_choices.append({'id':row.id,'title':row.title})
            revisions = {}; revision_count = {}; selected = {}; choices = {}; counts = {}
            table = PatientStateRevision
            for side in ('left','right'):
                sid = scenarios[side].id
                revision_count[side] = db.session.scalar(select(func.count()).select_from(table).where(table.scenario_id==sid))
                revisions[side] = list(db.session.scalars(select(table).where(table.scenario_id==sid)
                    .order_by(table.revision_number.desc()).limit(100)))
                rid = ids[side+'_revision']
                if rid is None:
                    candidates = revisions[side]
                    if side=='left' and sid==scenarios['right'].id and len(candidates)>1:
                        rid = candidates[1].id
                    elif side=='right' and sid==scenarios['left'].id:
                        rid = next((r.id for r in candidates if r.id!=ids['left_revision']),None)
                    elif candidates:
                        rid = candidates[0].id
                    ids[side+'_revision'] = rid
                selected[side] = read_revision(rid) if rid else None
                if rid and (selected[side] is None or selected[side].scenario_id!=sid):
                    abort(404)
                if rid and rid not in {r.id for r in revisions[side]}:
                    revisions[side].append(selected[side])
                run_id = ids[side+'_run']
                choices[side], counts[side] = _run_choices(rid,(run_id,) if run_id else ()) if rid else ([],0)
                if run_id:
                    row = db.session.get(EducationalPKRun,run_id)
                    if row is None or row.revision_id!=rid:
                        abort(404)
                elif choices[side]:
                    ids[side+'_run'] = choices[side][0]['id']
            report = chart = None
            if all(ids.values()) and ids['left_revision']!=ids['right_revision']:
                report = compare_patient_pk(scenario_id,ids['left_revision'],ids['right_revision'],ids['left_run'],ids['right_run'],right_scenario_id=ids['right_scenario'])
                points = report['exposure_comparison']['points']
                if points:
                    times = [p['time_h'] for p in points]
                    chart = _chart('Archived central concentration','ng/mL',times,[
                        {'label':f"Left run #{ids['left_run']}",'color':'#007b83','dash':'','values':[p['left_concentration_ng_ml'] for p in points]},
                        {'label':f"Right run #{ids['right_run']}",'color':'#8b5b92','dash':'6 3','values':[p['right_concentration_ng_ml'] for p in points]}])
                    chart['time_ticks'] = [{'x':70+670*i/4,'label':f'{times[-1]*i/4:g}'} for i in range(5)]
            if output=='json':
                if report is None:
                    abort(400,description='Select two different states with a saved run for each.')
                return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',headers={
                    'Content-Disposition':'attachment; filename="patient-state-exposure-comparison.json"',
                    'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            response = _response('landscape_patient_pk_compare.html',scenario=scenarios['left'],scenarios=scenarios,
                scenario_choices=scenario_choices,revisions=revisions,revision_count=revision_count,selected=selected,ids=ids,
                choices=choices,counts=counts,report=report,chart=chart,labels=LABELS,categories=CATEGORIES,
                summary={'cohort':scenarios['left'].payload['analysis']['report']['cohort']})
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        except ValueError as exc:
            return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Patient comparison storage is temporarily unavailable.',503)
