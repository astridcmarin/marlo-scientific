"""Read the bundled scientific comparison without importing the Flask app."""
import argparse
import importlib.util
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Optional new JSON file; never overwrite.')
    args=parser.parse_args()
    path=Path(__file__).resolve().parents[1]/'intelligence_store/bortezomib_evidence_review.py'
    spec=importlib.util.spec_from_file_location('_standalone_btz_review',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    try:
        report=module.build_evidence_review()
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:
                stream.write(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    except (OSError,ValueError) as exc:parser.exit(1,f'Review/export failed: {exc}\n')
    print('Bortezomib evidence review | '+report['status'])
    print(f"Observed summaries: {report['summary_count']} | Above equation ceiling: {report['summaries_above_ceiling']}")
    print('Matched concentration-response pairs: 0 | Fitting: not_run')
    print('Development-source study; not independent validation.')
    print('Clinical prediction validated: false | Patient simulation ready: false')


if __name__=='__main__':main()
