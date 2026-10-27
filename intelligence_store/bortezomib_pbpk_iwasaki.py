"""Simulation 3.0j: transcription of the Iwasaki 2020 bortezomib PBPK model (equations 1-6, Table 2).

This module holds the model's right-hand side only: the six differential equations as transcribed in
bortezomib_pbpk_iwasaki_2020_extract_v1.json, with the parameters of Table 2. It does not dose or simulate, and
nothing here is compared with clinical data; that needs a locked check plan first (as for Kuan 2012 and the
falling-clearance forms). The structural checks below test the transcription itself: the binding and flow terms
must cancel in a mass balance, so the only loss of drug is hepatic metabolism.

Units: concentrations in ng/mL, volumes in L/kg, flows in L/h/kg, time in h; amounts are therefore ug/kg.
"""
from pathlib import Path

from .covariate_estimation import _load_pinned

DATA = Path(__file__).parent / 'data'
EXTRACT_PATH = DATA / 'bortezomib_pbpk_iwasaki_2020_extract_v1.json'
EXTRACT_SHA256 = '9bfb9ac21012b2910f59c451d1e802a9282401469875241bd96126fae24b745c'
STATE = ('Cp', 'Crbc', 'Cperi', 'Chp', 'Chrbc', 'Ch')
VOLUME_OF = {'Cp': 'Vsys', 'Crbc': 'Vrbc', 'Cperi': 'Vperi', 'Chp': 'Vhp', 'Chrbc': 'Vhrbc', 'Ch': 'Vh'}
FM = ('fm_1A2', 'fm_2C9', 'fm_2C19', 'fm_2D6', 'fm_3A4')


def load_extract(path=EXTRACT_PATH):
    return _load_pinned(path, EXTRACT_SHA256, 'published-model-extract-v1', 'Iwasaki 2020 bortezomib PBPK extract')


def parameters(extract=None):
    return {name: entry['value'] for name, entry in (extract or load_extract())['parameters'].items()}


def _binding(p, conc_bound, volume, conc_plasma):
    """Net association minus dissociation (ng/mL x L/kg per h) for one RBC pool, as in equations 1, 2, 4 and 5."""
    free_sites = p['Bmax'] * volume - volume * conc_bound / p['MW'] * 1000.0
    return p['Kon'] * free_sites * p['fu_p'] * conc_plasma - p['Koff'] * volume * conc_bound


def metabolic_rate(state, p):
    """Hepatic metabolism, the model's only elimination (ug/kg per h): the last term of equation 6."""
    return p['fu_liver'] * sum(p[f] for f in FM) * p['CLint'] * state['Ch']


def derivatives(state, p):
    """dC/dt (ng/mL per h) for the six compartments; equations 1-6 divided by their volumes."""
    cp, crbc, cperi, chp, chrbc, ch = (state[s] for s in STATE)
    qp, qr = p['Qh'] * (1.0 - p['Hct']), p['Qh'] * p['Hct']
    bind_sys = _binding(p, crbc, p['Vrbc'], cp)
    bind_hep = _binding(p, chrbc, p['Vhrbc'], chp)
    flux = {
        'Cp': -qp * cp + qp * chp - p['CLperi'] * cp + p['CLperi'] * cperi - bind_sys,
        'Crbc': -qr * crbc + qr * chrbc + bind_sys,
        'Cperi': p['CLperi'] * cp - p['CLperi'] * cperi,
        'Chp': qp * cp - qp * chp - p['PSliv'] * p['fu_p'] * chp + p['PSliv'] * p['fu_liver'] * ch - bind_hep,
        'Chrbc': qr * crbc - qr * chrbc + bind_hep,
        'Ch': p['PSliv'] * p['fu_p'] * chp - p['PSliv'] * p['fu_liver'] * ch - metabolic_rate(state, p),
    }
    return {s: flux[s] / p[VOLUME_OF[s]] for s in STATE}


def amount_ug_kg(state, p):
    """Total drug in the body (ng/mL x L/kg = ug/kg)."""
    return sum(state[s] * p[VOLUME_OF[s]] for s in STATE)


def blood_concentration(state, p):
    """Equation 7: systemic whole-blood concentration (ng/mL)."""
    return state['Cp'] * (1.0 - p['Hct']) + state['Crbc'] * p['Hct']


def structural_summary(p=None):
    """Quantities that follow from the transcription alone (no dosing, no data)."""
    p = p or parameters()
    fm_total = sum(p[f] for f in FM)
    return {
        'fm_total': fm_total,
        'hepatic_plasma_fraction': p['Vhp'] / (p['Vhp'] + p['Vhrbc']),
        'kd_nM': p['Koff'] / p['Kon'],
        'rbc_capacity_nmol_kg': p['Bmax'] * p['Vrbc'],
        'rbc_capacity_ug_kg': p['Bmax'] * p['Vrbc'] * p['MW'] / 1000.0,
        'liver_to_hepatic_plasma_ratio_at_equilibrium_without_metabolism': p['fu_p'] / p['fu_liver'],
        'vsys_vs_physiological_plasma_note': 'Vsys is an allometrically scaled apparent volume, not plasma volume.',
    }
