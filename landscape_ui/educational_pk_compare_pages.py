"""Compatible archived educational overlays, never a model execution endpoint."""
import json
import re
from flask import Response,abort,request
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.educational_pk_runs import EducationalPKRun
from intelligence_store.educational_pk_comparison import compare_pk_runs,LIMITATION
from intelligence_store.educational_pk_comparison_summary import comparison_summary
from .educational_pk_run_pages import _context
from .workspace_pages import _response
from .scenario_pages import _error
from .transit_pages import _chart


CHOICE_LIMIT = 100


def _run_choices(revision_id, selected_ids=()):
    """Bounded archive metadata list; chosen payloads are audited separately."""
    table = EducationalPKRun
    columns = (table.id, table.title, table.created_at_utc)
    total = db.session.scalar(select(func.count()).select_from(table).where(table.revision_id == revision_id))
    rows = list(db.session.execute(select(*columns).where(table.revision_id == revision_id)
                                  .order_by(table.id.desc()).limit(CHOICE_LIMIT)).mappings())
    visible = {row['id'] for row in rows}
    missing = set(selected_ids) - visible
    if missing:
        rows.extend(db.session.execute(select(*columns).where(table.revision_id == revision_id,
                    table.id.in_(missing)).order_by(table.id.desc())).mappings())
    return rows, total


def register_educational_pk_compare_pages(bp):
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/pk-runs/compare')
    def saved_pk_compare(scenario_id,revision_id):
        if set(request.args)-{'left','right','format'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
        left=request.args.get('left');right=request.args.get('right');output=request.args.get('format','html')
        if output not in ('html','json','summary-json') or (left is None)!=(right is None):abort(400)
        if left is not None and any(not re.fullmatch(r'[1-9][0-9]{0,9}',v) for v in (left,right)):abort(400)
        try:
            scenario,revision=_context(scenario_id,revision_id)
            report=compare_pk_runs(int(left),int(right),revision_id=revision_id) if left is not None else None
            if output=='json':
                if report is None:abort(400)
                return Response(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',
                    headers={'Content-Disposition':f'attachment; filename="educational-pk-comparison-{left}-{right}.json"',
                             'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            summary=comparison_summary(int(left),int(right),revision_id=revision_id) if report else None
            if summary and summary['source_comparison_sha256']!=report['report_sha256']:
                raise ValueError('Archived comparison changed while preparing the audited summary.')
            if output=='summary-json':
                if summary is None:abort(400)
                return Response(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+'\n',mimetype='application/json',
                    headers={'Content-Disposition':f'attachment; filename="educational-pk-comparison-summary-{left}-{right}.json"',
                             'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            labels={'single_declared_covariate_value_changed':'One declared covariate value changed',
                    'multiple_covariate_values_changed':'Multiple declared covariate values changed',
                    'treatment_values_changed_do_not_isolate_covariate_effect':'Treatment values changed; a covariate effect is not isolated',
                    'no_declared_numeric_input_change':'No declared numerical input change'}
            context_label=labels.get(summary['comparison_context']['status']) if summary else None
            chart=None
            if report and report['points'] and summary['status']=='educational_comparison_summary_available':
                points=report['points'];times=[p['time_h'] for p in points]
                chart=_chart('Archived central concentration','ng/mL',times,[
                    {'label':f'Left run #{left}','color':'#007b83','dash':'','values':[p['left_concentration_ng_ml'] for p in points]},
                    {'label':f'Right run #{right}','color':'#8b5b92','dash':'6 3','values':[p['right_concentration_ng_ml'] for p in points]}])
                chart['time_ticks']=[{'x':70+670*i/4,'label':f'{times[-1]*i/4:g}'} for i in range(5)]
            choices,choice_count=_run_choices(revision_id,(int(left),int(right)) if report else ())
            return _response('landscape_saved_pk_compare.html',scenario=scenario,revision=revision,report=report,
                chart=chart,left=left or '',right=right or '',limitation=LIMITATION,
                pk_summary=summary,summary_context_label=context_label,run_choices=choices,run_choice_count=choice_count,choice_limit=CHOICE_LIMIT)
        except ValueError as exc:return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback();return _error('Saved-run comparison storage is temporarily unavailable.',503)
