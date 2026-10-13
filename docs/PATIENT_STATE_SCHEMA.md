# Synthetic patient-state schema v1

Root keys are exactly `schema_version`, `purpose` and `fields`:

- schema_version: `synthetic-patient-state-v1`
- purpose: `synthetic_educational`
- fields: a dictionary containing any subset of the supported fields below

Omitted fields canonicalize to null values with unknown origin. An explicit field
requires exactly `value`, `unit`, `origin`, `observed_at` and `source_ref`.
Unsupported fields are rejected rather than silently ignored.

| Field | Exact unit | Input type |
|---|---|---|
| age_years | year | finite number, 0–130 |
| biological_sex | null | FEMALE, MALE or null |
| weight | kg | finite positive number |
| height | cm | finite positive number |
| egfr_indexed | mL/min/1.73m2 | finite nonnegative number |
| creatinine_clearance | mL/min | finite nonnegative number |
| serum_creatinine | umol/L | finite nonnegative number |
| alt | U/L | finite nonnegative number |
| ast | U/L | finite nonnegative number |
| albumin | g/L | finite nonnegative number |
| total_bilirubin | umol/L | finite nonnegative number |

Every field can instead have a null value and unknown origin. Numeric strings are
accepted and canonicalized to floats; booleans, infinities and NaN are rejected.
These are data-contract rules. The schema does not declare a value physiologically
plausible or within a clinical reference interval. Unit conversion is deferred.

## Provenance

Origins:

- `unknown`: requires a null value.
- `synthetic_input`: a supplied invented value; optional source reference.
- `assumption`: requires a nonblank source reference or assumption rationale.
- `legacy_scenario`: requires a source reference; the adapter identifies the
  original v1 profile by SHA256. It does not invent richer provenance.

`source_ref` is null or nonblank text of at most 240 characters. It is recorded,
not fetched or authenticated. `observed_at` is null or an ISO timestamp with a
specified timezone. Supplied times canonicalize to UTC; no current timestamp is
filled automatically. All fields in this stage belong to synthetic scenarios.

A known value cannot have unknown origin. A null value cannot claim a known
origin. The validator has no supported derivation formulas and rejects `derived`
origins. Omitted fields' units describe schema identity, not an observed measurement.

## Preview contract

`preview_patient_state` returns:

- preview schema and validator versions
- canonical state and its SHA256
- known and unknown field-name lists
- `simulation_status: not_run`
- interpretation limitations

The digest covers the canonical state, including field provenance; it does not
cover all surrounding preview metadata. The CLI verifies that digest when a
preview is used as input, then revalidates and regenerates the preview. Edit raw
state inputs for changes rather than changing a captured preview in place.

Raw input files and previews are capped at 128 KiB. Input mode must be exactly
one of example, raw/preview state file or legacy scenario file. File output is
explicit and does not overwrite an existing destination. No database read/write
or external request is needed by the validator/preview command.

## Compatibility and next architecture step

> Superseded in part (13 October 2026): stored, immutable state revisions now exist (`patient_state_revisions.py`, migration `f25e8b6a96c1`), and model execution from a revision is implemented for the Hughes lenalidomide model (see [Patient Lab 2.0](PATIENT_LAB_2_0.md)). The compatibility notes below still apply; the "not yet" statements describe the state at the time of writing.


Legacy scenario v1 schema, stored payloads and report digests are unchanged.
The adapter invokes that schema's validator with a local placeholder catalog for
the legacy selected ID; this checks profile syntax without asserting current drug
support. State validation is independent of catalog provenance and trial analysis.

A versioned state does not yet mean a stored state revision. Persistence needs a
new model/migration with revision lineage, immutable snapshots and explicit links
to existing scenarios. The web form should be extended after that contract exists.
Future model execution should record the specific state revision/input subset,
model and parameter versions, solver settings, ignored fields and uncertainty.
Adding a recorded field must not implicitly change numerical model behavior.
