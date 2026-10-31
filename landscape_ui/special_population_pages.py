"""Phase 4.2: special-population evidence summary pages."""
import json

from flask import Response, abort, render_template, request

from intelligence_store.special_populations import SummaryError, available, build


def fmt_value(value):
    """Readable form of a sourced value: [ratio, low, high] -> '1.39 (0.88-2.20)'; dicts as 'key: value' lines."""
    if isinstance(value, list) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value):
        return f'{value[0]:.2f} (90% CI {value[1]:.2f}–{value[2]:.2f})'
    if isinstance(value, list) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
        return f'{value[0]:g}–{value[1]:g}'
    if isinstance(value, dict):
        return '; '.join(f'{k.replace("_", " ")}: {fmt_value(v)}' for k, v in value.items())
    if isinstance(value, float):
        return f'{value:g}'
    return str(value)


def register_special_population_pages(bp):
    @bp.get('/drugs/<drug>/special-populations')
    def special_populations(drug):
        if set(request.args) - {'format'} or request.args.get('format', 'html') not in ('html', 'json'):
            abort(400)
        if drug not in available():
            abort(404)
        try:
            view = build(drug)
        except SummaryError as exc:
            return Response(render_template('landscape_message.html', message=str(exc)), status=503,
                            headers={'Cache-Control': 'no-store'})
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if request.args.get('format') == 'json':
            headers['Content-Disposition'] = f'attachment; filename="{drug}-special-populations.json"'
            return Response(json.dumps(view, indent=2, ensure_ascii=False) + '\n', mimetype='application/json', headers=headers)
        return Response(render_template('landscape_special_populations.html', v=view, fmt=fmt_value), headers=headers)
