#!/usr/bin/env python3
"""Install the generic binding pulse page with narrow backed-up integration edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

REGISTER = 'from .binding_pulse_pages import register_binding_pulse_pages\nregister_binding_pulse_pages(bp)\n'
REGISTER_ANCHOR = 'def register_landscape(app):'
NAV_ANCHOR = '{% set patient_active = request.endpoint in ['
NAV_HOOK = NAV_ANCHOR + "'landscape.binding_pulse_demo', "
OVERVIEW_ANCHOR = '<h1>Patient Lab overview</h1>'
LINK = '<p data-binding-pulse-link><a class="button secondary" href="{{ url_for(\'landscape.binding_pulse_demo\') }}">Explore invented binding pulse (separate demonstration)</a></p>'


def proposed_sources(initializer,base,overview):
    if REGISTER not in initializer:
        if initializer.count(REGISTER_ANCHOR)!=1 or 'register_binding_pulse_pages' in initializer:
            raise ValueError('Blueprint registration anchor is unrecognized or partially installed')
        initializer=initializer.replace(REGISTER_ANCHOR,REGISTER+'\n'+REGISTER_ANCHOR,1)
    elif initializer.count(REGISTER)!=1: raise ValueError('Duplicate binding pulse registration')
    if NAV_HOOK not in base:
        if base.count(NAV_ANCHOR)!=1 or "'landscape.binding_pulse_demo'" in base:
            raise ValueError('Patient Lab navigation anchor is unrecognized or partially installed')
        base=base.replace(NAV_ANCHOR,NAV_HOOK,1)
    elif base.count(NAV_HOOK)!=1: raise ValueError('Duplicate binding pulse navigation')
    if LINK not in overview:
        if overview.count(OVERVIEW_ANCHOR)!=1 or 'data-binding-pulse-link' in overview:
            raise ValueError('Patient Lab overview anchor is unrecognized or partially installed')
        overview=overview.replace(OVERVIEW_ANCHOR,OVERVIEW_ANCHOR+'\n'+LINK,1)
    elif overview.count(LINK)!=1: raise ValueError('Duplicate binding pulse overview link')
    return initializer,base,overview


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
    assets=['intelligence_store/target_binding_kinetics.py','intelligence_store/target_binding_schedule.py','landscape_ui/binding_pulse_pages.py',
            'landscape_ui/templates/landscape_binding_pulse_demo.html','landscape_ui/static/target-binding-pulse.css']
    if any(not (root/item).is_file() for item in assets):
        raise ValueError('Copy the binding pulse assets before running this installer')
    paths=[root/'landscape_ui/__init__.py',root/'landscape_ui/templates/landscape_base.html',
           root/'landscape_ui/templates/landscape_patient_lab_overview.html']
    originals = [p.read_bytes() for p in paths]
    modes = [p.stat().st_mode & 0o777 for p in paths]
    proposed = proposed_sources(*(raw.decode('utf-8') for raw in originals))
    changed = [(p, old, new.encode('utf-8'), mode) for p, old, new, mode in zip(paths, originals, proposed, modes)
               if old != new.encode('utf-8')]
    if not changed:
        return {'status': 'already_installed', 'changed_files': []}
    # Validate all integration hooks before changing any existing file.
    if any(path.read_bytes() != old for path, old, _, _ in changed):
        raise ValueError('Existing files changed during preparation; retry after reviewing them')
    backup = root / 'instance' / ('step82-code-backup-' + uuid.uuid4().hex)
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
