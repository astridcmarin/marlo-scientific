"""Versioned synthetic state data; no pharmacological or physiological model."""
from datetime import datetime, timezone
import hashlib
import json
import math
import re

import click

SCHEMA_VERSION = 'synthetic-patient-state-v1'
VALIDATION_VERSION = 'patient-state-validation-v1.0'
# Units describe field identity, not a claim about normality or model applicability.
UNITS = {
    'age_years': 'year', 'biological_sex': None,
    'weight': 'kg', 'height': 'cm',
    'egfr_indexed': 'mL/min/1.73m2', 'creatinine_clearance': 'mL/min',
    'serum_creatinine': 'umol/L', 'alt': 'U/L', 'ast': 'U/L',
    'albumin': 'g/L', 'total_bilirubin': 'umol/L',
}
ORIGINS = ('unknown', 'synthetic_input', 'assumption', 'legacy_scenario')
FIELD_KEYS = {'value', 'unit', 'origin', 'observed_at', 'source_ref'}


class PatientStateError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def unknown_field(name):
    return {'value': None, 'unit': UNITS[name], 'origin': 'unknown',
            'observed_at': None, 'source_ref': None}


def validate_patient_state(state):
    """Return an independent canonical copy. Omitted fields remain unknown."""
    if not isinstance(state, dict) or set(state) != {'schema_version', 'purpose', 'fields'}:
        raise PatientStateError('State requires schema_version, purpose and fields only.')
    if state['schema_version'] != SCHEMA_VERSION or state['purpose'] != 'synthetic_educational':
        raise PatientStateError('Only the synthetic educational state schema is supported.')
    fields = state['fields']
    if not isinstance(fields, dict) or set(fields) - set(UNITS):
        raise PatientStateError('State contains missing or unsupported field definitions.')
    result = {'schema_version': SCHEMA_VERSION, 'purpose': 'synthetic_educational', 'fields': {}}
    for name, unit in UNITS.items():
        raw = fields.get(name, unknown_field(name))
        if not isinstance(raw, dict) or set(raw) != FIELD_KEYS:
            raise PatientStateError(f'{name}: supply value, unit, origin, observed_at and source_ref.')
        if raw['unit'] != unit:
            raise PatientStateError(f'{name}: expected unit {unit!r}; no unit conversion is performed.')
        origin = raw['origin']
        if origin not in ORIGINS:
            raise PatientStateError(f'{name}: unsupported origin; calculated origins are not supported yet.')
        value = raw['value']
        if value is None:
            if origin != 'unknown':
                raise PatientStateError(f'{name}: a null value requires unknown origin.')
        else:
            if origin == 'unknown':
                raise PatientStateError(f'{name}: a supplied value requires an explicit origin.')
            if name == 'biological_sex':
                if value not in ('FEMALE', 'MALE'):
                    raise PatientStateError('biological_sex: use FEMALE, MALE or null for unknown.')
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                    raise PatientStateError(f'{name}: expected a finite numeric value or null.')
                try:
                    value = float(value)
                except (ValueError, OverflowError) as exc:
                    raise PatientStateError(f'{name}: expected a finite numeric value or null.') from exc
                if not math.isfinite(value) or value < 0:
                    raise PatientStateError(f'{name}: expected a finite nonnegative value.')
                if name in ('weight', 'height') and value == 0:
                    raise PatientStateError(f'{name}: supplied value must be positive.')
                if name == 'age_years' and value > 130:
                    raise PatientStateError('age_years: supported software input range is 0–130.')
        observed = raw['observed_at']
        if observed is not None:
            if not isinstance(observed, str) or len(observed) > 64:
                raise PatientStateError(f'{name}: observed_at must be an ISO timestamp with timezone or null.')
            try:
                parsed = datetime.fromisoformat(observed.replace('Z', '+00:00'))
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise ValueError('Timezone required')
                observed = parsed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
            except (ValueError, OverflowError) as exc:
                raise PatientStateError(f'{name}: observed_at requires a valid timestamp and timezone.') from exc
        source = raw['source_ref']
        if source is not None:
            if not isinstance(source, str) or not source.strip() or len(source) > 240:
                raise PatientStateError(f'{name}: source_ref must be nonblank text of at most 240 characters or null.')
            source = source.strip()
        if origin in ('assumption', 'legacy_scenario') and source is None:
            raise PatientStateError(f'{name}: this origin requires a source reference or assumption rationale.')
        result['fields'][name] = {'value': value, 'unit': unit, 'origin': origin,
                                 'observed_at': observed, 'source_ref': source}
    return result


