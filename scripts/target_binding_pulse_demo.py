#!/usr/bin/env python3
"""Fixed invented concentration pulse; no Flask or application storage initialization."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import types
import uuid


def _load():
    folder=Path(__file__).resolve().parents[1]/'intelligence_store'
    # A private namespace permits the relative helper import without executing
    # the real intelligence_store initializer or altering its module identity.
    package_name='_standalone_binding_'+uuid.uuid4().hex
    package=types.ModuleType(package_name);package.__path__=[str(folder)]
    sys.modules[package_name]=package
    name=package_name+'.target_binding_schedule'
    try:
        spec=importlib.util.spec_from_file_location(name,folder/'target_binding_schedule.py')
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        return module
    finally:
        for key in list(sys.modules):
            if key==package_name or key.startswith(package_name+'.'):sys.modules.pop(key,None)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true',dest='json_output')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output and args.output.exists():raise ValueError('Output exists; choose a new filename.')
        report=_load().binding_pulse_example()
        rendered=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:stream.write(rendered)
        if args.json_output:print(rendered,end='')
        else:
            print('Invented free-site pulse | 10 nM until 4 h, then 0 nM | No patient or drug')
            print('Time (h) | Free concentration (nM) | Slower fraction | Faster fraction')
            for a,b in zip(report['slow_example']['points'],report['fast_example']['points']):
                print(f"{a['time_h']:g} | {a['free_concentration_nm']:g} | {a['fraction_bound']:.6g} | {b['fraction_bound']:.6g}")
            print('Concentration switches externally; binding fraction remains continuous.')
            print('Clinical prediction validated: false | Patient simulation ready: false')
            if args.output:print(f'Exported: {args.output}')
        return 0
    except (OSError,ValueError) as exc:
        print(f'Error: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
