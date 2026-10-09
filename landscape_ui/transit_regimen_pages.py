"""Fixed repeated-dose teaching page; no patient or evidence access."""
import json
from flask import Response, abort, render_template, request
from intelligence_store.transit_regimen import transit_regimen_demo
from .transit_pages import _chart


def register_transit_regimen_pages(bp):
    @bp.get('/patient-lab/transit-regimen-demo')
    def transit_regimen_example():
        if set(request.args) - {'format', 'cohort_id'}:
            abort(400)
        if any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400)
        cohort = request.args.get('cohort_id')
        if cohort is not None and (not cohort.isascii() or not cohort.isdecimal()
                                  or not 1 <= len(cohort) <= 10 or int(cohort) <= 0):
            abort(400)
        output = request.args.get('format', 'html')
        if output not in ('html', 'json'):
            abort(400)
        report = transit_regimen_demo()
        if output == 'json':
            return Response(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n',
                mimetype='application/json', headers={
                    'Content-Disposition': 'attachment; filename="generic-transit-regimen-demo.json"',
                    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
        points = report['points']; single = report['single_dose_reference_points']
        times = [p['time_h'] for p in points]
        def comparison(key):
            return [{'label': 'Three additions (0, 8, 16 h)', 'color': '#007b83', 'dash': '',
                     'values': [p[key] for p in points]},
                    {'label': 'One addition (0 h)', 'color': '#8b5b92', 'dash': '6 3',
                     'values': [p[key] for p in single]}]
        # Include the pre-event state at the SAME time as the after-event state
        # so jumps are vertical rather than an invented ramp between grid times.
        before = {e['time_h']: e['before'] for e in report['event_boundaries']}
        amount_points = []
        for p in points:
            if p['time_h'] in before:
                amount_points.append(before[p['time_h']])
            amount_points.append(p)
        amount_times = [p['time_h'] for p in amount_points]
        amounts = [
            {'label': 'Transit total', 'color': '#5964a0', 'dash': '',
             'values': [sum(p['transit_amounts_mg']) for p in amount_points]},
            {'label': 'Central', 'color': '#007b83', 'dash': '2 3',
             'values': [p['central_amount_mg'] for p in amount_points]},
            {'label': 'Eliminated', 'color': '#2d643f', 'dash': '8 3',
             'values': [p['eliminated_amount_mg'] for p in amount_points]},
            {'label': 'Cumulative administered', 'color': '#a26735', 'dash': '6 3',
             'values': [p['cumulative_administered_mg'] for p in amount_points]}]
        charts = [_chart('Concentration: one versus three additions', 'ng/mL', times,
                         comparison('concentration_ng_ml')),
                  _chart('Amounts and additions', 'mg', amount_times, amounts),
                  _chart('Cumulative exposure comparison', 'ng·h/mL', times,
                         comparison('auc_0_t_ng_h_ml'))]
        return Response(render_template('landscape_transit_regimen_demo.html',
                        report=report, charts=charts), headers={'Cache-Control': 'no-store',
                                                               'X-Content-Type-Options': 'nosniff'})
