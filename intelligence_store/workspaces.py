"""Save complete-cohort outputs once; read/export without recomputing."""
import copy
from datetime import datetime, timezone
import json
import re
import click
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError
from .extensions import db
from .models import TrialSnapshot
from .workspace_models import IntelligenceBrief
from .summaries import summarize_cohort, CohortSummaryError
from .normalization import _mapping, _text
from .regulatory import summarize_regulatory, digest
from .protocols import summarize_protocols
from .stopping import summarize_stopping
from .safety import summarize_safety
from .interactions import summarize_interactions
from .site_feasibility import summarize_locations

SCHEMA_VERSION = 'saved-intelligence-brief-v1.0'
SECTIONS = {'landscape': 'Landscape', 'protocols': 'Protocol structure',
    'stopping': 'Stopped-study evidence', 'safety': 'Safety references',
    'interactions': 'Interaction references', 'sites': 'Site evidence',
    'regulatory': 'Regulatory evidence'}
METRIC_LABELS = {'total_trials': 'Unique saved studies', 'recruiting_trials': 'Overall RECRUITING studies',
    'lead_sponsor_names': 'Unique raw lead sponsor names', 'industry_lead_sponsor_names': 'Unique raw industry lead sponsor names',
    'drug_biologic_interventional_trials': 'Drug / biologic interventional studies', 'listed_countries': 'Countries with listed locations'}
LIMITATION = ('Descriptive registry intelligence from frozen query cohorts. Query scope and retrieval dates remain separate; '
    'a two-cohort comparison is not a longitudinal, causal or statistical comparison. Cohorts can overlap and their counts '
    'must not be summed as unique studies. Analyst notes are user-authored interpretations, not verified source facts. '
    'No patient scenario or patient-pool assumptions are saved automatically.')


def validate_inputs(title, notes, cohort_ids, sections, pinned):
    if not isinstance(title,str) or not 1 <= len(title.strip()) <= 160:
        raise ValueError('Enter a brief title between 1 and 160 characters.')
    if not isinstance(notes,str) or len(notes)>8000:
        raise ValueError('Analyst notes must be at most 8,000 characters.')
    if any(ord(c)<32 and c not in '\n\r\t' for c in title+notes):
        raise ValueError('Unsupported control character in title or notes.')
    if not isinstance(cohort_ids,list) or not 1<=len(cohort_ids)<=2 or any(type(c) is not int or c<1 for c in cohort_ids) or len(set(cohort_ids))!=len(cohort_ids):
        raise ValueError('Choose one or two distinct complete cohorts.')
    if not isinstance(sections,list) or any(s not in SECTIONS for s in sections) or len(set(sections))!=len(sections) or 'landscape' not in sections:
        raise ValueError('Choose valid sections including Landscape.')
    if not isinstance(pinned,str):raise ValueError('Enter NCT IDs as text.')
    ids=[s.upper() for s in re.split(r'[\s,;]+',pinned.strip()) if s]
    if any(not re.fullmatch(r'NCT\d{8}',s) for s in ids) or len(set(ids))>20:
        raise ValueError('Pin at most 20 valid NCT IDs, separated by spaces, commas or new lines.')
    return {'title':title.strip(),'notes':notes,'cohort_ids':cohort_ids,
        'sections':[s for s in SECTIONS if s in sections],'pinned_nct_ids':sorted(set(ids))}


def workspace_ready():
    if not inspect(db.engine).has_table(IntelligenceBrief.__tablename__):
        raise ValueError('Workspace table is missing. Generate and apply the Step 19 migration in START_HERE.md.')


def _compact(section, report):
    result=copy.deepcopy(report)
    for key in {'protocols':['profiles'],'stopping':['records'], 'sites':['rows','trials'], 'regulatory':['records']}.get(section,[]):result.pop(key,None)
    if section=='stopping':result['outside_status_with_reason'].pop('records',None)
    return result


