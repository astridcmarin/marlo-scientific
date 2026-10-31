"""Phase 4.3: the lenalidomide dose-optimisation page (docs/DOSE_OPTIMISATION.md)."""
import json
import math

from flask import Response, abort, render_template, request

from intelligence_store.dose_optimisation import DOSE_STATUS, lenalidomide_dose_view
from intelligence_store.lenalidomide_relative_odds import ENDPOINTS
from intelligence_store.patient_state import example_state

NUMERIC = {'age': ('age_years', 'year'), 'weight': ('weight', 'kg'), 'height': ('height', 'cm'),
           'scr': ('serum_creatinine', 'umol/L')}
SEXES = {'FEMALE': 'Female', 'MALE': 'Male', '': 'Unknown'}
DISEASES = {'MM': 'Multiple myeloma', 'CLL': 'Chronic lymphocytic leukaemia', 'AML': 'Acute myeloid leukaemia',
            'ALL': 'Acute lymphoblastic leukaemia', 'OTHER': 'Other', 'UNKNOWN': 'Not declared'}
ALLOWED = set(NUMERIC) | {'sex', 'disease', 'format'}
DEFAULTS = {'age': '65', 'sex': 'FEMALE', 'weight': '70', 'height': '165', 'scr': '80', 'disease': 'MM'}
ENDPOINT_LABELS = {'grade_3_4_thrombocytopenia': 'Grade 3/4 thrombocytopenia', 'grade_3_4_neutropenia': 'Grade 3/4 neutropenia'}


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


def build_state(args):
    state = example_state()
    for name in state['fields']:
        state['fields'][name].update(value=None, origin='unknown')
    for key, (field, unit) in NUMERIC.items():
        value = _number(args.get(key))
        if value is not None:
            state['fields'][field].update(value=value, unit=unit, origin='synthetic_input')
    sex = args.get('sex', '')
    if sex not in SEXES:
        abort(400)
    if sex:
        state['fields']['biological_sex'].update(value=sex, origin='synthetic_input')
    disease = args.get('disease', 'UNKNOWN')
    if disease not in DISEASES:
        abort(400)
    return state, disease


def register_dose_optimisation_pages(bp):
    @bp.get('/drugs/lenalidomide/dose-optimisation')
    def lenalidomide_dose_optimisation():
        if set(request.args) - ALLOWED or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        if fmt not in ('html', 'json'):
            abort(400)
        submitted = bool(set(request.args) - {'format'})
        args = request.args if submitted else DEFAULTS
        state, disease = build_state(args)
        try:
            result = lenalidomide_dose_view(state, disease)
        except ValueError as exc:
            return Response(render_template('landscape_message.html', message=str(exc)), status=503,
                            headers={'Cache-Control': 'no-store'})
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if fmt == 'json':
            headers['Content-Disposition'] = 'attachment; filename="lenalidomide-dose-view.json"'
            return Response(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
                            mimetype='application/json', headers=headers)
        form = {k: args.get(k, '') for k in DEFAULTS}
        return Response(render_template('landscape_dose_optimisation.html', r=result, form=form, diseases=DISEASES,
                                        sexes=SEXES, dose_status=DOSE_STATUS, endpoints=ENDPOINTS,
                                        endpoint_labels=ENDPOINT_LABELS), headers=headers)
