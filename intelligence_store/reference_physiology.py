"""Digital human 1.1, step 1.1a: pinned reference physiology and lenalidomide's blood-to-plasma distribution.

- ICRP Publication 89 (2002): the reference adult male's cardiac output, the kidneys' share of it and the red-cell
  fraction of blood, copied from its tables with page numbers. Reference physiology for a reference man, not a
  patient value, and not adjusted for kidney function (the owner's decision 1 for Digital human 1.1).
- Chen et al. 2012: whole-blood to plasma exposure ratio of [14C]-lenalidomide radioactivity (0.931), used as the
  blood-to-plasma ratio with the status "assumed" and its limits recorded.

Plan: docs/DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md (approved 3 November 2026).
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / 'data'
ICRP_PATH = DATA / 'reference_physiology_icrp89_v1.json'
ICRP_SHA256 = 'd1d6663757a6355164ffbe38dbc433526a3702f70c44eff66a78551b51734195'
# v2 (12 November 2026): the reference woman and man side by side, from the Track H design draft, every quote checked
# against the PDF. The pages still use v1 (men only); v2 is for the organ-level work.
ICRP_V2_PATH = DATA / 'reference_physiology_icrp89_v2.json'
ICRP_V2_SHA256 = '8d699fe0794e1e56671e3536551b44ad7d755b5aa8f8751d55084677ad679338'
CHEN_PATH = DATA / 'lenalidomide_blood_plasma_chen_2012_v1.json'
CHEN_SHA256 = '789986fa01ee5a9f375e71a28e5f03345f00f827d8defb654818ede35c2638cf'


class ReferencePhysiologyError(ValueError):
    pass


def _pinned(path, sha256, label, schema):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ReferencePhysiologyError(f'{label} is missing or changed.')
    data = json.loads(raw)
    if data.get('schema_version') != schema:
        raise ReferencePhysiologyError(f'Unsupported {label} schema.')
    return data


def load_reference_physiology(path=ICRP_PATH):
    return _pinned(path, ICRP_SHA256, 'ICRP 89 reference physiology extract', 'reference-physiology-v1')


def load_reference_physiology_v2(path=ICRP_V2_PATH):
    return _pinned(path, ICRP_V2_SHA256, 'ICRP 89 reference physiology extract v2', 'reference-physiology-v2')


def load_blood_plasma(path=CHEN_PATH):
    return _pinned(path, CHEN_SHA256, 'Lenalidomide blood-to-plasma extract', 'blood-plasma-distribution-v1')


def renal_flows():
    """Reference renal blood and plasma flow (both kidneys, mL/min), computed from the pinned values."""
    v = load_reference_physiology()['values']
    blood = 1000 * v['cardiac_output_adult_male']['value'] * v['kidney_blood_flow_fraction_adult_male']['value'] / 100
    plasma = blood * (1 - v['red_cell_fraction_of_blood_adult_male']['value'] / 100)
    return {'renal_blood_flow_ml_min': blood, 'renal_plasma_flow_ml_min': plasma,
            'cardiac_output_l_min': v['cardiac_output_adult_male']['value'],
            'kidney_fraction_pct': v['kidney_blood_flow_fraction_adult_male']['value'],
            'red_cell_fraction_pct': v['red_cell_fraction_of_blood_adult_male']['value']}