def build_brief(inputs, saved_at=None):
    # Revalidate independently of the web form or CLI.
    inputs=validate_inputs(inputs['title'],inputs['notes'],inputs['cohort_ids'],inputs['sections'], ' '.join(inputs['pinned_nct_ids']))
    summaries=[summarize_cohort(c) for c in inputs['cohort_ids']]
    all_ids=set().union(*(set(s['evidence']) for s in summaries))
    if set(inputs['pinned_nct_ids'])-all_ids:
        raise ValueError('Every pinned NCT ID must belong to at least one selected cohort.')
    cohorts=[]
    for summary in summaries:
        refs=summary['evidence']
        snapshots={s.id:s for s in db.session.scalars(select(TrialSnapshot).where(TrialSnapshot.id.in_([r['snapshot_id'] for r in refs.values()])))} if refs else {}
        # Keep a hash of every underlying JSON object, not just its ID.
        for nct,ref in refs.items():
            snap=snapshots.get(ref['snapshot_id'])
            if snap is None or snap.nct_id!=nct:raise CohortSummaryError('Missing retained brief evidence.')
            ref['raw_study_sha256']=digest(snap.raw_study)
        reports={}
        for section in inputs['sections']:
            if section=='landscape':continue
            report={'protocols':lambda:summarize_protocols(summary['cohort']['id']),
                'stopping':lambda:summarize_stopping(summary['cohort']['id'],status='ALL'),
                'safety':lambda:summarize_safety(summary),'interactions':lambda:summarize_interactions(summary),
                'sites':lambda:summarize_locations(summary),'regulatory':lambda:summarize_regulatory(summary)}[section]()
            reports[section]=_compact(section,report)
        pinned=[]
        for nct in inputs['pinned_nct_ids']:
            if nct not in refs:continue
            raw=copy.deepcopy(snapshots[refs[nct]['snapshot_id']].raw_study)
            p=_mapping(_mapping(raw).get('protocolSection'))
            pinned.append({'nct_id':nct,'title':_text(_mapping(p.get('identificationModule')).get('briefTitle')),
                'status':_text(_mapping(p.get('statusModule')).get('overallStatus')),
                'sponsor':_text(_mapping(_mapping(p.get('sponsorCollaboratorsModule')).get('leadSponsor')).get('name')),
                'evidence':copy.deepcopy(refs[nct]),'raw_study':raw})
        cohorts.append({'summary':summary,'reports':reports,'pinned_trials':pinned,
            'source_manifest_sha256':digest(refs)})
    payload={'schema_version':SCHEMA_VERSION,**inputs,
        'saved_at_utc':saved_at or datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        'cohorts':cohorts,'limitation':LIMITATION}
    if len(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode())>32*1024*1024:
        raise ValueError('Brief exceeds 32 MiB. Choose fewer sections or pinned trials.')
    return payload


def read_brief(brief_id):
    workspace_ready()
    row=db.session.get(IntelligenceBrief,brief_id)
    if row is None:return None
    if not isinstance(row.payload,dict) or row.schema_version!=SCHEMA_VERSION or row.payload.get('schema_version')!=SCHEMA_VERSION or row.title!=row.payload.get('title') or digest(row.payload)!=row.payload_sha256:
        raise ValueError('Saved brief format or integrity check failed. Its exports are unavailable.')
    return row


def save_brief(inputs,save_key):
    workspace_ready()
    if not isinstance(save_key,str) or not re.fullmatch(r'[a-f0-9]{64}',save_key):raise ValueError('Invalid submission key.')
    inputs=validate_inputs(inputs['title'],inputs['notes'],inputs['cohort_ids'],inputs['sections'],' '.join(inputs['pinned_nct_ids']))
    def retry(existing):
        saved=read_brief(existing.id)
        if any(saved.payload[key]!=value for key,value in inputs.items()):
            raise ValueError('This form already saved a different brief. Reload Workspace to create a new brief.')
        return saved
    existing=db.session.scalar(select(IntelligenceBrief).where(IntelligenceBrief.save_key==save_key))
    if existing:return retry(existing)
    payload=build_brief(inputs)
    row=IntelligenceBrief(title=payload['title'],schema_version=SCHEMA_VERSION,payload=payload,
        payload_sha256=digest(payload),save_key=save_key)
    db.session.add(row)
    try:db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        existing=db.session.scalar(select(IntelligenceBrief).where(IntelligenceBrief.save_key==save_key))
        if existing:return retry(existing)
        raise
    return row


