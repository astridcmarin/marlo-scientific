"""Phase 2.5: enforceable model scope (the ICH M15 context of use, as rules the platform applies).

A scope file (schema model-scope-v1, pinned by the module that uses it) lists:
- the outputs the platform will compute for the model, each with an evidence tier, and the outputs it will not;
- request rules (disease, route, dose) and patient-state rules (ranges, ratios to a laboratory reference), each
  citing the pinned source or locked report that justifies it, with the reason shown when a request falls outside.

`evaluate` applies the rules to a synthetic patient state and a request. It returns, rule by rule, in_scope,
out_of_scope or cannot_determine (input unknown), and an overall status:
- in_scope: every rule in scope; the supported outputs may be computed;
- out_of_scope: at least one rule out of scope; no model output is computed;
- cannot_determine: no rule out of scope but at least one unknown; no model output is computed.
The overall evidence tier of an in-scope request is the weakest tier among its rules. The weakest tier,
external_check_disagrees, is still in scope: the model was fitted on such patients but a locked outside check found
it inconsistent there, so the output is computed, flagged and shown with the observed data the band names.
Rules may read covariates derived by the model's own estimator (passed as `derived`); an `optional` rule whose input
is unknown is reported as not_assessed and does not block. Nothing is converted or
assumed: a unit that differs from the rule's is an error, and an unknown value stays unknown.
"""
import hashlib
import json
import math
from pathlib import Path

SCHEMA_VERSION = 'model-scope-v1'
EVALUATION_VERSION = 'model-scope-evaluation-v1.0'
TIER_ORDER = ('externally_checked', 'inside_model_data', 'external_check_disagrees')


class ScopeError(ValueError):
    pass


def load_scope(path, expected_sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ScopeError('Model scope file is missing or changed; nothing was evaluated.')
    data = json.loads(raw)
    if data.get('schema_version') != SCHEMA_VERSION:
        raise ScopeError('Unsupported model scope schema.')
    return data


def bsa_du_bois(weight_kg, height_cm):
    """Du Bois and Du Bois (1916): BSA (m2) = 0.007184 x W^0.425 x H^0.725."""
    return 0.007184 * weight_kg ** 0.425 * height_cm ** 0.725


DERIVED = {'bsa_du_bois': (('weight', 'kg'), ('height', 'cm'), bsa_du_bois)}


def _field(state, name, unit):
    field = state['fields'].get(name)
    if field is None or field.get('value') is None:
        return None
    if field.get('unit') != unit:
        raise ScopeError(f'{name}: unit {field.get("unit")!r} differs from the scope unit {unit!r}; no conversion is performed.')
    return field['value']


def _derived(state, name):
    (a, ua), (b, ub), fn = DERIVED[name]
    x, y = _field(state, a, ua), _field(state, b, ub)
    return None if x is None or y is None else fn(x, y)


def _reason(rule, key):
    reasons = rule.get('outside_reason', {})
    return reasons.get(key) or reasons.get('default')


def _range_rule(rule, value):
    lo, hi = rule['range']
    if value is None:
        if rule.get('optional'):
            return {'status': 'not_assessed', 'value': None, 'reason': 'Input unknown; this rule is optional.'}
        return {'status': 'cannot_determine', 'value': None, 'reason': 'Input unknown.'}
    if value < lo:
        return {'status': 'out_of_scope', 'value': value, 'side': 'below', 'reason': _reason(rule, 'below')}
    if value > hi:
        return {'status': 'out_of_scope', 'value': value, 'side': 'above', 'reason': _reason(rule, 'above')}
    row = {'status': 'in_scope', 'value': value, 'tier': rule.get('tier')}
    for band in rule.get('tier_by_band', []):
        if band['range'][0] <= value <= band['range'][1]:
            row['tier'] = band['tier']
            for key in ('band_note', 'observed'):
                if key in band:
                    row[key] = band[key]
            break
    return row


def evaluate_rule(rule, state, request, derived=None):
    kind = rule['kind']
    row = {'id': rule['id'], 'kind': kind}
    if kind == 'category':
        value = request.get(rule['input'])
        if value is None or value == 'UNKNOWN':
            row.update(status='cannot_determine', value=value, reason=_reason(rule, 'UNKNOWN') or 'Input unknown.')
        elif value in rule['in_scope']:
            row.update(status='in_scope', value=value, tier=rule.get('tier_by_value', {}).get(value, rule.get('tier')))
        else:
            row.update(status='out_of_scope', value=value, reason=_reason(rule, value))
    elif kind == 'range':
        if 'input' in rule:
            value = request.get(rule['input'])
        elif 'derived_input' in rule:
            value = (derived or {}).get(rule['derived_input'])
        elif 'derived' in rule:
            value = _derived(state, rule['derived'])
        else:
            value = _field(state, rule['field'], rule['unit'])
        row.update(_range_rule(rule, value), unit=rule['unit'])
    elif kind == 'ratio_max':
        value = _field(state, rule['field'], rule['unit'])
        reference = request.get(rule['reference_input'])
        if value is None or reference is None:
            row.update(status='cannot_determine', value=value, reference=reference,
                       reason='Input or laboratory reference value unknown.')
        else:
            if not (isinstance(reference, (int, float)) and reference > 0 and math.isfinite(reference)):
                raise ScopeError(f'{rule["reference_input"]} must be a positive number.')
            ratio = value / reference
            inside = ratio <= rule['max_ratio']
            row.update(status='in_scope' if inside else 'out_of_scope', value=value, reference=reference, ratio=ratio,
                       unit=rule['unit'], **({'tier': rule['tier']} if inside else {'side': 'above', 'reason': _reason(rule, 'above')}))
    else:
        raise ScopeError(f'Unknown rule kind {kind!r}.')
    for key in ('basis', 'assumption'):
        if key in rule:
            row[key] = rule[key]
    for key in ('observed_when_below', 'observed_when_above'):
        if key in rule and row.get('side') == key.rsplit('_', 1)[1]:
            row['observed'] = rule[key]
    return row


def evaluate(scope, state, request, derived=None):
    rows = [evaluate_rule(r, state, request, derived) for r in scope['request_rules'] + scope['state_rules']]
    statuses = {r['status'] for r in rows}
    status = ('out_of_scope' if 'out_of_scope' in statuses else 'cannot_determine' if 'cannot_determine' in statuses
              else 'in_scope')
    result = {'evaluation_version': EVALUATION_VERSION, 'scope_version': scope['scope_version'], 'model_id': scope['model_id'],
              'status': status, 'rules': rows, 'outputs_not_supported': scope['outputs']['not_supported'],
              'never_claimed': scope['never_claimed'], 'clinical_prediction_validated': False}
    if status == 'in_scope':
        result['weakest_rule_tier'] = max((r['tier'] for r in rows if r['status'] == 'in_scope'), key=TIER_ORDER.index)
        result['outputs_supported'] = scope['outputs']['supported']
        result['flags'] = [r['id'] for r in rows if r.get('tier') == 'external_check_disagrees']
    return result
