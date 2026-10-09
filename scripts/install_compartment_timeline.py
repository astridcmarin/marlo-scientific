#!/usr/bin/env python3
"""Add narrow timeline and archived chart integration hooks while preserving the user's existing pages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

IMPORT_ANCHOR = 'from .educational_pk_pages import _charts\n'
NEW_IMPORT = 'from .pk_compartment_timeline import build_compartment_timeline\n'
CONTEXT = 'report=report,review=review,charts=_charts(report),inputs_json='
NEW_CONTEXT = 'report=report,review=review,timeline=build_compartment_timeline(report),charts=_charts(report),inputs_json='
CHART_ANCHOR = '{% for chart in charts %}'
SVG_ANCHOR = '<svg class="transit-chart" viewBox="0 0 780 305"'
SVG_HOOK = SVG_ANCHOR + ' data-pk-archive-chart="{{ chart.unit }}"'
INCLUDE = '{% include "pk_compartment_timeline.html" %}'


def proposed_sources(route, template):
    if NEW_IMPORT not in route:
        if route.count(IMPORT_ANCHOR) != 1:
            raise ValueError('Saved-run route import anchor is not recognized; no existing file was changed')
        route = route.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + NEW_IMPORT, 1)
    elif route.count(NEW_IMPORT) != 1:
        raise ValueError('Duplicate timeline imports; no existing file was changed')
    if NEW_CONTEXT not in route:
        if route.count(CONTEXT) != 1:
            raise ValueError('Saved-run rendering context is not recognized; no existing file was changed')
        route = route.replace(CONTEXT, NEW_CONTEXT, 1)
    elif route.count(NEW_CONTEXT) != 1:
        raise ValueError('Duplicate timeline contexts; no existing file was changed')
    if INCLUDE not in template:
        if template.count(CHART_ANCHOR) != 1:
            raise ValueError('Saved-run chart anchor is not recognized; no existing file was changed')
        template = template.replace(CHART_ANCHOR, INCLUDE + '\n' + CHART_ANCHOR, 1)
    elif template.count(INCLUDE) != 1:
        raise ValueError('Duplicate timeline includes; no existing file was changed')
    if SVG_HOOK not in template:
        if template.count(SVG_ANCHOR) != 1:
            raise ValueError('Saved-run SVG chart anchor is not recognized; no existing file was changed')
        template = template.replace(SVG_ANCHOR, SVG_HOOK, 1)
    elif template.count(SVG_HOOK) != 1:
        raise ValueError('Duplicate archived chart hooks; no existing file was changed')
    return route, template


def atomic_write(path, raw, mode):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name); stream.write(raw)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()


def install(project_root):
    root = Path(project_root).resolve()
    assets = ['landscape_ui/pk_compartment_timeline.py', 'landscape_ui/templates/pk_compartment_timeline.html',
              'landscape_ui/static/pk-compartment-timeline.css', 'landscape_ui/static/pk-compartment-timeline.js']
    if any(not (root / item).is_file() for item in assets):
        raise ValueError('Copy the four timeline assets into the project before running the installer')
    paths = [root / 'landscape_ui/educational_pk_run_pages.py',
             root / 'landscape_ui/templates/landscape_saved_pk_run.html']
    originals = [p.read_bytes() for p in paths]
    modes = [p.stat().st_mode & 0o777 for p in paths]
    proposed = proposed_sources(*(raw.decode('utf-8') for raw in originals))
    changed = [(p, old, new.encode('utf-8'), mode) for p, old, new, mode in zip(paths, originals, proposed, modes)
               if old != new.encode('utf-8')]
    if not changed:
        return {'status': 'already_installed', 'changed_files': []}
    # Validate both integration hooks before changing either existing file.
    if any(path.read_bytes() != old for path, old, _, _ in changed):
        raise ValueError('Existing files changed during preparation; retry after reviewing them')
    backup = root / 'instance' / ('step74-code-backup-' + uuid.uuid4().hex)
    backup.mkdir(parents=True, exist_ok=False)
    records = []
    for path, old, new, _ in changed:
        relative = path.relative_to(root)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(old)
        records.append({'path': str(relative), 'original_sha256': hashlib.sha256(old).hexdigest(),
                        'updated_sha256': hashlib.sha256(new).hexdigest()})
    (backup / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    try:
        for path, old, new, mode in changed: atomic_write(path, new, mode)
    except OSError:
        for path, old, new, mode in changed: atomic_write(path, old, mode)
        raise
    return {'status': 'installed', 'changed_files': [str(p.relative_to(root)) for p, _, _, _ in changed],
            'code_backup_directory': str(backup)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.project_root), indent=2)); return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'Error: {exc}'); return 1


if __name__ == '__main__': raise SystemExit(main())
