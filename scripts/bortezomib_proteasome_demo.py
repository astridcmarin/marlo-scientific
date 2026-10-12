"""Run directly without importing the Flask application or touching its database."""
import argparse
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Save JSON to a new file; never overwrite.')
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1]/'intelligence_store/bortezomib_proteasome.py'
    spec = importlib.util.spec_from_file_location('_standalone_bortezomib_proteasome',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        report = module.proteasome_example()
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:
                stream.write(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    except (ValueError,OSError) as exc:
        parser.exit(1,f'Calculation/export failed: {exc}\n')
    print('Bortezomib | Published equation component | Hypothetical concentration inputs')
    print('Plasma concentration (nM) | Proteasome activity (% of baseline)')
    for point in report['points']:
        print(f"{point['plasma_concentration_nm']:g} | {point['activity_percent_of_baseline']:.6g}")
    print('At IC50, half of the maximum inhibition is reached, not 50% activity.')
    print('No dose-to-concentration calculation, patient prediction, efficacy or toxicity.')
    print('Clinical prediction validated: false | Patient simulation ready: false')


if __name__ == '__main__':
    main()
