"""Fixed, source-bound historical study reference; no patient or model access."""
import hashlib
import json
from io import BytesIO
from pathlib import Path
from flask import Response, abort, render_template, request, send_file

DATA = Path(__file__).resolve().parent / 'data' / 'renal_pk'
PINS = {
    'renal_pk_group_evidence_v1.json': 'bb5a71f3a989ddfbf6ef1c6e855a18468f38888cdd3d6cc5835fe8bf6b1bed89',
    'ema_lenalidomide_2008.pdf': 'c27c16b42062171d3146273e33abd2360dc630cd8f8f513b835010c6842b2661',
}


def load_reference():
    raw = {name: (DATA / name).read_bytes() for name in PINS}
    if any(hashlib.sha256(raw[name]).hexdigest() != pin for name, pin in PINS.items()):
        raise ValueError('Bundled evidence integrity mismatch')
    evidence = json.loads(raw['renal_pk_group_evidence_v1.json'])
    baseline = evidence['groups'][0]['measurements']['auc_infinity']['mean']
    ratios = {g['group']: g['measurements']['auc_infinity']['mean']/baseline
              for g in evidence['groups']}
    return evidence, ratios, raw['ema_lenalidomide_2008.pdf']


def register_renal_pk_evidence_pages(bp):
    @bp.get('/patient-lab/published-renal-pk')
    def renal_pk_evidence():
        if set(request.args) - {'format'} or len(request.args.getlist('format')) > 1:
            abort(400)
        output = request.args.get('format', 'html')
        if output not in ('html', 'json', 'pdf'):
            abort(400)
        try:
            evidence, ratios, pdf = load_reference()
        except (OSError, ValueError, KeyError, TypeError):
            return Response('Published evidence unavailable: bundled source or extraction failed integrity checks.',
                            status=503, mimetype='text/plain', headers={'Cache-Control':'no-store'})
        if output == 'pdf':
            response = send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True,
                                 download_name='EMA-lenalidomide-2008.pdf')
        elif output == 'json':
            payload = {'evidence': evidence, 'evidence_sha256': PINS['renal_pk_group_evidence_v1.json'],
                       'derived_auc_mean_ratios': ratios,
                       'ratio_definition': 'Ratio of reported arithmetic group means; no uncertainty interval calculated.',
                       'individual_model_comparison_performed': False,
                       'clinical_prediction_validated': False, 'ready_for_patient_simulation': False}
            response = Response(json.dumps(payload, indent=2, allow_nan=False)+'\n', mimetype='application/json')
            response.headers['Content-Disposition'] = 'attachment; filename="published-renal-pk.json"'
        else:
            response = Response(render_template('landscape_renal_pk_evidence.html', evidence=evidence,
                                ratios=ratios, evidence_sha=PINS['renal_pk_group_evidence_v1.json']))
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
