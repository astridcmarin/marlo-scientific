#!/usr/bin/env python3
"""Read-only file checkpoint for Step 75 UI and an exported educational archive."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import types
import io
import json
import math
from pathlib import Path
import re
import sys

VERSION = 'patient-lab-timeline-checkpoint-v1'
HEADERS = ['export_version','purpose','clinical_prediction_validated','patient_simulation_ready',
    'run_id','scenario_id','revision_id','payload_sha256','report_sha256','revision_payload_sha256',
    'execution_contract_sha256','method_version','solver_method_version','boundary_coverage',
    'sampled_point_index_zero_based','state','request_amount_mg','time_h','absorption_amount_mg',
    *[f'transit_{i}_amount_mg' for i in range(1,8)],'central_amount_mg','eliminated_amount_mg',
    'concentration_ng_ml','auc_0_t_ng_h_ml','cumulative_requested_amount_mg','accounted_amount_mg']


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',', ':'),allow_nan=False).encode('utf-8')).hexdigest()


def reject_constant(value):
    raise ValueError('Nonfinite JSON value')


def unique_object(pairs):
    result = {}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def read_json(path):
    if path.stat().st_size > 20*1024*1024: raise ValueError('JSON file exceeds 20 MiB')
    return json.loads(path.read_text(encoding='utf-8'),parse_constant=reject_constant,object_pairs_hook=unique_object)


def positive(value):
    return type(value) is int and 0 < value <= 9007199254740991


def hashed_report(report):
    body = dict(report)
    expected = body.pop('report_sha256')
    if not isinstance(expected,str) or digest(body) != expected: raise ValueError('Nested report checksum mismatch')
    return expected


def archive_context(archive):
    p = archive['payload']; report = p['report']; review = report['preflight_review']; binding = review['binding']
    if not positive(archive['run_id']) or not positive(p['revision_id']) or not positive(binding['scenario_id']):
        raise ValueError('Invalid archive identifiers')
    if p['schema_version'] != 'saved-educational-pk-run-v1' or digest(p) != archive['payload_sha256']:
        raise ValueError('Archive payload checksum/schema mismatch')
    report_sha = hashed_report(report)
    if report['preflight_report_sha256'] != hashed_report(review): raise ValueError('Preflight report linkage mismatch')
    hashed_report(review['treatment_request_preview'])
    if review['binding_sha256'] != digest(binding) or binding['revision_id'] != p['revision_id']:
        raise ValueError('Contained revision binding mismatch')
    if p['identity'] != {'revision_id':p['revision_id'],'title':p['title'],'report_sha256':report_sha}:
        raise ValueError('Archive identity mismatch')
    if report['clinical_prediction_validated'] is not False or report['ready_for_patient_simulation'] is not False:
        raise ValueError('Unexpected educational readiness flags')
    if report['method_version'] != 'hughes-educational-pk-v1.0' or report['status'] != 'completed_educational_calculation':
        raise ValueError('Unsupported archived model/status')
    for value in (binding['revision_payload_sha256'],report['execution_contract_sha256']):
        if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value): raise ValueError('Missing source digest')
    if not re.fullmatch('[a-zA-Z0-9._-]{1,100}',report['solver_method_version']): raise ValueError('Unsupported solver identifier')
    metadata = {'run_id':archive['run_id'],'scenario_id':binding['scenario_id'],'revision_id':p['revision_id'],
        'payload_sha256':archive['payload_sha256'],'report_sha256':report_sha,
        'revision_payload_sha256':binding['revision_payload_sha256'],
        'execution_contract_sha256':report['execution_contract_sha256'],
        'method_version':report['method_version'],'solver_method_version':report['solver_method_version']}
    return report,metadata


def verify_csv(text,timeline,metadata):
    m = metadata
    prefix = ['archived-pk-timeline-csv-v1','synthetic_educational','false','false',
        str(m['run_id']),str(m['scenario_id']),str(m['revision_id']),m['payload_sha256'],m['report_sha256'],
        m['revision_payload_sha256'],m['execution_contract_sha256'],m['method_version'],m['solver_method_version'],
        'available' if timeline['events']['available'] else 'unavailable']
    expected = []
    events = {e['index']:e for e in timeline['events']['items']}
    def row(p,index,state,amount):
        expected.append((prefix+[str(index),state], [amount,p['time_h'],*p['amounts_mg'],
            p['concentration_ng_ml'],p['auc_ng_h_ml'],p['requested_mg'],p['accounted_mg']]))
    for index,p in enumerate(timeline['points']):
        event = events.get(index)
        if event: row(event['before'],index,'boundary_before_request',event['amount_mg'])
        row(p,index,'sampled_after_request' if event else 'sampled',event['amount_mg'] if event else '')
    rows = list(csv.reader(io.StringIO(text),strict=True))
    if not rows or rows[0] != HEADERS or len(rows)-1 != len(expected): raise ValueError('CSV headers or row count mismatch')
    numeric = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z')
    for number,(cells,(strings,values)) in enumerate(zip(rows[1:],expected),start=1):
        if len(cells) != len(HEADERS) or cells[:16] != strings: raise ValueError(f'CSV row {number} identifiers/state mismatch')
        for cell,value in zip(cells[16:],values):
            if value == '' and cell == '': continue
            if value == '' or not numeric.fullmatch(cell): raise ValueError(f'CSV row {number} numeric format mismatch')
            parsed = float(cell)
            if not math.isfinite(parsed) or parsed != value: raise ValueError(f'CSV row {number} archived value mismatch')
    return len(expected)


def checkpoint(root,archive_path,manifest_path,csv_path=None):
    checks=[]; details={}
    def check(code,operation):
        try:
            result=operation(); checks.append({'code':code,'status':'passed'}); return result
        except (OSError,ValueError,KeyError,TypeError,AttributeError,OverflowError,csv.Error) as exc:
            checks.append({'code':code,'status':'failed','reason':str(exc)}); return None
    manifest=read_json(manifest_path)
    if manifest.get('schema_version')!='patient-lab-timeline-assets-v1': raise ValueError('Unsupported checkpoint manifest version')
    assets=manifest['assets']
    required={'landscape_ui/pk_compartment_timeline.py','landscape_ui/templates/pk_compartment_timeline.html','landscape_ui/static/pk-compartment-timeline.css','landscape_ui/static/pk-compartment-timeline.js','landscape_ui/static/pk-timeline-csv.js'}
    if not isinstance(assets,dict) or set(assets)!=required: raise ValueError('Unsupported checkpoint asset manifest')
    def installed_assets():
        for relative,sha in assets.items():
            path=(root/relative).resolve()
            if not path.is_relative_to(root.resolve()) or not re.fullmatch('[a-f0-9]{64}',sha): raise ValueError('Invalid manifest path/digest')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=sha: raise ValueError(f'Asset differs from Step 75: {relative}')
        details['installed_asset_sha256']=assets
        return True
    matched=check('step75_asset_identity',installed_assets)
    def hooks():
        route=(root/'landscape_ui/educational_pk_run_pages.py').read_text(encoding='utf-8')
        page=(root/'landscape_ui/templates/landscape_saved_pk_run.html').read_text(encoding='utf-8')
        for source,anchor in [(route,'from .pk_compartment_timeline import build_compartment_timeline'),
            (route,'timeline=build_compartment_timeline(report)'),(page,'{% include "pk_compartment_timeline.html" %}'),
            (page,'data-pk-archive-chart="{{ chart.unit }}"')]:
            if source.count(anchor)!=1: raise ValueError('Expected unique timeline/chart integration hook not found')
        return True
    check('static_integration_hooks',hooks)
    context=check('exported_archive_checksums_and_contained_links',lambda:archive_context(read_json(archive_path)))
    timeline=None
    if context and matched:
        report,metadata=context; details['archive_identifiers']=metadata
        def projection():
            path=root/'landscape_ui/pk_compartment_timeline.py'
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=assets['landscape_ui/pk_compartment_timeline.py']: raise ValueError('Projection helper changed during verification')
            module=types.ModuleType('verified_timeline_projection')
            exec(compile(raw,str(path),'exec'),module.__dict__)
            result=module.build_compartment_timeline(report)
            if not result['available']: raise ValueError(result['reason'])
            details.update(sampled_points=len(result['points']),request_boundaries=len(result['events']['items']),
                boundary_coverage='available' if result['events']['available'] else 'unavailable')
            return result
        timeline=check('archived_timeline_projection',projection)
        if timeline:
            if not timeline['events']['available']:
                checks.append({'code':'request_boundaries','status':'warning','reason':timeline['events']['reason']})
            if csv_path:
                def csv_check():
                    if csv_path.stat().st_size>4*1024*1024: raise ValueError('CSV exceeds 4 MiB')
                    details['verified_csv_rows']=verify_csv(csv_path.read_text(encoding='utf-8-sig'),timeline,metadata)
                    details['verified_csv_sha256']=hashlib.sha256(csv_path.read_bytes()).hexdigest()
                check('downloaded_csv_matches_archive',csv_check)
    if not csv_path: checks.append({'code':'downloaded_csv_matches_archive','status':'pending','reason':'No browser-downloaded CSV supplied'})
    elif not timeline: checks.append({'code':'downloaded_csv_matches_archive','status':'pending','reason':'Archive or asset prerequisite failed'})
    failed=any(c['status']=='failed' for c in checks)
    return {'schema_version':VERSION,'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'checkpoint_failed' if failed else 'static_and_archive_checks_passed_browser_review_pending',
        'checks':checks,'details':details,'clinical_prediction_validated':False,'patient_simulation_ready':False,
        'browser_review_status':'not_verified','independent_database_anchor_verification':'not_performed_by_this_script',
        'scope':'File checks only. Export with patient-pk-export first for existing database/source-anchor integrity checks. No model solve, browser execution, clinical validation, deployment or data repair.',
        'manual_review_pending':['Slider and request jumps','Before/after snapshots','Play/Pause and hidden-page pause',
            'Both chart markers','Safari CSV download','Keyboard controls and readable layout']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',type=Path,default=Path.cwd())
    parser.add_argument('--archive-file',type=Path,required=True)
    parser.add_argument('--csv-file',type=Path)
    parser.add_argument('--manifest',type=Path,default=Path(__file__).with_name('patient_lab_timeline_assets_v1.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output and args.output.exists(): raise ValueError('Output exists; choose a new filename')
        result=checkpoint(args.project_root.resolve(),args.archive_file,args.manifest,args.csv_file)
        result['checkpoint_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        rendered=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream: stream.write(rendered)
        print(rendered,end='')
        return 1 if result['status']=='checkpoint_failed' else 0
    except (OSError,ValueError,KeyError,TypeError,RecursionError) as exc:
        print(f'Error: {exc}',file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
