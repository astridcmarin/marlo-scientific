"""Phase 4.4: the lenalidomide guided path page."""
import json

from flask import Response, abort, render_template, request, url_for

from intelligence_store.guided_path import lenalidomide_path


def register_guided_path_pages(bp):
    @bp.get('/drugs/lenalidomide/guide')
    def lenalidomide_guide():
        if set(request.args) - {'format'} or request.args.get('format', 'html') not in ('html', 'json'):
            abort(400)
        try:
            path = lenalidomide_path()
        except ValueError as exc:
            return Response(render_template('landscape_message.html', message=str(exc)), status=503,
                            headers={'Cache-Control': 'no-store'})
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if request.args.get('format') == 'json':
            headers['Content-Disposition'] = 'attachment; filename="lenalidomide-guided-path.json"'
            return Response(json.dumps(path, indent=2, ensure_ascii=False) + '\n', mimetype='application/json', headers=headers)
        for step in path['steps']:
            step['hrefs'] = [(label, url_for(endpoint, **kw)) for label, endpoint, kw in step['links']]
        return Response(render_template('landscape_guided_path.html', p=path), headers=headers)
