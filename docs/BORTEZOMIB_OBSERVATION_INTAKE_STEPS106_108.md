# Bortezomib observation intake v1 (historically labeled Steps 106–108)

Checkpoint naming: this batch reused step numbers already assigned to figure review, time-course modeling and assumption sensitivity. Its stable name is **observation intake v1**. Existing filenames and schema identifiers are retained for compatibility; see [checkpoint mapping](REPOSITORY_CHECKPOINT.md).

This new development batch follows Step105. Step106 defines a paired-observation extraction contract; Step107 checks source archives and record compatibility; Step108 produces a deterministic readiness report through one CLI. These are new implementation checkpoints, not previously recovered packages. The batch prepares evidence collection and does not resolve the scientific discrepancy.

## Scope and current finding

Step105's eight summary maxima are not paired concentration/activity observations. Seven summary means exceed the deterministic equation's maximum inhibition. Aggregation, normalization and selected series need review. This batch supplies no measured points, concentration-time driver, fit metric, source truth certification or clinical prediction. The default template is intentionally empty and reports `evidence_incomplete`.

The primary article pages were attempted on 12 October 2026 but returned an access check. No new article text or figure data were obtained during this batch. Existing Step104/105 extractions remain authoritative for their recorded provenance, with independent scientific review pending.

## Sources to examine

- Model: Zhang and Mager, DOI 10.1016/j.xphs.2018.11.024; https://pmc.ncbi.nlm.nih.gov/articles/PMC6495529/ . Examine equation, fitted parameters, data sources, figure series and fitting selection.
- Clinical source: Reece et al., DOI 10.1007/s00280-010-1283-3; https://pmc.ncbi.nlm.nih.gov/articles/PMC3951913/ . Locate compatible concentration and activity profiles, source captions, sampling schedules and endpoint denominators.

Do not use Table3 mean peak inhibition as if it were measured at the time of a selected plasma concentration. The clinical source was used in model development and cannot be labeled independent external validation.

## Extraction contract

Copy the installed blank template to a new research folder. Keep each archived source inside that folder; `archive_file` is a relative path. Record its SHA256 of the actual saved bytes, exact table/figure locations, citation and DOI. An archive hash establishes byte identity only, not authenticity, scientific review or permission to redistribute it. No source articles are included in this batch.

Set `data_origin` to `published_observations` only after extraction from the source. Record reviewed rationales and locations for series selection, baseline normalization, aggregation, and population/schedule. Attribute the review to its actual reviewer; the software does not authenticate this declaration.

Each observation is an object with these fields:

| Field | Required meaning |
|---|---|
| `id`, `source_id` | Unique row identifier and source record identifier |
| `series_id`, `subject_or_group_id`, `visit_id`, `arm` | Distinguish source series, patient/group, visit and study arm |
| `population`, `schedule`, `pairing_evidence_location` | Document context and where pairing is supported |
| `route`, `dose_mg_per_m2` | IV and positive reported dose; no dose inferred from concentration |
| `aggregation` | `individual` or `group_mean_at_time`; peak summaries are unsupported |
| `endpoint_n` | Endpoint-specific positive integer; individual records require 1 |
| `concentration` | Object with `quantity: plasma_total_bortezomib`, `unit: nM`, `value`, `time_h`, `source_location`, `extraction_uncertainty`, `uncertainty_kind: absolute_digitization_bound` |
| `response` | Object with `quantity: 20S_activity_percent_of_baseline` or `20S_inhibition_percentage_points`, `value`, `time_h`, `source_location`, `extraction_uncertainty`, `uncertainty_kind: absolute_digitization_bound` |

Concentration and response must have the same declared nominal sampling time and compatible subject/group and series context. Do not interpolate, replace missing time points, invent covariate values or silently pair different series. If time grids or sample denominators differ, leave the record unresolved for scientific review. Original units and conversion derivations should remain in the extraction notes; the intake only accepts the canonical units and does not perform unit conversion.

`extraction_uncertainty` is a nonnegative absolute bound in nM for concentration and percentage points for response. Do not substitute a published SD or SE. If unavailable, leave null: the record remains incomplete. Zero is appropriate only for an exact tabulated transcription with a documented rationale, not an assumed digitization certainty. Bounds are recorded but not propagated by this version.

## Review commands

Default empty-template review:

```bash
python3 scripts/review_bortezomib_observation_intake.py
```

Review your own extracted file, retaining a new report:

```bash
python3 scripts/review_bortezomib_observation_intake.py --input /absolute/path/observations.json --output /absolute/path/intake-report.json
```

Output files are never overwritten. Archive paths outside the input directory, including symlinks that leave it, are rejected. No patient database or network is accessed. All outputs keep `clinical_prediction_validated`, `ready_for_patient_simulation`, and `step105_discrepancy_resolved` false. No RMSE, MAE or fitted parameters are calculated. A nonempty structurally complete dataset reports `manual_comparison_review_required`, not validation success.

## Roadmap checkpoint

This advances the evidence preparation layer of drug-specific endpoint development. Actual extraction, independent review, matched-profile comparison, uncertainty analysis remain ahead. A study-regimen time-course candidate exists, but a scientifically supported, patient-compatible bortezomib PK implementation remains ahead. Broader disease and drug coverage remains a separate active roadmap goal. Deployment is deferred.