def state_from_scenario(profile):
    """Copy supported v1 inputs; do not require today's drug catalog or mutate v1."""
    from .patient_scenarios import validate_scenario
    if not isinstance(profile, dict) or not isinstance(profile.get('selected_drug'), str):
        raise PatientStateError('Expected an existing v1 scenario profile.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', profile['selected_drug']):
        raise PatientStateError('The legacy drug identifier is invalid.')
    # Validate the legacy schema without reinterpreting its drug under a newer catalog.
    validated = validate_scenario(profile, alias_catalog={'entries': [{'id': profile['selected_drug']}]})
    source = 'legacy-profile-sha256:' + digest(profile)
    fields = {}
    for old, new in [('age_years', 'age_years'), ('biological_sex', 'biological_sex'),
                     ('weight_kg', 'weight'), ('egfr_ml_min_1_73m2', 'egfr_indexed')]:
        value = validated[old]
        if value == 'UNSPECIFIED':
            value = None
        fields[new] = unknown_field(new) if value is None else {
            'value': value, 'unit': UNITS[new], 'origin': 'legacy_scenario',
            'observed_at': None, 'source_ref': source}
    return validate_patient_state({'schema_version': SCHEMA_VERSION,
                                   'purpose': 'synthetic_educational', 'fields': fields})


def preview_patient_state(state):
    canonical = validate_patient_state(state)
    known = [name for name, field in canonical['fields'].items() if field['value'] is not None]
    return {'schema_version': 'patient-state-preview-v1', 'validation_version': VALIDATION_VERSION,
            'state': canonical, 'state_sha256': digest(canonical), 'known_fields': known,
            'unknown_fields': [name for name in UNITS if name not in known],
            'simulation_status': 'not_run',
            'limitation': 'Synthetic state input validation only. No normal-range interpretation, organ-function score, '
                          'derived physiology, exposure adjustment or patient-response prediction. '
                          'Provenance is recorded input metadata, not independently verified evidence.'}


def example_state():
    fields = {}
    for name, value in [('age_years', 65), ('biological_sex', 'FEMALE'), ('weight', 70),
                        ('height', 165), ('egfr_indexed', 60)]:
        fields[name] = {'value': value, 'unit': UNITS[name], 'origin': 'synthetic_input',
                        'observed_at': None, 'source_ref': None}
    return validate_patient_state({'schema_version': SCHEMA_VERSION,
                                   'purpose': 'synthetic_educational', 'fields': fields})


def _read_json(path):
    with open(path, 'rb') as handle:
        content = handle.read(131073)
    if len(content) > 131072:
        raise PatientStateError('Input JSON exceeds 128 KiB.')
    def invalid_constant(value):
        raise PatientStateError('JSON contains a nonfinite numeric constant.')
    return json.loads(content, parse_constant=invalid_constant)


def register_patient_state_commands(app):
    @app.cli.command('patient-state')
    @click.option('--example', is_flag=True, help='Preview an explicitly invented example.')
    @click.option('--state-file', type=click.Path(exists=True, dir_okay=False), help='Validate raw state JSON.')
    @click.option('--scenario-file', type=click.Path(exists=True, dir_okay=False), help='Copy a v1 profile or Patient Lab report JSON.')
    @click.option('--output', type=click.Path(dir_okay=False), help='Create preview JSON; existing files are not overwritten.')
    def patient_state(example, state_file, scenario_file, output):
        """Validate synthetic patient-state data without database reads or writes."""
        if sum((example, state_file is not None, scenario_file is not None)) != 1:
            raise click.ClickException('Choose exactly one of --example, --state-file or --scenario-file.')
        try:
            if example:
                state = example_state()
            elif state_file:
                state = _read_json(state_file)
                if isinstance(state, dict) and state.get('schema_version') == 'patient-state-preview-v1':
                    if 'state' not in state or state.get('state_sha256') != digest(state['state']):
                        raise PatientStateError('Preview state digest mismatch. Edit raw state input instead of a hashed preview.')
                    state = state['state']
            else:
                source = _read_json(scenario_file)
                if not isinstance(source, dict):
                    raise PatientStateError('Expected a legacy profile or Patient Lab report object.')
                state = state_from_scenario(source.get('profile', source))
            report = preview_patient_state(state)
            payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if output:
                with open(output, 'x', encoding='utf-8') as handle:
                    handle.write(payload)
                click.echo(f'Saved preview: {output}\nState SHA256: {report["state_sha256"]}')
            else:
                click.echo(payload, nl=False)
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
            raise click.ClickException(str(exc)) from exc
