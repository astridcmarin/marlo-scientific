"""Reviewed covariate variations, keeping the source archive immutable."""
import copy
import json
import math
from flask import abort, request, redirect, url_for
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy.exc import SQLAlchemyError
from intelligence_store.extensions import db
from intelligence_store.patient_state import digest
from intelligence_store.educational_pk_runs import EducationalPKRun, read_pk_run, save_pk_run
from intelligence_store.educational_pk_audit import audit_pk_run
from intelligence_store.educational_pk import calculate_educational_pk, CONTRACT_SHA256, METHOD_VERSION
from intelligence_store.pk_model_inputs import validate_model_inputs, INPUT_CONTRACT_SHA256
from intelligence_store.pk_parameter_reference import EXTRACT_SHA256
from intelligence_store.published_transit_reference import CONTRACT_SHA256 as STRUCTURE_SHA256
from intelligence_store.model_coverage import CONTRACT_SHA256 as COVERAGE_SHA256
from intelligence_store.treatment_requests import validate_treatment_request
from .educational_pk_run_pages import _context
from .workspace_pages import COOKIE, TTL, _form_token, _validate_token, _response, _signer
from .scenario_pages import _error

FIELDS = {'ffm', 'crcl', 'note', 'title'}
FORM_FIELDS = FIELDS | {'action', 'form_token', 'review_token'}


def _source(run_id, revision_id):
    row = db.session.get(EducationalPKRun, run_id)
    if row is None or row.revision_id != revision_id:
        abort(404)
    row = read_pk_run(run_id)
    report = row.payload['report']; review = report['preflight_review']
    preview = review.get('standalone_input_preview')
    if not isinstance(preview, dict):
        raise ValueError('The source archive lacks a supported parameter preview. No variation is prepared.')
    if (report['method_version'] != METHOD_VERSION or report['execution_contract_sha256'] != CONTRACT_SHA256
            or review['coverage_contract_sha256'] != COVERAGE_SHA256
            or review['binding']['structure_contract_sha256'] != STRUCTURE_SHA256
            or review['binding']['input_contract_sha256'] != INPUT_CONTRACT_SHA256
            or preview['parameter_extract_sha256'] != EXTRACT_SHA256):
        raise ValueError('The source archive uses different model contracts. This variation workflow is withheld.')
    if audit_pk_run(run_id)['status'] != 'mathematical_checks_passed':
        raise ValueError('The source archive did not pass its mathematical audit. No variation is prepared.')
    return row


def _number(text, label):
    if not isinstance(text, str) or len(text) > 40:
        raise ValueError(f'{label}: enter a finite positive number in the displayed unit.')
    try:
        value = float(text)
    except (ValueError, OverflowError):
        raise ValueError(f'{label}: enter a finite positive number in the displayed unit.') from None
    if not math.isfinite(value) or not 0 < value <= 1000000:
        raise ValueError(f'{label}: enter a finite positive number within the implementation limit.')
    return value


def _proposal(row, values):
    note = values['note'].strip(); title = values['title'].strip()
    if not 1 <= len(note) <= 500 or any(ord(c) < 32 for c in note):
        raise ValueError('Supply a one-line rationale for the synthetic variation (1–500 characters).')
    if not 1 <= len(title) <= 160 or any(ord(c) < 32 for c in title):
        raise ValueError('Supply a one-line new-run title (1–160 characters).')
    review = row.payload['report']['preflight_review']
    original = review['explicit_model_inputs']
    inputs = copy.deepcopy(original)
    changed = []
    source = {'source_run_id': row.id, 'source_revision_id': row.revision_id,
              'source_payload_sha256': row.payload_sha256, 'source_report_sha256': row.report_sha256}
    # Existing schema provenance text carries the source anchor without a storage migration.
    link = json.dumps(dict(source, kind='educational_covariate_variation_v1', rationale=note),
                      ensure_ascii=False, separators=(',', ':'))
    for field, key in [('fat_free_mass', 'ffm'), ('creatinine_clearance', 'crcl')]:
        value = _number(values[key], field)
        if value != original['fields'][field]['value']:
            changed.append(field)
            inputs['fields'][field].update(value=value, origin='synthetic_input',
                method='direct_synthetic_covariate', source_ref=link)
    inputs = validate_model_inputs(inputs)
    treatment = copy.deepcopy(review['treatment_request_preview']['request'])
    # Only top-level provenance changes. Drug, disease, units, event values and event provenance remain copied.
    treatment['source_ref'] = link
    treatment = validate_treatment_request(treatment)
    disease = review['declared_disease_context']['code']
    proposal = dict(source, inputs=inputs, treatment=treatment, disease=disease, title=title,
                    note=note, changed_fields=changed,
                    original_request_sha256=digest(review['treatment_request_preview']['request']))
    proposal['proposal_sha256'] = digest(proposal)
    return proposal


