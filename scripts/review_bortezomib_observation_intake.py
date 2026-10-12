"""Read-only extraction review. Does not calculate model predictions."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_observation_intake', ROOT/'intelligence_store/bortezomib_observation_intake.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def archive_hashes(document, input_path):
    hashes = {}
    base = input_path.parent.resolve()
    for source in document.get('sources', []):
        if not isinstance(source, dict):
            raise ValueError('Each source must be an object')
        archive = source.get('archive_file')
        if archive is None:
            continue
        if not isinstance(archive, str) or not archive.strip():
            raise ValueError('archive_file must name a relative file beside the input')
        path = Path(archive)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Archive path must remain inside the input directory')
        path = (base/path).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError('Archive path is missing or leaves the input directory')
        if path.stat().st_size > 50*1024*1024:
            raise ValueError('Archived source exceeds 50 MiB review limit')
        sid = source.get('id')
        if not model.filled(sid) or sid in hashes:
            raise ValueError('Archive source IDs must be unique and nonempty')
        hashes[sid] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=model.TEMPLATE_PATH)
    parser.add_argument('--output', type=Path, help='Write a new report; never overwrite.')
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 5*1024*1024:
            raise ValueError('Input exceeds 5 MiB review limit')
        data = model.load_json(args.input)
        if not isinstance(data, dict):
            raise ValueError('Input must be a JSON object')
        report = model.review_intake(data, verified_archive_hashes=archive_hashes(data, args.input))
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, 'Observation review failed: '+str(exc)+'\n')
    print('Bortezomib observation intake | '+report['status'])
    print('Submitted records:', report['submitted_record_count'])
    print('Structurally matched records:', report['structurally_matched_record_count'])
    print('Blocking issues:', len(report['blocking_issues']))
    for issue in report['blocking_issues']:
        print(' - '+issue)
    print('No fitting or patient prediction. Step105 discrepancy remains unresolved.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
