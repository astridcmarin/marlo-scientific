"""Read-only structural checks; never a clinical or deployment certification."""
import json
import click
from sqlalchemy import inspect, select, func
from sqlalchemy.exc import SQLAlchemyError
from .extensions import db
from .models import AnalysisCohort, CohortTrial, TrialSnapshot
from .summaries import summarize_cohort
from .drug_aliases import load_alias_catalog, reconcile_drug_aliases
from .mechanisms import load_annotation_catalog
from .safety import load_safety_catalog
from .interactions import load_interaction_catalog
from .patient_scenarios import load_scenario_presets
from .trial_criteria import summarize_criteria
from .pharmacokinetics import load_pk_catalog
from .site_feasibility import load_pool_reference
from .regulatory import load_regulatory_reference, summarize_regulatory, digest
from .workspace_models import IntelligenceBrief
from .workspaces import read_brief
from .saved_scenarios import SavedPatientScenario, read_scenario
from .patient_state_revisions import PatientStateRevision, read_revision
from .educational_pk_runs import EducationalPKRun, read_pk_run
from .watchlists import TrialWatchlist, WatchlistTrial, export_watchlist

METHOD = 'platform-structural-validation-v1.1'
LIMITATION = ('Checks local schemas, catalog compatibility, count partitions and saved payload integrity. '
    'A pass does not establish clinical validity, label currency, regulatory compliance, complete scientific coverage, '
    'security readiness or deployment readiness. No network refresh or data repair is performed.')


def check_partition(rows, expected_ids, label):
    """Require unique, disjoint groups whose union exactly equals the denominator."""
    expected = set(expected_ids)
    seen = set()
    for row in rows:
        ids = row['nct_ids']
        if row['count'] != len(ids) or len(ids) != len(set(ids)) or seen.intersection(ids):
            raise ValueError(f'{label}: count, duplicate or overlap inconsistency.')
        seen.update(ids)
    if seen != expected:
        raise ValueError(f'{label}: groups do not partition the expected study IDs.')


