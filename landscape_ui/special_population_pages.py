"""Phase 4.2: special-population evidence summary pages."""
import json

from flask import Response, abort, render_template, request

from intelligence_store.special_populations import SummaryError, available, build


def fmt_value(value, display=None):
    """Readable form of a sourced value: [ratio, low, high] -> '1.39 (0.88-2.20)'; dicts as 'key: value' lines.
    `display` (from the summary) disambiguates two-number lists: 'mean_sd' -> 'mean (SD)', otherwise a range."""
    numbers = isinstance(value, list) and all(isinstance(v, (int, float)) for v in value)
    if display == 'mean_sd' and numbers and len(value) == 2:
        return f'{value[0]:g} (SD {value[1]:g})'
    if display == 'gm_cv' and numbers and len(value) == 2:
        return f'{value[0]:g} (CV {value[1]:g}%)'
    if display == 'bands' and isinstance(value, list):
        tiers = {'externally_checked': 'checked against outside data', 'inside_model_data': "model's own data only",
                 'external_check_disagrees': 'outside check disagrees'}
        return '; '.join(f'{b["range"][0]:g}–{b["range"][1]:g}: {tiers.get(b["tier"], b["tier"])}' for b in value)
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
