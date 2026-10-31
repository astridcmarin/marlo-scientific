"""Phase 2.5c: every model scope on the platform, for the public scope pages and record links.

Each entry points at the scope file's own pinned loader, so a page can only show a scope whose checksum matches.
'runtime' says where the platform applies the scope (None when the platform does not compute the model yet).
"""
from pathlib import Path

from .model_scope import load_scope

DATA = Path(__file__).parent / 'data'
DARATUMUMAB_SCOPE_PATH = DATA / 'daratumumab_scope_v1.json'
DARATUMUMAB_SCOPE_SHA256 = '2005d487a42b54659c2af372a964cd8ff691184d2b2ac807474b251d86865d60'


def _ixazomib():
    from .ixazomib_exposure import load_ixazomib_scope
    return load_ixazomib_scope()


def _hughes():
    from .lenalidomide_scope import load_hughes_scope
    return load_hughes_scope()


def _kim():
    from .lenalidomide_scope import load_kim_scope
    return load_kim_scope()


def _daratumumab():
    return load_scope(DARATUMUMAB_SCOPE_PATH, DARATUMUMAB_SCOPE_SHA256)


REGISTRY = {
    'lenalidomide_hughes_2019': {'label': 'Lenalidomide, Hughes 2019 population PK', 'load': _hughes,
                                 'runtime': 'Patient Lab: estimated PK, saved runs, weight-basis comparison, population band, model comparison'},
    'lenalidomide_kim_2026': {'label': 'Lenalidomide, Kim 2026 population PK', 'load': _kim,
                              'runtime': 'Patient Lab: Kim runs and model comparison'},
    'ixazomib_pk_gupta_2017': {'label': 'Ixazomib, Gupta 2017 population PK', 'load': _ixazomib,
                               'runtime': 'Ixazomib exposure page (/landscape/patient-lab/ixazomib-exposure)'},
    'daratumumab_pk_luo_2021': {'label': 'Daratumumab, Luo 2021 population PK', 'load': _daratumumab, 'runtime': None},
}


def scope_for(model_id):
    entry = REGISTRY[model_id]
    return {'model_id': model_id, 'label': entry['label'], 'runtime': entry['runtime'], 'scope': entry['load']()}


def all_scopes():
    return [scope_for(m) for m in REGISTRY]
