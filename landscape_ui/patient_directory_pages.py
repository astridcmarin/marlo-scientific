"""Bounded directory of saved synthetic scenarios and their latest state/run."""
import re
from flask import abort, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.saved_scenarios import SavedPatientScenario, read_scenario, scenarios_ready
from intelligence_store.patient_state_revisions import PatientStateRevision, read_revision, revisions_ready
from intelligence_store.educational_pk_runs import EducationalPKRun, read_pk_run, runs_ready
from .workspace_pages import _response
from .scenario_pages import _error

PAGE_SIZE = 10


def register_patient_directory_pages(bp):
    @bp.get('/patient-lab/workspace')
    def patient_directory():
        if set(request.args)-{'q','page','cohort_id'} or any(len(request.args.getlist(k))!=1 for k in request.args):
            abort(400)
        q = request.args.get('q','').strip()
        raw_page = request.args.get('page','1')
        cohort = request.args.get('cohort_id')
        if len(q)>120 or not re.fullmatch(r'[1-9][0-9]{0,4}',raw_page):
            abort(400)
        if cohort is not None and not re.fullmatch(r'[1-9][0-9]{0,9}',cohort):
            abort(400)
        page = int(raw_page)
        try:
            scenarios_ready(); revisions_ready(); runs_ready()
            condition = SavedPatientScenario.title.contains(q,autoescape=True)
            count = db.session.scalar(select(func.count()).select_from(SavedPatientScenario).where(condition))
            pages = max(1,(count+PAGE_SIZE-1)//PAGE_SIZE)
            if page>pages:
                abort(404)
            ids = list(db.session.scalars(select(SavedPatientScenario.id).where(condition)
                .order_by(SavedPatientScenario.id.desc()).offset((page-1)*PAGE_SIZE).limit(PAGE_SIZE)))
            entries = []
            for sid in ids:
                # One invalid archive must not hide other valid saved work.
                entry = {'scenario_id':sid,'scenario':None,'revision':None,'run':None,'error':None}
                try:
                    row = read_scenario(sid)
                    if row is None:
                        raise ValueError('Scenario is no longer available.')
                    entry['scenario'] = row
                    entry['reference'] = row.payload['analysis']['report']
                    revision = db.session.scalar(select(PatientStateRevision).where(PatientStateRevision.scenario_id==sid)
                        .order_by(PatientStateRevision.revision_number.desc()).limit(1))
                    if revision:
                        revision = read_revision(revision.id)
                        entry['revision'] = revision
                        fields = revision.payload['state']['fields']
                        entry['known_count'] = sum(f['value'] is not None for f in fields.values())
                        entry['field_count'] = len(fields)
                        entry['run_count'] = db.session.scalar(select(func.count()).select_from(EducationalPKRun)
                            .where(EducationalPKRun.revision_id==revision.id))
                        run = db.session.scalar(select(EducationalPKRun).where(EducationalPKRun.revision_id==revision.id)
                            .order_by(EducationalPKRun.id.desc()).limit(1))
                        if run:
                            entry['run'] = read_pk_run(run.id)
                except ValueError as exc:
                    entry['error'] = str(exc)
                    # Suppress all detail for this entry instead of presenting
                    # an unchecked source chain as a usable patient workspace.
                    entry.update(scenario=None,revision=None,run=None)
                entries.append(entry)
            nav = {'q':q,'cohort_id':cohort}
            return _response('landscape_patient_directory.html',entries=entries,q=q,count=count,
                page=page,pages=pages,cohort_id=cohort,
                previous_url=url_for('landscape.patient_directory',**nav,page=page-1) if page>1 else None,
                next_url=url_for('landscape.patient_directory',**nav,page=page+1) if page<pages else None)
        except ValueError as exc:
            return _error(exc,409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Saved Patient Lab storage is temporarily unavailable.',503)