def _approval_signer():
    signer = _signer()
    signer.salt = b'intelligence-pk-variation-review-v1'
    return signer


def _approval(proposal, stage, report_sha256=None):
    return _approval_signer().dumps({'kind':'pk_variation_approval_v1', 'nonce':request.cookies.get(COOKIE),
                           'proposal_sha256':proposal['proposal_sha256'], 'stage':stage,
                           'report_sha256':report_sha256})


def _check_approval(proposal, action):
    try:
        data = _approval_signer().loads(request.form['review_token'], max_age=TTL)
    except (BadSignature, SignatureExpired):
        abort(403)
    if (data.get('kind') != 'pk_variation_approval_v1' or data.get('nonce') != request.cookies.get(COOKIE)
            or data.get('proposal_sha256') != proposal['proposal_sha256']
            or data.get('stage') not in ('reviewed', 'calculated')
            or (action == 'save' and data.get('stage') != 'calculated')):
        abort(403)
    return data


def register_educational_pk_variation_pages(bp):
    @bp.route('/workspace/scenarios/<int:scenario_id>/patient-state/revisions/<int:revision_id>/pk-runs/<int:run_id>/variation', methods=['GET', 'POST'])
    def saved_pk_variation(scenario_id, revision_id, run_id):
        if request.args:
            abort(400)
        if request.content_length and request.content_length > 16000:
            abort(413)
        try:
            scenario, revision = _context(scenario_id, revision_id)
            row = _source(run_id, revision_id)
            source_review = row.payload['report']['preflight_review']
            fields = source_review['explicit_model_inputs']['fields']
            values = {'ffm':str(fields['fat_free_mass']['value']),
                      'crcl':str(fields['creatinine_clearance']['value']),
                      'note':'', 'title':f'Variation of run #{run_id}'}
            proposal = None; report = None; approval = ''; error = None; status = 200
            if request.method == 'POST':
                if set(request.form) != FORM_FIELDS or any(len(request.form.getlist(k)) != 1 for k in request.form):
                    abort(400)
                _validate_token()
                action = request.form['action']
                if action not in ('review', 'calculate', 'save'):
                    abort(400)
                values = {key:request.form[key] for key in FIELDS}
                try:
                    proposal = _proposal(row, values)
                    if action == 'review':
                        approval = _approval(proposal, 'reviewed')
                    else:
                        prior = _check_approval(proposal, action)
                        report = calculate_educational_pk(revision_id, proposal['inputs'], proposal['treatment'], proposal['disease'])
                        if action == 'save':
                            if report['status'] != 'completed_educational_calculation' or report['report_sha256'] != prior['report_sha256']:
                                raise ValueError('The calculation differs from the reviewed result. Review and calculate again; no new run was saved.')
                            new = save_pk_run(revision_id, proposal['inputs'], proposal['treatment'], proposal['disease'], title=proposal['title'])
                            return redirect(url_for('landscape.saved_pk_compare', scenario_id=scenario_id, revision_id=revision_id,
                                                    left=row.id, right=new.id), code=303)
                        if report['status'] == 'completed_educational_calculation':
                            approval = _approval(proposal, 'calculated', report['report_sha256'])
                        else:
                            approval = _approval(proposal, 'reviewed')
                except (ValueError, OverflowError) as exc:
                    error = str(exc); status = 400; approval = ''
            from .educational_pk_pages import _charts
            nonce, token = _form_token()
            response = _response('landscape_pk_variation.html', scenario=scenario, revision=revision,
                source_run=row, source_review=source_review, values=values, proposal=proposal,
                report=report, charts=_charts(report), review_token=approval, form_token=token, error=error)
            response.status_code = status
            response.set_cookie(COOKIE, nonce, max_age=TTL, httponly=True, secure=request.is_secure,
                                samesite='Strict', path='/landscape/workspace')
            return response
        except ValueError as exc:
            return _error(exc, 409)
        except SQLAlchemyError:
            db.session.rollback()
            return _error('Archived variation storage is temporarily unavailable.', 503)