def brief_tables(cohort):
    """One presentation specification shared by HTML and PDF; full IDs in JSON."""
    s=cohort['summary'];tables=[{'title':'Landscape metrics','headers':['Measure','Value'],
        'rows':[[METRIC_LABELS[k],v['value']] for k,v in s['metrics'].items()],
        'note':f"Whole cohort: {s['metrics']['total_trials']['value']} unique studies. Sponsor metrics count raw names; countries count reported names.",'method':s['method_version']}]
    for key,label in [('study_type','Study types'),('status','Trial statuses'),('phase','Interventional phases'),('sponsor','Lead sponsors'),('drug_intervention','Raw drug / biologic names')]:
        tables.append({'title':label,'headers':['Reported category','Studies'],'rows':[[r['label'],r['count']] for r in s['groups'][key][:10]],
            'note':f"Top 10 of {len(s['groups'][key])} categories. "+({'phase':f"Interventional denominator: {s['phase_denominator']}.",'study_type':'Groups partition the whole cohort, including unknown values.','status':'Groups partition the whole cohort, including unknown values.','sponsor':'Lead sponsors only; exact reported names. Missing sponsor names are excluded.','drug_intervention':'Distinct studies per raw name; groups can overlap. Names are not alias-normalized.'}[key]),'method':s['method_version']})
    for key,r in cohort['reports'].items():
        note=r.get('limitation','');rows=[]
        if key=='regulatory':rows=[[g['label'],g['count']] for g in r['results_groups'].values()];note+=' Results groups partition the whole cohort.'
        elif key=='sites':rows=[[k.replace('_',' ').title(),v] for k,v in r['metrics'].items()]
        elif key=='safety':rows=[[k.replace('_',' ').title(),g['count']] for k,g in r['coverage'].items()]
        elif key=='interactions':rows=[[k.replace('_',' ').title(),g['count']] for k,g in r['coverage'].items()]
        elif key=='stopping':rows=[[g['status'],g['count']] for g in r['status_counts']]+[['Selected stopped studies',r['selected_trials']],['Reported reason',r['reported_reasons']],['Missing / invalid reason',r['unknown_reasons']]]
        elif key=='protocols':rows=[['Interventional studies',r['interventional_trials']],['Complete feature profiles',r['complete_profiles']],['Partial feature profiles',r['partial_profiles']],['Not assessed',r['not_assessed']]]
        tables.append({'title':SECTIONS[key],'headers':['Source measure','Studies / objects as labeled'],'rows':rows,'note':note,'method':r['method_version']})
        if key=='regulatory':
            tables.append({'title':'Reported FDA and monitoring fields','headers':['Source field','Yes','No','Unreported','Invalid'],
                'rows':[[g['label'],*[g['groups'][state]['count'] for state in ('yes','no','unreported','invalid')]] for g in r['oversight'].values()],
                'note':'Each field independently partitions the whole cohort. These are reported indicators, not approval or compliance determinations.','method':r['method_version']})
    return tables


def reference_urls(value):
    found=set()
    def visit(v):
        if isinstance(v,dict):
            for k,item in v.items():
                if k in ('url','definition_url','source_url') and isinstance(item,str) and item.startswith(('https://','http://')):found.add(item)
                elif k not in ('evidence','pinned_trials'):visit(item)
        elif isinstance(v,list):
            for item in v:visit(item)
    visit(value)
    return sorted(found)


def register_workspace_commands(app):
    @app.cli.command('workspace-check')
    def workspace_check():
        try:
            workspace_ready()
            rows=list(db.session.scalars(select(IntelligenceBrief).order_by(IntelligenceBrief.id)))
            for row in rows:read_brief(row.id)
        except (ValueError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
        click.echo(f'Workspace ready. Saved briefs: {len(rows)}; payload integrity checks passed.')
