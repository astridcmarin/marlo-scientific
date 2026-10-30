"""Phase 2.5: the ixazomib exposure page, showing a model value only inside the model's declared scope."""
import json
import math

from flask import Response, abort, render_template, request

from intelligence_store.ixazomib_exposure import ixazomib_exposure, load_ixazomib_scope
from intelligence_store.patient_state import example_state

NUMERIC = {'weight': ('weight', 'kg'), 'height': ('height', 'cm'), 'age': ('age_years', 'year'),
           'crcl': ('creatinine_clearance', 'mL/min'), 'bilirubin': ('total_bilirubin', 'umol/L')}
REQUEST_NUMERIC = ('dose', 'bilirubin_uln')
DISEASES = {'MM': 'Multiple myeloma', 'SOLID_TUMOUR': 'Solid tumour', 'OTHER': 'Other', 'UNKNOWN': 'Not declared'}
ALLOWED = set(NUMERIC) | set(REQUEST_NUMERIC) | {'disease', 'format'}
DEFAULTS = {'weight': '70', 'height': '165', 'age': '65', 'crcl': '95', 'bilirubin': '8', 'bilirubin_uln': '21',
            'dose': '4', 'disease': 'MM'}
TIER_LABELS = {'externally_checked': 'Checked against outside data', 'inside_model_data': "Inside the model's own data only"}


def _number(raw):
    if raw is None or raw.strip() == '':
        return None
    try:
        value = float(raw)
    except ValueError:
        abort(400)
    if not math.isfinite(value) or value <= 0 or value > 10000:
        abort(400)
    return value


def build_inputs(args):
    state = example_state()
    for name in state['fields']:
        state['fields'][name].update(value=None, origin='unknown')
    for key, (field, unit) in NUMERIC.items():
        value = _number(args.get(key))
        if value is not None:
            state['fields'][field].update(value=value, unit=unit, origin='synthetic_input')
    disease = args.get('disease', 'UNKNOWN')
    if disease not in DISEASES:
        abort(400)
    req = {'disease_code': disease, 'route': 'oral', 'dose_mg': _number(args.get('dose')),
           'bilirubin_uln_umol_l': _number(args.get('bilirubin_uln'))}
    return state, req


def register_ixazomib_exposure_pages(bp):
    @bp.get('/patient-lab/ixazomib-exposure')
    def ixazomib_exposure_page():
        if set(request.args) - ALLOWED or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        if fmt not in ('html', 'json'):
            abort(400)
        submitted = bool(set(request.args) - {'format'})
        args = request.args if submitted else DEFAULTS
        state, req = build_inputs(args)
        try:
            result = ixazomib_exposure(state, req)
        except ValueError as exc:
            return Response(render_template('landscape_message.html', message=str(exc)), status=503,
                            headers={'Cache-Control': 'no-store'})
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if fmt == 'json':
            headers['Content-Disposition'] = 'attachment; filename="ixazomib-exposure.json"'
            return Response(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
                            mimetype='application/json', headers=headers)
        form = {k: args.get(k, '') for k in DEFAULTS}
        return Response(render_template('landscape_ixazomib_exposure.html', r=result, scope=load_ixazomib_scope(), form=form,
                                        diseases=DISEASES, tiers=TIER_LABELS), headers=headers)
