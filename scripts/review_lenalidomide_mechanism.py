#!/usr/bin/env python3
"""Print the bundled, source-linked mechanism research plan. No Flask or solver."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PACKET_PATH=Path(__file__).resolve().parents[1]/'intelligence_store/data/lenalidomide_mechanism_evidence_plan_v1.json'


def build_report():
    raw=PACKET_PATH.read_bytes()
    if len(raw)>100_000:raise ValueError('Evidence plan exceeds the supported file size.')
    packet=json.loads(raw)
    if packet.get('schema_version')!='mechanism-evidence-plan-v1' or packet.get('entity_id')!='lenalidomide':
        raise ValueError('Unsupported mechanism evidence plan.')
    # This command summarizes a planning document; it never promotes readiness.
    return {'schema_version':'mechanism-evidence-plan-report-v1',
            'packet_sha256':hashlib.sha256(raw).hexdigest(),'evidence_plan':packet,
            'simulation_status':'not_run','clinical_prediction_validated':False,
            'ready_for_patient_simulation':False,
            'verification_scope':'Packet identity and size only. Source statements, provenance and parameters are recorded declarations; no independent evidence verification is performed.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true',dest='json_output')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output and args.output.exists():raise ValueError('Output exists; choose a new filename.')
        report=build_report();packet=report['evidence_plan']
        rendered=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:stream.write(rendered)
        if args.json_output:print(rendered,end='')
        else:
            print('Lenalidomide / cereblon | Initial research plan')
            print('Status: '+packet['status'])
            print('Source: '+packet['source']['doi'])
            print('Independent source review: pending | Supplement review: pending')
            print('Decision: '+packet['architecture_decision']['decision'])
            print('Next candidate observable: '+packet['architecture_decision']['next_candidate_observable'])
            print('Quantitative input values in the bundled plan: not extracted')
            for item in packet['missing_evidence']:print('- '+item)
            print('Simulation: not_run | Clinical prediction validated: false | Patient simulation ready: false')
            if args.output:print('Exported: '+str(args.output))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print('Error: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