def validate_platform(cohort_id):
    if type(cohort_id) is not int or cohort_id < 1:
        raise ValueError('Choose a positive cohort ID.')
    checks = []
    def add(key, label, status, detail):
        checks.append({'key':key, 'label':label, 'status':status, 'detail':detail})
    def run(key, label, fn, dependency=True):
        if not dependency:
            add(key,label,'skipped','Required preceding check failed; this check was not run.')
            return None
        try:
            value, detail = fn()
            add(key,label,'passed',detail)
            return value
        except SQLAlchemyError:
            db.session.rollback()
            add(key,label,'failed','Database operation failed. Check configuration and migrations.')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            add(key,label,'failed',str(exc))
        return None

    tables = set(inspect(db.engine).get_table_names())
    required = {t.name for t in db.metadata.sorted_tables}
    missing = sorted(required - tables)
    add('tables','Required storage tables','failed' if missing else 'passed',
        'Missing: '+', '.join(missing) if missing else f'{len(required)} required model tables are present. Column/migration-head checks are not implied.')
    def alias():
        c=load_alias_catalog()
        return c, f"{c['catalog_version']} | {len(c['entries'])} entities | SHA256 {c['sha256']}"
    aliases=run('aliases','Drug alias catalog',alias)
    adapter = {'catalog_version':aliases['catalog_version'], 'catalog_sha256':aliases['sha256'],
               'catalog_entries':aliases['entries']} if aliases is not None else None
    def catalog(loader):
        c=loader()
        return c, f"{c['catalog_version']} | SHA256 {c['sha256']}"
    for key,label,loader in [
        ('annotations','Mechanism annotation catalog',lambda:load_annotation_catalog(adapter)),
        ('safety','Safety reference catalog',lambda:load_safety_catalog(adapter)),
        ('interactions','Interaction reference catalog',lambda:load_interaction_catalog(adapter))]:
        run(key,label,lambda loader=loader:catalog(loader),adapter is not None)
    presets=run('presets','Synthetic preset catalog',lambda:catalog(lambda:load_scenario_presets(alias_catalog=aliases)),aliases is not None)
    for key,label,loader in [('pk','Historical PK catalog',load_pk_catalog),
        ('pool','Population reference catalog',load_pool_reference),('regulatory_catalog','Regulatory field reference catalog',load_regulatory_reference)]:
        run(key,label,lambda loader=loader:catalog(loader))
    def cohort():
        s=summarize_cohort(cohort_id)
        return s, f"Cohort #{cohort_id}: {s['metrics']['total_trials']['value']} unique retained studies; COMPLETE count/snapshot checks passed."
    summary=run('cohort','Complete cohort and retained snapshots',cohort,
        all(m.__tablename__ in tables for m in (AnalysisCohort,CohortTrial,TrialSnapshot)))
    if summary is not None:
        universe=set(summary['evidence'])
        def counts():
            for key in ('study_type','status'):
                check_partition(summary['groups'][key],universe,key)
            for key,row in summary['metrics'].items():
                ids=row['nct_ids']
                if len(ids)!=len(set(ids)) or not set(ids)<=universe:
                    raise ValueError(f'{key}: duplicate or out-of-cohort evidence.')
                if key in ('total_trials','recruiting_trials','drug_biologic_interventional_trials') and row['value']!=len(ids):
                    raise ValueError(f'{key}: count differs from study IDs.')
            return True,'Study-type/status partitions and trial-count metric ID sets are consistent. Sponsor/country values remain distinct-name counts.'
        run('counts','Summary count consistency',counts)
        def names():
            a=reconcile_drug_aliases(summary,catalog=aliases)
            return a, f"{a['mapped_formatting_group_count']} mapped / {a['formatting_group_count']} formatting groups; {a['unmapped_group_count']} unmapped."
        mapped=run('mapping','Cohort drug-name mapping coverage',names,aliases is not None)
        if mapped is not None and mapped['unmapped_group_count']:
            add('unmapped','Unmapped drug-name groups','warning','Unmapped names remain unassessed. Mapping coverage is not clinical confidence or formulation confirmation.')
        if not universe:
            add('empty','Empty complete cohort','warning','The query retained no studies; consistency checks do not establish useful evidence coverage.')
        def regulatory():
            r=summarize_regulatory(summary)
            check_partition(r['results_groups'].values(),universe,'Results signals')
            for key,g in r['oversight'].items():check_partition(g['groups'].values(),universe,key)
            return True,'Results-signal and each oversight-field partition cover the source cohort independently. No legal compliance inference.'
        run('regulatory_counts','Regulatory partition consistency',regulatory)
        def criteria():
            profile=presets['presets'][0]['profile']
            r=summarize_criteria(summary,profile)
            ids={row['nct_id'] for row in r['records']}
            if r['denominator']!=len(ids) or not ids<=universe:
                raise ValueError('Criteria denominator or source ID inconsistency.')
            for dimension,rows in r['groups'].items():check_partition(rows,ids,dimension)
            return True,f"Preset {presets['presets'][0]['id']}: {len(ids)} selected-name studies; age, sex and combined groups partition that subset. This is one structural example, not all-drug clinical validation."
        run('criteria_counts','Synthetic criteria partition example',criteria,presets is not None and aliases is not None)
    else:
        for key,label in [('counts','Summary count consistency'),('mapping','Cohort drug-name mapping coverage'),
            ('regulatory_counts','Regulatory partition consistency'),('criteria_counts','Synthetic criteria partition example')]:
            run(key,label,lambda:None,False)
    def saved(model, reader):
        ids=list(db.session.scalars(select(model.id).order_by(model.id)))
        for item in ids:reader(item)
        return len(ids),f'{len(ids)} saved items checked; stored payload integrity passed.'
    for key,label,model,reader in [('briefs','Saved brief integrity',IntelligenceBrief,read_brief),
        ('scenarios','Saved synthetic scenario integrity',SavedPatientScenario,read_scenario),
        ('patient_states','Saved patient-state revision integrity',PatientStateRevision,read_revision),
        ('educational_pk_runs','Saved educational PK run integrity',EducationalPKRun,read_pk_run)]:
        run(key,label,lambda model=model,reader=reader:saved(model,reader),model.__tablename__ in tables)
    def watchlists():
        ids=list(db.session.scalars(select(TrialWatchlist.id)))
        for item in ids:export_watchlist(item)
        orphan=db.session.scalar(select(func.count()).select_from(WatchlistTrial).where(~WatchlistTrial.watchlist_id.in_(ids)))
        if orphan:raise ValueError(f'{orphan} watchlist entries have no parent list.')
        return len(ids),f'{len(ids)} lists checked, including copied source integrity and orphan-entry check. Review notes are not source facts.'
    run('watchlists','Watchlist source integrity',watchlists,
        all(m.__tablename__ in tables for m in (TrialWatchlist,WatchlistTrial)))
    totals={s:sum(row['status']==s for row in checks) for s in ('passed','warning','failed','skipped')}
    report={'method_version':METHOD,'cohort_id':cohort_id,'status':'failed' if totals['failed'] else 'passed_with_warnings' if totals['warning'] else 'passed',
        'checks':checks,'totals':totals,'limitation':LIMITATION}
    report['report_sha256']=digest(report)
    return report


def register_validation_commands(app):
    @app.cli.command('platform-check')
    @click.option('--id','cohort_id',type=click.IntRange(1),required=True)
    @click.option('--json','json_output',is_flag=True)
    def platform_check(cohort_id,json_output):
        try:report=validate_platform(cohort_id)
        except (SQLAlchemyError,OSError) as exc:raise click.ClickException('Platform checks could not start. Check database configuration.') from exc
        if json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
        else:
            click.echo(f"Platform checks: {report['status']} | Cohort {cohort_id}")
            for row in report['checks']:click.echo(f"[{row['status'].upper()}] {row['label']}: {row['detail']}")
            click.echo(LIMITATION)
        if report['totals']['failed']:raise click.exceptions.Exit(1)
