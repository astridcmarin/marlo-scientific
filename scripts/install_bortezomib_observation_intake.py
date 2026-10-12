"""Add the Steps106–108 intake toolkit without changing existing application files."""
import argparse
import ast
import hashlib
from pathlib import Path

ASSETS = (
    'intelligence_store/bortezomib_observation_intake.py',
    'intelligence_store/data/bortezomib_observation_template_v1.json',
    'scripts/review_bortezomib_observation_intake.py',
    'scripts/check_bortezomib_observation_intake.py',
    'scripts/install_bortezomib_observation_intake.py',
    'tests/test_bortezomib_observation_intake.py',
    'docs/BORTEZOMIB_OBSERVATION_INTAKE_STEPS106_108.md',
)
PINS = {
    'intelligence_store/data/bortezomib_proteasome_reference_v1.json':
        'ac5e3ad9a9cb8156ca019ba0b9bf31956b96c973631e595ebafabdc4166b59be',
    'intelligence_store/data/bortezomib_observed_summary_v1.json':
        '2f077db4f1b44b65bd7e634e067d25b5a703e9563a6a21e91f5c57288bb24ae9',
}


def install(root, bundle=None):
    root = Path(root).resolve()
    bundle = Path(bundle or Path(__file__).resolve().parents[1])
    for name, pin in PINS.items():
        path = root/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError('Missing or changed Step104/105 reference: '+name)
    if not (root/'intelligence_store/bortezomib_evidence_review.py').is_file():
        raise ValueError('Step105 evidence-review module is required')
    payload = {name: (bundle/name).read_bytes() for name in ASSETS}
    for name, data in payload.items():
        if name.endswith('.py'):
            ast.parse(data, filename=name)
        target = root/name
        if not target.resolve().is_relative_to(root):
            raise ValueError('Target path leaves the project: '+name)
        if target.exists() and (not target.is_file() or target.read_bytes() != data):
            raise ValueError('Existing customized file; no files changed: '+name)
    created = []
    try:
        for name, data in payload.items():
            target = root/name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    created.append(target)
                    stream.write(data)
    except OSError:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return 'Installed Steps106–108 observation intake.' if created else 'Already installed.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        print(install(args.project))
    except (OSError, ValueError) as exc:
        parser.exit(1, 'Installation failed: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
