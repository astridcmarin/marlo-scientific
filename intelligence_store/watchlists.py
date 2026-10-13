"""Local curation of retained trial evidence with explicit analyst review state."""
import copy
from datetime import datetime
import re
import click
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, inspect, select, update
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .extensions import db
from .models import TrialSnapshot, utc_now
from .summaries import summarize_cohort
from .regulatory import digest
from .normalization import _mapping, _text

SCHEMA_VERSION='frozen-trial-watchlist-v1.0'
STATES={'to_review':'To review','follow_up':'Follow up','reviewed':'Reviewed','archived':'Archived'}


class TrialWatchlist(db.Model):
    __tablename__='trial_watchlist'
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(160))
    created_at_utc:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    payload:Mapped[dict]=mapped_column(JSON)
    payload_sha256:Mapped[str]=mapped_column(String(64))
    save_key:Mapped[str]=mapped_column(String(64),unique=True)


class WatchlistTrial(db.Model):
    __tablename__='watchlist_trial'
    __table_args__=(UniqueConstraint('watchlist_id','nct_id'),
        CheckConstraint("review_status IN ('to_review','follow_up','reviewed','archived')",name='review_status_allowed'))
    id:Mapped[int]=mapped_column(primary_key=True)
    watchlist_id:Mapped[int]=mapped_column(ForeignKey('trial_watchlist.id'),index=True)
    nct_id:Mapped[str]=mapped_column(String(11))
    source_payload:Mapped[dict]=mapped_column(JSON)
    source_sha256:Mapped[str]=mapped_column(String(64))
    review_status:Mapped[str]=mapped_column(String(20),default='to_review')
    notes:Mapped[str]=mapped_column(Text,default='')
    version:Mapped[int]=mapped_column(default=1)
    added_at_utc:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    updated_at_utc:Mapped[datetime]=mapped_column(DateTime,default=utc_now)


def ready():
    inspector=inspect(db.engine)
    if not all(inspector.has_table(name) for name in ('trial_watchlist','watchlist_trial')):
        raise ValueError('Watchlist tables are missing. Generate and apply the Step 20 migration in START_HERE.md.')


def validate_text(value,label,maximum,required=False):
    if not isinstance(value,str) or len(value)>maximum or (required and not value.strip()):
        raise ValueError(f'{label} must contain '+('1 to ' if required else 'at most ')+f'{maximum} characters.')
    if any(ord(c)<32 and c not in '\n\r\t' for c in value):raise ValueError(f'{label} contains an unsupported control character.')
    return value.strip() if required else value


def get_watchlist(list_id):
    ready()
    row=db.session.get(TrialWatchlist,list_id)
    if row is None:return None
    if not isinstance(row.payload,dict) or row.payload.get('schema_version')!=SCHEMA_VERSION or row.payload.get('title')!=row.title or digest(row.payload)!=row.payload_sha256:
        raise ValueError('Saved watchlist source integrity check failed.')
    return row


def create_watchlist(title,cohort_id,save_key):
    ready();title=validate_text(title,'Title',160,True)
    if type(cohort_id) is not int or cohort_id<1:raise ValueError('Choose a valid complete cohort.')
    if not isinstance(save_key,str) or not re.fullmatch(r'[a-f0-9]{64}',save_key):raise ValueError('Invalid submission key.')
    def retry(row):
        row=get_watchlist(row.id)
        if row.title!=title or row.payload['cohort']['id']!=cohort_id:raise ValueError('This form already created a different list. Reload Watchlists to create another.')
        return row
    existing=db.session.scalar(select(TrialWatchlist).where(TrialWatchlist.save_key==save_key))
    if existing:return retry(existing)
    summary=summarize_cohort(cohort_id)
    refs=copy.deepcopy(summary['evidence'])
    snapshots={s.id:s for s in db.session.scalars(select(TrialSnapshot).where(TrialSnapshot.id.in_([r['snapshot_id'] for r in refs.values()])))} if refs else {}
    for nct,ref in refs.items():ref['raw_study_sha256']=digest(snapshots[ref['snapshot_id']].raw_study)
    payload={'schema_version':SCHEMA_VERSION,'title':title,'cohort':summary['cohort'],
        'source_manifest':refs,'source_manifest_sha256':digest(refs),
        'limitation':'A manually curated subset of one frozen query cohort. Review status and notes are analyst workflow fields, not registry status, clinical findings or compliance determinations.'}
    row=TrialWatchlist(title=title,payload=payload,payload_sha256=digest(payload),save_key=save_key)
    db.session.add(row)
    try:db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing=db.session.scalar(select(TrialWatchlist).where(TrialWatchlist.save_key==save_key))
        if existing:return retry(existing)
        raise
    return row


def parse_nct_ids(text):
    if not isinstance(text,str) or len(text)>2000:raise ValueError('Enter at most 50 NCT IDs.')
    ids=sorted(set(s.upper() for s in re.split(r'[\s,;]+',text.strip()) if s))
    if not 1<=len(ids)<=50 or any(not re.fullmatch(r'NCT\d{8}',n) for n in ids):
        raise ValueError('Enter 1 to 50 valid NCT IDs, separated by spaces, commas or new lines.')
    return ids


