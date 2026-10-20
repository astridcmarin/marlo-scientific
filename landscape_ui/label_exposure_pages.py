"""Phase 3.1e: label-based exposure page (typical value from the product label, checked before it is shown)."""
import json
import math
from flask import Response, abort, render_template, request
from intelligence_store.label_exposure_view import view

X0, X1, Y0, Y1 = 70.0, 740.0, 24.0, 250.0


def _nice_top(values):
    top = max(values) * 1.1
    step = 10 ** math.floor(math.log10(top))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * step >= top:
            return m * step
    return 10 * step


def _chart(times, series, end_h, top, x_tick_every):
    x = lambda t: X0 + (X1 - X0) * t / end_h
    y = lambda c: Y1 - (Y1 - Y0) * c / top
    lines = {name: ' '.join(f'{x(t):.2f},{y(c):.2f}' for t, c in zip(times, values)) for name, values in series.items()}
    y_ticks = [{'y': round(y(top * f), 2), 'label': f'{top * f:g}'} for f in (0, 0.25, 0.5, 0.75, 1.0)]
    x_ticks = [{'x': round(x(t), 2), 'label': f'{t:g}'} for t in range(0, int(end_h) + 1, x_tick_every)]
    return {'lines': lines, 'y_ticks': y_ticks, 'x_ticks': x_ticks, 'x': x, 'y': y}


def charts(v):
    week, day = v['curves']['first_72_h'], v['curves']['steady_state_day']
    top = _nice_top(week['base'] + day['base'] + day['li_2017_typical'] + week.get('scenario', []) + day.get('scenario', [])
                    + [v['label_points']['cmax_ng_ml']])
    first = _chart(week['times_h'], {k: week[k] for k in ('base', 'scenario') if k in week}, 72.0, top, 12)
    steady = _chart(day['times_h'], {k: day[k] for k in ('base', 'li_2017_typical', 'scenario') if k in day}, 24.0, top, 4)
    lp = v['label_points']
    lo, hi = lp['tmax_range_h']
    steady['label_cmax'] = {'x0': round(steady['x'](lo), 2), 'x1': round(steady['x'](hi), 2), 'y': round(steady['y'](lp['cmax_ng_ml']), 2)}
    first['doses'] = [round(first['x'](t), 2) for t in (0, 24, 48)]
    for c in (first, steady):
        del c['x'], c['y']
    return {'first': first, 'steady': steady}


def register_label_exposure_pages(bp):
    @bp.get('/patient-lab/label-exposure/<drug>')
    def label_exposure(drug):
        if set(request.args) - {'scenario', 'format'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        fmt = request.args.get('format', 'html')
        scenario = request.args.get('scenario') or None
        if fmt not in ('html', 'json') or (scenario and len(scenario) > 80):
            abort(400)
        try:
            v = view(drug, scenario)
        except KeyError:
            abort(404 if not scenario else 400)
        except ValueError as exc:
            return Response(render_template('landscape_message.html', message=str(exc)), status=503,
                            headers={'Cache-Control': 'no-store'})
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if fmt == 'json':
            headers['Content-Disposition'] = f'attachment; filename="{drug}-label-exposure{"-" + scenario if scenario else ""}.json"'
            return Response(json.dumps(v, indent=2, ensure_ascii=False, allow_nan=False) + '\n', mimetype='application/json', headers=headers)
        return Response(render_template('landscape_label_exposure.html', v=v, charts=charts(v)), headers=headers)
