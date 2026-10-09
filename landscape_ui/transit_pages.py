"""Read-only, fixed invented solver example; independent of evidence storage."""
import json
from flask import Response, abort, render_template, request
from intelligence_store.transit_kernel import transit_demo


def _chart(title, unit, times, series):
    """SVG display coordinates only; source values remain in the report/table."""
    maximum = max(max(s['values']) for s in series) or 1.0
    top = maximum * 1.1
    for row in series:
        row['polyline'] = ' '.join(
            f'{70 + 670*t/times[-1]:.3f},{250 - 220*v/top:.3f}'
            for t, v in zip(times, row['values']))
    return {'title': title, 'unit': unit, 'series': series,
            'ticks': [{'y': 250-220*i/4, 'label': f'{top*i/4:.3g}'} for i in range(5)],
            'time_ticks': [{'x': 70+670*t/times[-1], 'label': f'{t:g}'} for t in (0, 6, 12, 18, 24)]}


def register_transit_pages(bp):
    @bp.get('/patient-lab/transit-demo')
    def transit_example():
        # Cohort ID is navigation context only, never an input to this model.
        if set(request.args) - {'format', 'cohort_id'}:
            abort(400)
        if any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        cohort_id = request.args.get('cohort_id')
        if cohort_id is not None and (not cohort_id.isascii() or not cohort_id.isdecimal()
                                     or not 1 <= len(cohort_id) <= 10 or int(cohort_id) <= 0):
            abort(400)
        output = request.args.get('format', 'html')
        if output not in ('html', 'json'):
            abort(400)
        report = transit_demo()
        if output == 'json':
            return Response(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n',
                mimetype='application/json', headers={
                    'Content-Disposition': 'attachment; filename="generic-transit-demo.json"',
                    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
        points = report['points']; times = [p['time_h'] for p in points]
        amounts = [{'label': f'Transit stage {i+1}', 'color': color,
                    'values': [p['transit_amounts_mg'][i] for p in points], 'dash': dash}
                   for i, (color, dash) in enumerate((('#5964a0',''),('#8b5b92','6 3'),('#a26735','2 3')))]
        amounts += [{'label': 'Central', 'color': '#007b83', 'dash': '',
                     'values': [p['central_amount_mg'] for p in points]},
                    {'label': 'Eliminated', 'color': '#2d643f', 'dash': '8 3',
                     'values': [p['eliminated_amount_mg'] for p in points]}]
        charts = [
            _chart('Central concentration', 'ng/mL', times, [
                {'label': 'Central concentration', 'color': '#007b83', 'dash': '',
                 'values': [p['concentration_ng_ml'] for p in points]}]),
            _chart('Where the amount is', 'mg', times, amounts),
            _chart('Cumulative exposure', 'ng·h/mL', times, [
                {'label': 'AUC from zero to time t', 'color': '#007b83', 'dash': '',
                 'values': [p['auc_0_t_ng_h_ml'] for p in points]}])]
        return Response(render_template('landscape_transit_demo.html', report=report,
                        charts=charts), headers={'Cache-Control': 'no-store',
                                                'X-Content-Type-Options': 'nosniff'})
