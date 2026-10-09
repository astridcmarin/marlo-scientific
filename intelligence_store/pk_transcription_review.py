"""Source-bound preparation for independent transcription review; never sign-off."""
import copy
import hashlib
import json
from pathlib import Path
import click
from .patient_state import digest
from .pk_parameter_reference import load_parameter_extract, EXTRACT_SHA256
from .published_transit_reference import load_structure_contract, CONTRACT_SHA256 as STRUCTURE_SHA256
from .model_coverage import load_coverage_contract, CONTRACT_SHA256 as COVERAGE_SHA256
from .educational_pk import load_execution_contract, CONTRACT_SHA256 as EXECUTION_SHA256

METHOD = 'pk-transcription-review-preparation-v1.0'
LIMITATION = ('Review preparation only. Matching source-file bytes and project contracts does not '
              'establish independent transcription review, published population-model reproduction, '
              'clinical validity or individual applicability. No reviewer identity or approval is supplied.')


def transcription_review_packet(source_file=None):
    parameters = load_parameter_extract()
    structure = load_structure_contract()
    coverage = load_coverage_contract()
    execution = load_execution_contract()
    if execution['structure_contract_sha256'] != STRUCTURE_SHA256 or execution['coverage_contract_sha256'] != COVERAGE_SHA256:
        raise ValueError('Execution contract is not bound to the loaded source contracts.')
    source = structure['source']
    source_file_check = {'status': 'not_supplied', 'expected_sha256': source['sha256'],
                         'actual_sha256': None, 'filename': None,
                         'meaning': 'Byte identity with the recorded supplement, not independent scientific review.'}
    if source_file is not None:
        path = Path(source_file)
        with path.open('rb') as handle:
            actual = hashlib.file_digest(handle, 'sha256').hexdigest()
        if actual != source['sha256']:
            raise ValueError('Source supplement SHA256 differs from the structure contract; no review packet was generated.')
        source_file_check.update(status='source_file_hash_matches', actual_sha256=actual, filename=path.name)
    items = []
    def item(code, label, transcription, locations, category='published_source'):
        items.append({'code': code, 'label': label, 'category': category,
                      'project_transcription': copy.deepcopy(transcription),
                      'recorded_source_locations': copy.deepcopy(locations),
                      'verification_status': 'independent_review_required'})
    for code, value in parameters['parameters'].items():
        item('parameter_' + code, code.replace('_', ' '), value, [value['location']])
    item('parameter_equations', 'Typical-value parameter equations', parameters['equations'], parameters['source']['locations'])
    item('covariate_definitions', 'FFM and CrCl definitions', parameters['input_definitions'], ['Main paper Section 2.3', source['location']])
    item('compartment_structure', 'Final compartment ordering and absorption stages', structure['structure'], [source['location']])
    item('units_and_conversion', 'Source units and concentration display conversion', structure['units'], [source['location']])
    item('cross_contract_values', 'Parameter values across project contracts', {
        'parameter_extract': parameters['parameters'], 'structure_reference_values': structure['reference_values']},
        ['Main paper Table 2 final model column', source['location']], 'project_consistency')
    item('population_context', 'Reported source population and marginal coverage', {
        k: coverage[k] for k in ('study_subject_count', 'disease_counts', 'state_ranges', 'covariate_ranges', 'listed_amounts_mg')},
        coverage['source']['locations'])
    item('typical_value_omissions', 'Random effects, observation error and apparent parameter assumptions', {
        'typical_value_assumption': structure['typical_value_assumption'], 'boundaries': structure['boundaries']},
        [source['location']], 'project_assumptions')
    item('execution_policy', 'Project execution restrictions, not published validation limits', execution,
        ['Project educational execution contract'], 'project_policy')
    report = {
        'schema_version': 'pk-transcription-review-packet-v1', 'method_version': METHOD,
        'status': 'independent_review_pending',
        'source_reference': {'doi': source['doi'], 'url': source['url'],
            'recorded_supplement_filename': source['filename'], 'recorded_supplement_sha256': source['sha256']},
        'source_file_check': source_file_check,
        'contract_binding': {
            'parameter_extract': {'version': parameters['extract_version'], 'sha256': EXTRACT_SHA256},
            'structure': {'version': structure['contract_version'], 'sha256': STRUCTURE_SHA256},
            'coverage': {'version': coverage['contract_version'], 'sha256': COVERAGE_SHA256},
            'execution': {'version': execution['contract_version'], 'sha256': EXECUTION_SHA256}},
        'review_items': items,
        'historical_notes_to_reconcile': [
            {'code': 'parameter_extract_review_depth', 'recorded_text': parameters['source']['review_depth'],
             'context': 'This describes the earlier parameter extraction. The later structure contract records supplement review; do not treat the older statement as the current project-wide status.'},
            {'code': 'parameter_extract_limitations', 'recorded_text': copy.deepcopy(parameters['limitations']),
             'context': 'These describe the earlier parameter-layer scope. Reconcile against later modules without rewriting historical hash-bound artifacts.'}],
        'review_protocol': [
            'Have a qualified second reviewer inspect the main paper and final Supplementary Material 2 control stream independently before comparing the project transcription.',
            'Record reviewer identity, independence declaration, date, exact source locations, independently transcribed values and units, and discrepancies.',
            'Distinguish the final stream from exploratory Material 3 and distinguish source facts from educational project restrictions.',
            'Resolve every discrepancy with source-backed rationale and a versioned change if needed; a worksheet alone is not approval.',
            'Review source-model reproduction and predictive validation separately; neither follows from transcription agreement.'],
        'independent_review_completed': False, 'validation_approval': None,
        'clinical_prediction_validated': False, 'ready_for_patient_simulation': False,
        'database_writes_performed': False, 'ode_solver_rerun': False, 'network_refresh_performed': False,
        'limitation': LIMITATION}
    report['report_sha256'] = digest(report)
    return report


