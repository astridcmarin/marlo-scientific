"""Integrated read-only Patient Lab workspace for one immutable revision."""
import re

from flask import abort, request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from intelligence_store.extensions import db
from intelligence_store.educational_pk_runs import EducationalPKRun, read_pk_run
from intelligence_store.mechanism_evidence import build_mechanism_map
from .educational_pk_run_pages import _context
from .educational_pk_pages import _charts
from .pk_compartment_timeline import build_compartment_timeline
from .patient_state_pages import LABELS
from .workspace_pages import _response
from .scenario_pages import _error


def register_patient_lab_overview_pages(bp):
    from .protein_turnover_pages import register_protein_turnover_pages
    register_protein_turnover_pages(bp)
    from .patient_directory_pages import register_patient_directory_pages
    register_patient_directory_pages(bp)
    from .patient_pk_compare_pages import register_patient_pk_compare_pages
    register_patient_pk_compare_pages(bp)
    @bp.get('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/patient-lab-overview')
    def patient_lab_overview(scenario_id, revision_id):
        if set(request.args) - {'run_id'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        raw_id = request.args.get('run_id')
        if raw_id is not None and not re.fullmatch(r'[1-9][0-9]{0,9}', raw_id):
            abort(400)
        try:
            scenario, revision = _context(scenario_id, revision_id)
            fields = revision.payload['state']['fields']
            count = db.session.scalar(select(func.count()).select_from(EducationalPKRun)
                .where(EducationalPKRun.revision_id == revision_id))
            rows = list(db.session.scalars(select(EducationalPKRun)
                .where(EducationalPKRun.revision_id == revision_id)
                .order_by(EducationalPKRun.id.desc()).limit(5)))
            for row in rows:
                read_pk_run(row.id)
            run = rows[0] if rows else None
            if raw_id is not None:
                run = db.session.get(EducationalPKRun, int(raw_id))
                if run is None or run.revision_id != revision_id:
                    abort(404)
                run = read_pk_run(run.id)
            report = run.payload['report'] if run else None
            review = report['preflight_review'] if report else None
            frozen = scenario.payload['analysis']['report']
            mechanism = None
            mechanism_error = None
            if frozen['selected_drug']['entity_id'] == 'lenalidomide':
                try:
                    mechanism = build_mechanism_map()
                except (OSError, ValueError):
                    mechanism_error = 'Mechanism evidence is unavailable. Patient state and archived PK remain available.'
            response = _response('landscape_patient_lab_overview.html',
                scenario=scenario, revision=revision, fields=fields, labels=LABELS,
                known=[LABELS[k] for k, v in fields.items() if v['value'] is not None],
                unknown=[LABELS[k] for k, v in fields.items() if v['value'] is None],
                runs=rows, count=count, run=run, report=report, review=review,
                charts=_charts(report), timeline=build_compartment_timeline(report) if report else None,
                frozen=frozen, summary={'cohort': frozen['cohort']},
                mechanism=mechanism, mechanism_error=mechanism_error)
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        except ValueError as exc:
            return _error(exc, 409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Patient Lab workspace storage is temporarily unavailable.', 503)
