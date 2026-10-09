#!/usr/bin/env python3
"""Run generic invented equilibrium binding examples, without initializing Flask/storage."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def kernel():
    path=Path(__file__).resolve().parents[1]/'intelligence_store/target_occupancy.py'
    spec=importlib.util.spec_from_file_location('standalone_target_occupancy',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kd-nm',type=float)
    parser.add_argument('--free-concentrations-nm',type=float,nargs='+')
    parser.add_argument('--json',action='store_true',dest='json_output')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if (args.kd_nm is None)!=(args.free_concentrations_nm is None):
            raise ValueError('Supply both --kd-nm and --free-concentrations-nm, or neither for the fixed invented example.')
        if args.output and args.output.exists(): raise ValueError('Output already exists; choose a new filename.')
        model=kernel()
        report=model.target_occupancy_example() if args.kd_nm is None else model.calculate_target_occupancy(
            kd_nm=args.kd_nm,free_concentrations_nm=args.free_concentrations_nm)
        rendered=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as handle:handle.write(rendered)
        if args.json_output: print(rendered,end='')
        else:
            print('Generic equilibrium target occupancy | Invented inputs | No drug or patient model')
            print(f"Kd: {report['inputs']['kd']['value']:g} nM")
            print('Free target-site concentration (nM) | Fraction bound')
            for point in report['points']:print(f"{point['free_concentration_nm']:g} | {point['fraction_bound']:.6g}")
            print('Clinical prediction validated: false | Patient simulation ready: false')
            print(report['limitation'])
            if args.output: print(f'Exported: {args.output}')
        return 0
    except (ValueError,OSError,OverflowError) as exc:
        print(f'Error: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
