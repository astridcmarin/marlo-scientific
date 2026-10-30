"""Phase 2.5: typical ixazomib exposure for a synthetic patient, inside the model's declared scope only.

The Gupta 2017 model (ixazomib_pk_gupta.py) is used only where ixazomib_scope_v1.json allows: MM, oral 1.5-4 mg,
creatinine clearance 30-297 mL/min, total bilirubin <= 1.5 x ULN, BSA 1.23-2.67 m2, age 23-91. Only total AUC is
computed; peak concentrations and curves are not. Outside the scope no model value is computed; where a dedicated
study observed the patient's group (severe renal impairment/ESRD, moderate/severe hepatic impairment), the observed
group values are shown instead, labelled as observations from other patients.
"""
import hashlib
import json
from pathlib import Path

import click

from . import ixazomib_pk_gupta as model
from .model_scope import bsa_du_bois, evaluate, load_scope
from .patient_state import digest, validate_patient_state

SCHEMA_VERSION = 'ixazomib-exposure-result-v1'
METHOD_VERSION = 'ixazomib-exposure-v1.0'
SCOPE_PATH = Path(__file__).parent / 'data' / 'ixazomib_scope_v1.json'
SCOPE_SHA256 = '8e6598e5830f931d4636e372bf0b5448e7351cc7fa67668ea4c79f0fbd8760f0'
OBSERVED_PATH = Path(__file__).parent / 'data' / 'ixazomib_impairment_observed_v1.json'
OBSERVED_SHA256 = '95fbf4c6f1269c7d77c44e08bb00b4b58095fc1ee8b8b5c0dd4ae2d640153f14'


def load_ixazomib_scope():
    return load_scope(SCOPE_PATH, SCOPE_SHA256)


def _observed_groups(spec):
    raw = OBSERVED_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != OBSERVED_SHA256:
        raise ValueError('Observed ixazomib data are missing or changed.')
    study = json.loads(raw)['studies'][spec['study']]
    groups = study['table2']['groups']
    ref = groups[spec['reference_group']]
    rows = []
    for g in spec['groups']:
        row = groups[g]
        dose = row.get('dose_mg', 3.0)
        ref_dose = ref.get('dose_mg', 3.0)
        rows.append({'group': g, 'definition': study['design']['groups'][g], 'dose_mg': dose,
                     'auc_0_last_gm_ng_h_ml': row['auc_last_ng_h_ml']['gm'], 'auc_cv_percent': row['auc_last_ng_h_ml']['cv_percent'],
                     'auc_n': row['auc_last_ng_h_ml']['n'],
                     'ratio_to_reference_dose_normalised': (row['auc_last_ng_h_ml']['gm'] / dose) / (ref['auc_last_ng_h_ml']['gm'] / ref_dose)})
    return {'kind': 'observed_group_values_from_other_patients', 'study': spec['study'], 'citation': study['citation'],
            'population': study['design']['population'], 'reference_group': spec['reference_group'],
            'reference_definition': study['design']['groups'][spec['reference_group']], 'groups': rows,
            'not_this': 'Geometric means of small groups of other patients after a single dose; not a prediction for this record.'}


def ixazomib_exposure(state, request):
    """state: a synthetic patient state (v1 or v2 schema). request: disease_code, route, dose_mg and, when total
    bilirubin is known, bilirubin_uln_umol_l (the laboratory's upper limit of normal)."""
    state = validate_patient_state(state)
    scope = load_ixazomib_scope()
    ev = evaluate(scope, state, request)
    result = {'schema_version': SCHEMA_VERSION, 'method_version': METHOD_VERSION, 'model_version': model.MODEL_VERSION,
              'scope_sha256': SCOPE_SHA256, 'model_extract_sha256': model.EXTRACT_SHA256,
              'state_sha256': digest(state), 'request': dict(request), 'scope_evaluation': ev, 'model_outputs': None,
              'observed_instead': [], 'clinical_prediction_validated': False}
    if ev['status'] == 'in_scope':
        f = state['fields']
        bsa = bsa_du_bois(f['weight']['value'], f['height']['value'])
        p = model.typical_parameters(model.load_extract(), bsa)
        dose = request['dose_mg']
        tiers = {o['id']: o['tier'] for o in ev['outputs_supported']}
        result['model_outputs'] = {
            'kind': 'typical_value',
            'bsa_m2_du_bois': bsa,
            'typical_total_auc_single_dose_0_336h': {'value': model.auc_to(336.0, dose, p), 'unit': 'h.ng/mL',
                                                     'tier': tiers['typical_total_auc_single_dose_0_336h']},
            'typical_total_auc_tau_steady_state': {'value': model.auc_infinity(dose, p), 'unit': 'h.ng/mL',
                                                   'tier': tiers['typical_total_auc_tau_steady_state'],
                                                   'note': 'Equals F x dose / CL for any dosing interval (linear model).'},
            'typical_parameters': {k: p[k] for k in ('cl', 'f', 'v4')},
            'weakest_rule_tier': ev['weakest_rule_tier'],
            'not_this': 'The exposure the published model gives a typical patient with this body size; not this patient\'s exposure.'}
    else:
        for rule in ev['rules']:
            if 'observed' in rule:
                result['observed_instead'].append(dict(_observed_groups(rule['observed']), triggered_by=rule['id']))
    result['result_sha256'] = digest(result)
    return result


def register_ixazomib_exposure_commands(app):
    @app.cli.command('ixazomib-exposure')
    @click.option('--state-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
    @click.option('--request-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
    def command(state_file, request_file):
        """Typical ixazomib total AUC for a synthetic state, inside the declared model scope only (Phase 2.5)."""
        try:
            result = ixazomib_exposure(json.loads(state_file.read_text()), json.loads(request_file.read_text()))
        except (ValueError, OSError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(result, indent=1, ensure_ascii=False, allow_nan=False))
