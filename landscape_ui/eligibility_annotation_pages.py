"""Phase 4.1c: annotation page for the eligibility validation sample (one trial at a time; saves after each)."""
from pathlib import Path

from flask import abort, current_app, redirect, request, url_for

from intelligence_store import eligibility_annotations as ea
from .workspace_pages import COOKIE, TTL, _form_token, _response, _validate_token

COOKIE_PATH = '/landscape/benchmarking'


def _store_path():
    return Path(current_app.config.get('ELIGIBILITY_ANNOTATIONS_PATH') or Path(current_app.instance_path) / 'eligibility_annotations_v1.json')


def _with_token(template, status=200, **context):
    nonce, token = _form_token()
    response = _response(template, form_token=token, **context)
    response.status_code = status
    response.set_cookie(COOKIE, nonce, max_age=TTL, httponly=True, secure=request.is_secure, samesite='Strict', path=COOKIE_PATH)
    return response


def register_eligibility_annotation_pages(bp):
    @bp.get('/benchmarking/annotate')
    def eligibility_annotation_overview():
        try:
            trials = ea.sample_trials()
            store = ea.load_store(_store_path())
        except (ValueError, OSError) as exc:
            abort(503, str(exc))
        done = store['annotations']
        rows = [{'position': i + 1, 'nct_id': t['nct_id'], 'saved_at_utc': done.get(t['nct_id'], {}).get('saved_at_utc')}
                for i, t in enumerate(trials)]
        next_row = next((r for r in rows if not r['saved_at_utc']), None)
        return _response('landscape_eligibility_annotation_overview.html', rows=rows, next_row=next_row,
                         done=sum(1 for r in rows if r['saved_at_utc']), total=len(rows), corrections=len(store['corrections']))

    @bp.route('/benchmarking/annotate/<nct_id>', methods=['GET', 'POST'])
    def eligibility_annotation_trial(nct_id):
        try:
            trials = ea.sample_trials()
            store = ea.load_store(_store_path())
        except (ValueError, OSError) as exc:
            abort(503, str(exc))
        position = next((i for i, t in enumerate(trials) if t['nct_id'] == nct_id), None)
        if position is None:
            abort(404)
        trial = trials[position]
        saved = store['annotations'].get(nct_id)
        context = dict(trial=trial, position=position + 1, total=len(trials), types=ea.TYPES, statuses=ea.STATUSES,
                       comparators=ea.COMPARATORS, sections=ea.SECTIONS, max_values=ea.MAX_VALUES, saved=saved)
        if request.method == 'POST':
            if request.content_length and request.content_length > 200_000:
                abort(413)
            _validate_token()
            form = request.form
            try:
                annotation = ea.parse_form(form, trial['criteria_text'])
                ea.save_annotation(_store_path(), nct_id, annotation, form.get('correction_reason'))
            except ValueError as exc:
                errors = exc.args[0] if exc.args and isinstance(exc.args[0], list) else [str(exc)]
                return _with_token('landscape_eligibility_annotation.html', status=400, errors=errors, form=form, **context)
            following = next((t['nct_id'] for t in trials[position + 1:] if t['nct_id'] not in ea.load_store(_store_path())['annotations']), None)
            return redirect(url_for('landscape.eligibility_annotation_trial', nct_id=following) if following
                            else url_for('landscape.eligibility_annotation_overview'), code=303)
        return _with_token('landscape_eligibility_annotation.html', errors=[], form=_form_from_saved(saved), **context)


def _form_from_saved(saved):
    """Prefill the form from a saved annotation, so a correction starts from what was recorded."""
    if not saved:
        return {}
    form = {}
    for key, entry in saved['criteria'].items():
        form[f'{key}__status'] = entry['status']
        form[f'{key}__note'] = entry.get('note', '')
        if 'equation' in entry:
            form[f'{key}__equation'] = entry['equation']
        for i, value in enumerate(entry['values'], start=1):
            for field, text in value.items():
                form[f'{key}__v{i}__{field}'] = text
    return form
