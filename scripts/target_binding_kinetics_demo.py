#!/usr/bin/env python3
"""Compare two fixed invented binding-rate examples without Flask/storage initialization."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true',dest='json_output')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output and args.output.exists():raise ValueError('Output exists; choose a new filename.')
        path=Path(__file__).resolve().parents[1]/'intelligence_store/target_binding_kinetics.py'
        spec=importlib.util.spec_from_file_location('standalone_binding_kinetics',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        report=module.binding_kinetics_example()
        rendered=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:stream.write(rendered)
        if args.json_output:print(rendered,end='')
        else:
            print('Invented binding kinetics | Constant free target-site concentration: 10 nM')
            print('Both examples: Kd 10 nM | Equilibrium bound fraction 0.5 | Initial fraction 0')
            print('Time (h) | Slower example fraction | Faster example fraction')
            for a,b in zip(report['slow_example']['points'],report['fast_example']['points']):
                print(f"{a['time_h']:g} | {a['fraction_bound']:.6g} | {b['fraction_bound']:.6g}")
            print('Clinical prediction validated: false | Patient simulation ready: false')
            print('Binding only; no drug, patient, plasma PK, efficacy or toxicity model is attached.')
            if args.output:print(f'Exported: {args.output}')
        return 0
    except (ValueError,OSError) as exc:
        print(f'Error: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
