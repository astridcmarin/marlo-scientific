"""Phase 4.1a: export a saved cohort's eligibility criteria as one compact, checksummed file.

Protocol benchmarking compares eligibility criteria across similar trials. The criteria are free text inside each
retained ClinicalTrials.gov snapshot. The full local database is too large to move around, so this command writes
only what benchmarking needs, from the cohort's frozen snapshots (never from current registry rows):

    PYTHONPATH=. flask --app app/app.py eligibility-corpus-export --list
    PYTHONPATH=. flask --app app/app.py eligibility-corpus-export --cohort-id 3 --output Articles/eligibility_corpus_cohort3.json

The file records the cohort's query, the snapshot behind every trial, and a checksum of its own content. Nothing is
parsed or interpreted here; extraction of thresholds is a later, separately validated step.
"""
import json
from pathlib import Path

import click
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import AnalysisCohort, CohortTrial, TrialSnapshot
from .normalization import _mapping, _text
from .patient_state import digest

SCHEMA_VERSION = 'eligibility-corpus-v1'
METHOD_VERSION = 'eligibility-corpus-export-v1.0'


def _list(value):
    return value if isinstance(value, list) else []


def trial_record(nct_id, snapshot):
    """Fields benchmarking needs, copied from one retained snapshot without interpretation."""
    protocol = _mapping(_mapping(snapshot.raw_study).get('protocolSection'))
    ident = _mapping(protocol.get('identificationModule'))
    status = _mapping(protocol.get('statusModule'))
    design = _mapping(protocol.get('designModule'))
    sponsor = _mapping(_mapping(protocol.get('sponsorCollaboratorsModule')).get('leadSponsor'))
    eligibility = _mapping(protocol.get('eligibilityModule'))
    arms = _mapping(protocol.get('armsInterventionsModule'))
    enrollment = _mapping(design.get('enrollmentInfo'))
    return {
        'nct_id': nct_id,
        'snapshot_id': snapshot.id,
        'retrieved_at_utc': snapshot.retrieved_at_utc.isoformat() if snapshot.retrieved_at_utc else None,
        'source_last_update_date': snapshot.source_last_update_date,
        'brief_title': _text(ident.get('briefTitle')),
        'overall_status': _text(status.get('overallStatus')),
        'start_date': _text(_mapping(status.get('startDateStruct')).get('date')),
        'study_type': _text(design.get('studyType')),
        'phases': [p for p in _list(design.get('phases')) if isinstance(p, str)],
        'conditions': [c for c in _list(_mapping(protocol.get('conditionsModule')).get('conditions')) if isinstance(c, str)],
        'interventions': [{'type': _text(_mapping(i).get('type')), 'name': _text(_mapping(i).get('name'))}
                          for i in _list(arms.get('interventions'))],
        'lead_sponsor': {'name': _text(sponsor.get('name')), 'class': _text(sponsor.get('class'))},
        'enrollment': {'count': enrollment.get('count') if isinstance(enrollment.get('count'), int) else None,
                       'type': _text(enrollment.get('type'))},
        'eligibility': {
            'criteria_text': eligibility.get('eligibilityCriteria') if isinstance(eligibility.get('eligibilityCriteria'), str) else None,
            'minimum_age': _text(eligibility.get('minimumAge')),
            'maximum_age': _text(eligibility.get('maximumAge')),
            'sex': _text(eligibility.get('sex')),
            'healthy_volunteers': eligibility.get('healthyVolunteers') if isinstance(eligibility.get('healthyVolunteers'), bool) else None,
        },
    }


def export_corpus(cohort_id):
    cohort = db.session.get(AnalysisCohort, cohort_id)
    if cohort is None:
        raise ValueError('No cohort has that ID.')
    if cohort.status != 'COMPLETE':
        raise ValueError(f'Cohort {cohort_id} is {cohort.status}; only complete cohorts are exported.')
    rows = db.session.execute(
        select(CohortTrial, TrialSnapshot).outerjoin(TrialSnapshot, CohortTrial.snapshot_id == TrialSnapshot.id)
        .where(CohortTrial.cohort_id == cohort_id).order_by(CohortTrial.nct_id)).all()
    if len(rows) != cohort.retrieved_count:
        raise ValueError('Saved membership and retrieved count disagree; nothing exported.')
    trials = []
    for member, snapshot in rows:
        if snapshot is None or snapshot.nct_id != member.nct_id:
            raise ValueError(f'{member.nct_id}: retained snapshot missing or mismatched; nothing exported.')
        trials.append(trial_record(member.nct_id, snapshot))
    with_text = sum(1 for t in trials if t['eligibility']['criteria_text'])
    corpus = {
        'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION,
        'cohort': {'id': cohort.id, 'condition': cohort.condition, 'scope': cohort.scope, 'query_params': cohort.query_params,
                   'query_version': cohort.query_version, 'expected_count': cohort.expected_count,
                   'retrieved_count': cohort.retrieved_count,
                   'finished_at_utc': cohort.finished_at_utc.isoformat() if cohort.finished_at_utc else None},
        'counts': {'trials': len(trials), 'with_eligibility_text': with_text,
                   'interventional': sum(1 for t in trials if t['study_type'] == 'INTERVENTIONAL')},
        'source': 'ClinicalTrials.gov study records as retained in the cohort snapshots; registry data are public.',
        'not_this': ['Not parsed or interpreted: criteria text is copied as registered.',
                     'Not current: each record is the snapshot frozen when the cohort was saved.'],
        'trials': trials,
    }
    corpus['corpus_sha256'] = digest(corpus)
    return corpus


def register_eligibility_corpus_commands(app):
    @app.cli.command('eligibility-corpus-export')
    @click.option('--list', 'list_only', is_flag=True, help='List saved cohorts and exit.')
    @click.option('--cohort-id', type=click.IntRange(1))
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(list_only, cohort_id, output):
        """Export a saved cohort's eligibility criteria for protocol benchmarking (Phase 4.1a)."""
        try:
            if list_only:
                for c in db.session.scalars(select(AnalysisCohort).order_by(AnalysisCohort.id)):
                    click.echo(f'{c.id}\t{c.status}\t{c.retrieved_count} trials\t{c.condition}\t{c.scope}\t{c.finished_at_utc}')
                return
            if cohort_id is None or output is None:
                raise click.UsageError('Give --list, or both --cohort-id and --output.')
            corpus = export_corpus(cohort_id)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise click.ClickException('Database unavailable. Check configuration and migrations.') from exc
        with output.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(corpus, ensure_ascii=False, allow_nan=False) + '\n')
        click.echo(f"Exported {corpus['counts']['trials']} trials ({corpus['counts']['with_eligibility_text']} with criteria text) "
                   f"to {output}\nCorpus SHA256: {corpus['corpus_sha256']}")
