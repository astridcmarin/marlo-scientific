"""Run a standalone invented turnover example without initializing Flask/storage."""
import argparse
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    try:
        source = Path(__file__).resolve().parents[1]/'intelligence_store/protein_turnover.py'
        spec = importlib.util.spec_from_file_location('_standalone_turnover_demo',source)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        examples = module.turnover_example()
        if args.output:
            with args.output.open('x',encoding='utf-8') as handle:
                handle.write(json.dumps(examples,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
            print('Saved invented turnover example:',args.output)
        else:
            print('Invented normalized protein turnover | No drug or patient')
            print('Loss multiplied by 4 until 4 h, then baseline loss resumes; synthesis stays constant.')
            print('Time (h) | Faster relative amount | Slower relative amount')
            for left,right in zip(examples['faster_turnover']['points'],examples['slower_turnover']['points']):
                print(f"{left['time_h']:g} | {left['relative_amount']:.6g} | {right['relative_amount']:.6g}")
            print('Clinical prediction validated: false | Patient simulation ready: false')
    except (OSError,ValueError) as exc:
        parser.exit(1,'Turnover demonstration failed: '+str(exc)+'\n')


if __name__=='__main__':main()