def add_trials(list_id,text):
    watchlist=get_watchlist(list_id)
    if watchlist is None:raise ValueError('Watchlist does not exist.')
    ids=parse_nct_ids(text);refs=watchlist.payload['source_manifest']
    if any(n not in refs for n in ids):raise ValueError('Every NCT ID must belong to this watchlist’s frozen cohort. No trials were added.')
    present=set(db.session.scalars(select(WatchlistTrial.nct_id).where(WatchlistTrial.watchlist_id==list_id)))
    additions=[]
    for nct in ids:
        if nct in present:continue
        ref=refs[nct];snapshot=db.session.get(TrialSnapshot,ref['snapshot_id'])
        if snapshot is None or snapshot.nct_id!=nct or digest(snapshot.raw_study)!=ref['raw_study_sha256']:
            raise ValueError('A retained source is missing or changed. No trials were added.')
        raw=copy.deepcopy(snapshot.raw_study);p=_mapping(raw.get('protocolSection'))
        source={'nct_id':nct,'title':_text(_mapping(p.get('identificationModule')).get('briefTitle')),
            'registry_status':_text(_mapping(p.get('statusModule')).get('overallStatus')),
            'sponsor':_text(_mapping(_mapping(p.get('sponsorCollaboratorsModule')).get('leadSponsor')).get('name')),
            'evidence':copy.deepcopy(ref),'raw_study':raw}
        additions.append(WatchlistTrial(watchlist_id=list_id,nct_id=nct,source_payload=source,source_sha256=digest(source)))
    db.session.add_all(additions)
    try:db.session.commit()
    except IntegrityError as exc:
        db.session.rollback();raise ValueError('The list changed during this save. Reload and retry; existing trial notes are preserved.') from exc
    return len(additions)


def checked_trial(row,watchlist=None):
    if not isinstance(row.source_payload,dict) or row.source_payload.get('nct_id')!=row.nct_id or digest(row.source_payload)!=row.source_sha256:
        raise ValueError('Saved trial source integrity check failed.')
    watchlist=watchlist or get_watchlist(row.watchlist_id)
    reference=watchlist.payload['source_manifest'].get(row.nct_id) if watchlist else None
    if reference is None or row.source_payload.get('evidence')!=reference or digest(row.source_payload.get('raw_study'))!=reference['raw_study_sha256']:
        raise ValueError('Saved trial source does not match the watchlist manifest.')
    return row


def get_trial(list_id,nct):
    row=db.session.scalar(select(WatchlistTrial).where(WatchlistTrial.watchlist_id==list_id,WatchlistTrial.nct_id==nct))
    return checked_trial(row) if row else None


class ReviewConflict(ValueError):pass


def update_review(list_id,nct,review_status,notes,version):
    if get_watchlist(list_id) is None:raise ValueError('Watchlist does not exist.')
    row=get_trial(list_id,nct)
    if row is None:raise ValueError('Trial is not in this watchlist.')
    notes=validate_text(notes,'Notes',8000)
    if review_status not in STATES:raise ValueError('Choose a valid review status.')
    if type(version) is not int or version<1:raise ValueError('Invalid review version. Reload the trial.')
    changed=db.session.execute(update(WatchlistTrial).where(WatchlistTrial.id==row.id,WatchlistTrial.version==version).values(
        review_status=review_status,notes=notes,version=version+1,updated_at_utc=utc_now()))
    if changed.rowcount!=1:
        db.session.rollback();raise ReviewConflict('Another save changed this trial. Your changes were not applied. Review the current saved notes before saving your draft again.')
    db.session.commit();return get_trial(list_id,nct)


def export_watchlist(list_id):
    watchlist=get_watchlist(list_id)
    if watchlist is None:return None
    rows=list(db.session.scalars(select(WatchlistTrial).where(WatchlistTrial.watchlist_id==list_id).order_by(WatchlistTrial.nct_id)))
    entries=[]
    for row in rows:
        checked_trial(row,watchlist)
        entries.append({'nct_id':row.nct_id,'review_status':row.review_status,'analyst_notes':row.notes,
            'review_version':row.version,'added_at_utc':row.added_at_utc.isoformat(),'updated_at_utc':row.updated_at_utc.isoformat(),
            'source_payload':row.source_payload,'source_sha256':row.source_sha256})
    report={'schema_version':SCHEMA_VERSION,'watchlist_id':watchlist.id,'created_at_utc':watchlist.created_at_utc.isoformat(),
        'export_scope':'whole_watchlist_including_archived','watchlist':watchlist.payload,'watchlist_sha256':watchlist.payload_sha256,
        'selected_trials':len(rows),'review_counts':{s:sum(r.review_status==s for r in rows) for s in STATES},'trials':entries}
    report['export_sha256']=digest(report)
    return report


def register_watchlist_commands(app):
    @app.cli.command('watchlist-check')
    def check():
        try:
            ready();ids=list(db.session.scalars(select(TrialWatchlist.id)))
            for i in ids:export_watchlist(i)
        except (ValueError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
        click.echo(f'Watchlists ready. Saved lists: {len(ids)}; source integrity checks passed.')
