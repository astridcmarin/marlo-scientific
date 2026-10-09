"""Explicit saved synthetic scenarios in the local shared Workspace."""
import json
from flask import Response, abort, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.regulatory import digest
from intelligence_store.saved_scenarios import (SavedPatientScenario, scenarios_ready,
    analyze_for_save, read_scenario, save_scenario)
from .workspace_pages import COOKIE, TTL, _form_token, _validate_token, _signer, _response


def _page(template, **context):
    nonce, token = _form_token()
    response = _response(template, form_token=token, **context)
    response.set_cookie(COOKIE, nonce, max_age=TTL, httponly=True,
                        secure=request.is_secure, samesite='Strict', path='/landscape/workspace')
    return response


def _body_limit():
    if request.content_length is None or request.content_length > 32768:
        abort(413)


def _error(exc, status=409):
    return Response(render_template('landscape_message.html', message=str(exc)),
                    status=status, headers={'Cache-Control': 'no-store'})


def register_saved_scenario_pages(bp, parse_profile):
    @bp.get('/workspace/scenarios')
    def saved_scenarios():
        try:
            scenarios_ready()
            page = request.args.get('page', 1, type=int)
            count = db.session.scalar(select(func.count()).select_from(SavedPatientScenario))
            if not page or page < 1 or page > max(1, (count + 19) // 20):
                abort(404)
            rows = list(db.session.scalars(select(SavedPatientScenario).order_by(
                SavedPatientScenario.id.desc()).offset((page - 1) * 20).limit(20)))
            for row in rows:
                read_scenario(row.id)
            return _response('landscape_saved_scenarios.html', scenarios=rows, count=count,
                             page=page, previous_url=url_for('landscape.saved_scenarios', page=page-1) if page>1 else None,
                             next_url=url_for('landscape.saved_scenarios', page=page+1) if page*20<count else None)
        except ValueError as exc:
            return _error(exc)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Saved scenario storage is temporarily unavailable.', 503)

    @bp.post('/workspace/scenarios/prepare')
    def scenario_prepare():
        _body_limit()
        try:
            scenarios_ready()
            cohort_id = request.form.get('cohort_id', type=int)
            analysis = analyze_for_save(cohort_id, parse_profile())
            report = analysis['report']
            ticket = _signer().dumps({'purpose': 'save-synthetic-scenario',
                'cohort_id': cohort_id, 'profile': report['profile'],
                'analysis_sha256': digest(analysis)})
            return _page('landscape_scenario_prepare.html', report=report, ticket=ticket,
                         title=report['selected_drug']['label'] + ' synthetic scenario', error=None)
        except ValueError as exc:
            return _error(exc, 400)
        except (SQLAlchemyError, OSError):
            db.session.rollback()
            return _error('Scenario preparation is temporarily unavailable.', 503)

    @bp.post('/workspace/scenarios/save')
    def scenario_save():
        _body_limit()
        save_key = _validate_token()
        try:
            try:
                ticket = _signer().loads(request.form.get('ticket', ''), max_age=TTL)
            except (BadSignature, SignatureExpired):
                abort(403)
            if not isinstance(ticket, dict) or ticket.get('purpose') != 'save-synthetic-scenario':
                abort(403)
            row = save_scenario(request.form.get('title', ''), ticket['cohort_id'],
                ticket['profile'], ticket['analysis_sha256'], save_key)
            return redirect(url_for('landscape.saved_scenario', scenario_id=row.id), code=303)
        except ValueError as exc:
            return _error(exc)
        except (SQLAlchemyError, OSError):
            db.session.rollback()
            return _error('Scenario save is temporarily unavailable.', 503)

    @bp.get('/workspace/scenarios/compare')
    def scenario_compare():
        from intelligence_store.scenario_comparisons import compare_scenarios
        output = request.args.get('format', 'html')
        if output not in ('html', 'json', 'pdf'):
            abort(400)
        try:
            scenarios_ready()
            comparison = None
            if request.args.get('left') and request.args.get('right'):
                try:
                    left, right = int(request.args.get('left', '')), int(request.args.get('right', ''))
                except ValueError:
                    abort(400)
                comparison = compare_scenarios(left, right)
            elif output in ('json', 'pdf'):
                abort(400)
            if output == 'pdf':
                try:
                    from intelligence_store.scenario_comparison_pdf import render_scenario_comparison_pdf
                except ImportError:
                    return _error('Install the existing ReportLab dependency to download PDFs.', 503)
                response = Response(render_scenario_comparison_pdf(comparison), mimetype='application/pdf')
                response.headers['Content-Disposition'] = f'attachment; filename="scenario_comparison_{left}_{right}.pdf"'
                response.headers['Cache-Control'] = 'no-store'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                return response
            if output == 'json':
                response = Response(json.dumps(comparison, indent=2, ensure_ascii=False, allow_nan=False), mimetype='application/json')
                response.headers['Content-Disposition'] = f'attachment; filename="scenario_comparison_{left}_{right}.json"'
                response.headers['Cache-Control'] = 'no-store'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                return response
            return _response('landscape_scenario_compare.html', comparison=comparison)
        except LookupError as exc:
            return _error(exc, 404)
        except ValueError as exc:
            return _error(exc, 400)
        except OSError:
            return _error('PDF font files are unavailable. Restore intelligence_store/fonts from the patch.', 503)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Saved scenario comparison is temporarily unavailable.', 503)

    @bp.get('/workspace/scenarios/<int:scenario_id>')
    def saved_scenario(scenario_id):
        output = request.args.get('format', 'html')
        if output not in ('html', 'json'):
            abort(400)
        try:
            row = read_scenario(scenario_id)
            if row is None:
                abort(404)
            if output == 'json':
                response = Response(json.dumps({'saved_scenario_id': row.id,
                    'payload_sha256': row.payload_sha256, 'payload': row.payload},
                    indent=2, ensure_ascii=False, allow_nan=False), mimetype='application/json')
                response.headers['Content-Disposition'] = f'attachment; filename="saved_synthetic_scenario_{row.id}.json"'
                response.headers['Cache-Control'] = 'no-store'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                return response
            from .patient_state_pages import scenario_state_summary
            state_info = scenario_state_summary(row.id)
            report = row.payload['analysis']['report']
            page = request.args.get('page', 1, type=int)
            records = report['criteria']['records']
            page_count = max(1, (len(records) + 24) // 25)
            if not page or page < 1 or page > page_count:
                abort(404)
            return _response('landscape_saved_scenario.html', saved=row, payload=row.payload,
                             state_info=state_info, report=report, page=page, page_count=page_count, rows=records[(page-1)*25:page*25])
        except ValueError as exc:
            return _error(exc)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Saved scenario is temporarily unavailable.', 503)
