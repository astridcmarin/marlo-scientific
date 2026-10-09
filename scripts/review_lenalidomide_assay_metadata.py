#!/usr/bin/env python3
"""Read the reviewed assay metadata and optionally match local source PDF hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PACKET_PATH=Path(__file__).resolve().parents[1]/'intelligence_store/data/lenalidomide_assay_metadata_v2.json'


def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):digest.update(block)
    return digest.hexdigest()


def build_report(main_file=None,supplement_file=None):
    raw=PACKET_PATH.read_bytes()
    if len(raw)>100_000:raise ValueError('Metadata packet is too large.')
    p=json.loads(raw)
    if p.get('schema_version')!='assay-metadata-review-v2' or p.get('entity_id')!='lenalidomide':raise ValueError('Unsupported metadata packet.')
    if p['clinical_prediction_validated'] is not False or p['ready_for_patient_simulation'] is not False:raise ValueError('Unexpected readiness promotion.')
    if p['assay']['protein_measurements']!=[] or p['model_assessment']['data_ready_for_fitting'] is not False:
        raise ValueError('This metadata-only report does not accept numerical measurements or fitting readiness.')
    if p['source']['source_bytes_sha256']==p['supplement']['source_bytes_sha256']:raise ValueError('Main and supplementary source hashes must differ.')
    checks={}
    for role,path,expected in [('main',main_file,p['source']['source_bytes_sha256']),
                              ('supplement',supplement_file,p['supplement']['source_bytes_sha256'])]:
        if path is None:checks[role]={'status':'not_checked','sha256':None}
        else:
            actual=file_sha(path)
            if actual!=expected:raise ValueError(f'{role} file does not match the inspected source hash; no report exported.')
            checks[role]={'status':'matches_inspected_source','sha256':actual}
    report={'schema_version':'assay-metadata-report-v2','metadata_packet_sha256':hashlib.sha256(raw).hexdigest(),
        'assay_metadata':p,'local_source_checks':checks,'simulation_status':'not_run',
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'verification_scope':'Optional byte identity matching to inspected copies. No independent scientific review, intensity extraction or parameter fitting.'}
    report['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main-file',type=Path)
    parser.add_argument('--supplement-file',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--json',action='store_true',dest='json_output')
    args=parser.parse_args(argv)
    try:
        if args.output and args.output.exists():raise ValueError('Output exists; choose a new filename.')
        report=build_report(args.main_file,args.supplement_file)
        rendered=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:stream.write(rendered)
        if args.json_output:print(rendered,end='')
        else:
            print('Lu Figure 2D | Source-reviewed assay metadata')
            print('Chase times: 0, 30, 60, 90, 120 min = 0, 0.5, 1, 1.5, 2 h')
            print('Groups: parental and CRBN-/- T11, each with DMSO or LEN pretreatment')
            print('Readouts: IKZF1 / IKZF3 | Loading control: Vinculin')
            print('Relevant supplement sections reviewed; full-document and independent review not established.')
            print('Assay medium: unresolved (culture section RPMI; generic chase method DMEM)')
            for role,check in report['local_source_checks'].items():print(role+' source: '+check['status'])
            print('Numerical protein measurements: none extracted | Fitting: not_run')
            print('Clinical prediction validated: false | Patient simulation ready: false')
            if args.output:print('Exported: '+str(args.output))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('Error: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
