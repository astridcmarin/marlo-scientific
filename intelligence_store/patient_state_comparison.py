"""Verified synthetic input comparison without clinical inference."""
import copy
import json
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .patient_state import UNITS_V2, digest, unknown_field
from .patient_state_revisions import read_revision

METHOD_VERSION='patient-state-comparison-v1.0'
SCHEMA_VERSION='patient-state-comparison-v1'
METADATA=('origin','observed_at','source_ref')
LIMITATION=('Compares recorded synthetic inputs and metadata only. Revision order and saving time do not '
            'establish biological progression or observation order. No normal-range interpretation, exposure '
            'adjustment, dose recommendation, efficacy or toxicity prediction is performed. Source references '
            'are recorded metadata, not independently authenticated evidence.')


def compare_revisions(left_id,right_id,*,scenario_id=None):
    left,right=read_revision(left_id),read_revision(right_id)
    if left is None or right is None:
        raise ValueError('One or both patient-state revision records do not exist.')
    if left.scenario_id!=right.scenario_id:
        raise ValueError('Choose two revisions attached to the same saved scenario.')
    if scenario_id is not None and (type(scenario_id) is not int or scenario_id<1 or left.scenario_id!=scenario_id):
        raise ValueError('Revision records do not belong to this saved scenario.')
    return _compare_verified_revisions(left,right)


def _compare_verified_revisions(left,right):
    """Compare fields after the caller has verified each scenario anchor."""
    rows=[]
    counts={key:0 for key in ('unchanged','value_changed','became_known','became_unknown','metadata_only')}
    left_fields,right_fields=left.payload['state']['fields'],right.payload['state']['fields']
    # Fields of the newer schema appear only if either side has them; a v1 side reads them as unknown.
    for name in [n for n in UNITS_V2 if n in left_fields or n in right_fields]:
        a,b=left_fields.get(name,unknown_field(name)),right_fields.get(name,unknown_field(name))
        metadata=[key for key in METADATA if a[key]!=b[key]]
        if a['value'] is None and b['value'] is not None:category='became_known'
        elif a['value'] is not None and b['value'] is None:category='became_unknown'
        elif a['value']!=b['value']:category='value_changed'
        elif metadata:category='metadata_only'
        else:category='unchanged'
        counts[category]+=1
        rows.append({'field':name,'unit':UNITS_V2[name],'category':category,'metadata_changes':metadata,
                     'left':copy.deepcopy(a),'right':copy.deepcopy(b)})
    def captured(row):
        return {'revision_id':row.id,'revision_number':row.revision_number,'title':row.title,
                'saved_at_utc':row.payload['saved_at_utc'],'state_sha256':row.state_sha256,
                'payload_sha256':row.payload_sha256,'parent_revision_id':row.parent_revision_id,
                'validation_version':row.payload['validation_version']}
    report={'schema_version':SCHEMA_VERSION,'method_version':METHOD_VERSION,'scenario_id':left.scenario_id,
            'scenario_payload_sha256':left.payload['scenario_payload_sha256'],'direction':'left_to_right',
            'left':captured(left),'right':captured(right),'field_count':len(rows),'counts':counts,
            'fields':rows,'limitation':LIMITATION}
    report['report_sha256']=digest(report)
    return report


def register_patient_state_comparison_commands(app):
    @app.cli.command('patient-state-compare')
    @click.option('--left',type=click.IntRange(min=1),required=True,help='Left revision record ID, not revision number.')
    @click.option('--right',type=click.IntRange(min=1),required=True,help='Right revision record ID, not revision number.')
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def patient_state_compare(left,right,output):
        """Compare two verified states from one saved synthetic scenario."""
        try:
            text=json.dumps(compare_revisions(left,right),indent=2,ensure_ascii=False,allow_nan=False)+'\n'
            if output:
                with output.open('x',encoding='utf-8') as handle:handle.write(text)
                click.echo(f'Saved comparison: {output}')
            else:click.echo(text,nl=False)
        except (ValueError,OSError,SQLAlchemyError) as exc:
            raise click.ClickException(str(exc)) from exc
