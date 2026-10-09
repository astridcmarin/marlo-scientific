#!/usr/bin/env python3
"""Print the local assay-condition extraction; no application initialization."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def _load():
    path=Path(__file__).resolve().parents[1]/'intelligence_store/assay_evidence.py'
    spec=importlib.util.spec_from_file_location('standalone_assay_evidence',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true',dest='json_output')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output and args.output.exists():raise ValueError('Output exists; choose a new filename.')
        report=_load().build_assay_review();packet=report['assay_extraction']
        rendered=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:stream.write(rendered)
        if args.json_output:print(rendered,end='')
        else:
            print('Lenalidomide assay review | Lu Figure 2D | Protocol conditions only')
            print('Status: '+packet['status'])
            for condition in packet['assay']['conditions']:
                print(f"{condition['field']}: {condition['value']:g} {condition['unit']} | {condition['source_locator']}")
            print('Extracted numerical protein measurements: 0 (not zero protein abundance)')
            print('Supplement review: pending | Independent verification: pending')
            print('Fitting: not_run | Simulation: not_run | Patient simulation ready: false')
            if args.output:print('Exported: '+str(args.output))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print('Error: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