def independent_review_worksheet(packet):
    """Blank worksheet deliberately omits the project transcription to reduce anchoring."""
    report = {'schema_version': 'pk-independent-transcription-worksheet-v1',
        'method_version': METHOD, 'status': 'unassessed',
        'source_reference': copy.deepcopy(packet['source_reference']),
        'review_packet_sha256': packet['report_sha256'],
        'contract_binding': copy.deepcopy(packet['contract_binding']),
        'reviewer': {'name': None, 'qualifications': None, 'independence_declaration': None, 'reviewed_at': None},
        'items': [{'code': r['code'], 'label': r['label'], 'category': r['category'],
                   'source_locations': [], 'independent_transcription': None, 'units': None,
                   'comparison_result': 'unassessed', 'discrepancy': None, 'resolution': None}
                  for r in packet['review_items']],
        'review_decision': None, 'clinical_prediction_validated': False,
        'ready_for_patient_simulation': False,
        'limitation': 'Blank external review worksheet; no completed reviewer record is imported, authenticated, saved or approved by this step.'}
    report['template_sha256'] = digest(report)
    return report


def register_pk_transcription_review_commands(app):
    @app.cli.command('pk-transcription-review')
    @click.option('--source-file', type=click.Path(exists=True, dir_okay=False, path_type=Path))
    @click.option('--worksheet', is_flag=True, help='Export a blank independent reviewer worksheet instead of the project packet.')
    @click.option('--json', 'json_output', is_flag=True)
    @click.option('--output', type=click.Path(dir_okay=False, path_type=Path))
    def command(source_file, worksheet, json_output, output):
        """Prepare a review of current source contracts; needs no stored patient run."""
        try:
            report = transcription_review_packet(source_file)
            if worksheet:
                report = independent_review_worksheet(report)
            if output:
                with output.open('x', encoding='utf-8') as handle:
                    json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
                    handle.write('\n')
                click.echo(f'Exported transcription review: {output}')
            elif json_output:
                click.echo(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
            else:
                click.echo(f"Hughes 2019 | {report['status']} | Independent review completed: false")
                if worksheet:
                    click.echo(f"Blank reviewer worksheet: {len(report['items'])} items; no reviewer or approval supplied.")
                else:
                    click.echo(f"Source file: {report['source_file_check']['status']} | Review items: {len(report['review_items'])}")
                click.echo(LIMITATION)
        except (ValueError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
