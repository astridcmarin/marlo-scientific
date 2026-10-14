"""Simulation 3.0d: typical bortezomib platelet time course (Lignet 2022), both mechanism variants."""
import json
import math
from flask import Response, abort, render_template, request
from intelligence_store.bortezomib_platelets import MAX_CYCLES, platelet_timecourse

X0, X1, Y0, Y1 = 70.0, 740.0, 30.0, 250.0
COLORS = {'myelosuppression': '#007b83', 'platelet_budding': '#b5651d'}
LABELS = {'myelosuppression': 'Myelosuppression variant (drug slows progenitor division)',
          'platelet_budding': 'Platelet-budding variant (drug slows platelet release)'}


def _x(t_h, end_h):
    return X0 + (X1 - X0) * t_h / end_h


def charts(report):
    end = report['times_h'][-1]
    top = max(1.5, math.ceil(max(max(v['fraction_of_baseline']) for v in report['variants'].values()) * 10) / 10)
    y = lambda f: Y1 - (Y1 - Y0) * f / top
    lines = [{'variant': name, 'label': LABELS[name], 'color': COLORS[name],
              'points': ' '.join(f'{_x(t, end):.2f},{y(f):.2f}' for t, f in zip(report['times_h'], v['fraction_of_baseline']))}
             for name, v in report['variants'].items()]
    obs = report['observed_reference']
    platelet = {'lines': lines, 'baseline_y': y(1.0), 'ticks': [{'y': y(f), 'label': f'{round(f * 100)}%'} for f in (0, 0.5, 1.0, 1.5) if f <= top],
                'observed': {'x': _x(240.0, end), 'y': y(obs['cycle1_day11_ratio']), 'lo': y(obs['interval'][0]), 'hi': y(obs['interval'][1])}}
    pk = report['pk']
    ly = lambda c: Y1 - (Y1 - Y0) * (math.log10(c) + 1) / 4  # 0.1 to 1000 ng/mL
    pk_points = ' '.join(f'{_x(t, end):.2f},{ly(min(max(c, 0.1), 1000)):.2f}' for t, c in zip(pk['times_h'], pk['concentration_ng_ml']) if c > 0)
    thresholds = [{'variant': name, 'color': COLORS[name], 'value': v['effect_term_zero_at_ng_ml'], 'y': ly(v['effect_term_zero_at_ng_ml'])}
                  for name, v in report['variants'].items()]
    concentration = {'points': pk_points, 'thresholds': thresholds,
                     'ticks': [{'y': ly(c), 'label': f'{c:g}'} for c in (0.1, 1, 10, 100, 1000)]}
    days = [{'x': _x(24.0 * d, end), 'label': f'{d + 1}'} for d in range(0, int(end / 24) + 1, 7)]
    doses = [_x(t, end) for t in report['regimen']['dose_times_h']]
    return {'platelets': platelet, 'pk': concentration, 'days': days, 'doses': doses}


def register_bortezomib_platelet_pages(bp):
    @bp.get('/simulation-lab/bortezomib-platelets')
    def bortezomib_platelets():
        if set(request.args) - {'cycles', 'format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        raw = request.args.get('cycles', '1')
        if fmt not in ('html', 'json') or raw not in {str(n) for n in range(1, MAX_CYCLES + 1)}:
            abort(400)
        try:
            report = platelet_timecourse(int(raw))
        except (ValueError, OSError, KeyError):
            abort(503, 'Model sources unavailable or altered; calculation withheld.')
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if fmt == 'json':
            headers['Content-Disposition'] = f'attachment; filename="bortezomib-platelets-{raw}-cycles.json"'
            return Response(json.dumps(report, indent=2, allow_nan=False) + '\n', mimetype='application/json', headers=headers)
        return Response(render_template('landscape_bortezomib_platelets.html', report=report, charts=charts(report),
                                        labels=LABELS, colors=COLORS, max_cycles=MAX_CYCLES), headers=headers)
