# Original materials and intake checklist

Purpose: enable a documented reproduction study of the original model. This checklist is a project proposal, not an assertion that a custodian will grant access. It is not an email and no request has been sent.

## Materials to clarify with a verified custodian

1. The analysis-ready dataset used with the final control stream, with deidentified subject/study identifiers and a data dictionary.
2. Observation records: actual elapsed times, concentration values and units, missing/below-quantification indicators and assay limits.
3. Administration records: amount, units, route, formulation, actual or imputed times, previous treatment history, event/compartment indicators and repeat-dose fields used by the source model.
4. Covariates: recorded FFM and CrCl, units, estimation methods and the demographic/laboratory inputs used where permitted. Clarify whether CRCL2 means the covariate defined in the published stream.
5. Analysis flags and preprocessing: exclusions, imputation rules, influential-outlier handling, dataset transformations, and the mapping between publication counts and analysis rows.
6. Exact final control stream and estimation/simulation settings, including the random-effects covariance, observation-error model, software/compiler versions and simulation seeds where relevant.
7. Numeric reference outputs sufficient for a declared replay comparison: parameter estimates, prediction tables and run summaries. Diagnostic/validation outputs are a separate request from a deterministic curve replay.
8. Access terms: permitted purpose, retention, redistribution, derived-output publication and access restrictions. Retain a documented permission decision; do not infer one from article access.
9. Clarification of the study-ID footnote ambiguity recorded in the assessment.

## Intake before modeling

- Preserve original files read-only and record source, receipt date, checksum and version. Maintain a separate transformed copy with a reproducible transformation log.
- Verify the dictionary and units; do not silently convert concentration values, indexed eGFR, CrCl, total weight or FFM into substitutes.
- Confirm the observation timing and entire administration history required for the intended replay. Unknown administrations remain unknown until clarified.
- Confirm whether outputs are typical predictions, individual predictions or error-bearing simulated observations. Compare like with like.
- Select the model revision, intended use, endpoint definitions and cohort eligibility explicitly. Establish inclusion/exclusion rules before outcome comparison.
- Define numerical replay tolerances separately from empirical predictive-performance acceptance criteria. Agree on the latter with an appropriate scientific reviewer before fitting or assessing performance; no clinical threshold is supplied by this checklist.
- Label internal reproduction, external evaluation and individual applicability as different objectives. No one objective automatically approves the others.
- Archive failed and excluded records with reasons; do not keep only cases that agree with the model.

Until intake is complete, received data would remain candidate evidence rather than accepted validation evidence. Existing trial summaries, synthetic calculations, source hashes and model equations are useful context but do not replace observed concentration data.
