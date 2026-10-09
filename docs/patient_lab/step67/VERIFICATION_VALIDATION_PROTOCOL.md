# Patient Lab: verification and validation protocol draft

Protocol: `hughes-educational-verification-validation-draft-1` • Date: 2026-10-08

**Draft, not locked or approved.** This step creates a plan. It supplies no scientific signoff, accepted empirical result, clinical prediction validation or deployment readiness. Unknown decisions remain null in the accompanying JSON. The existing application gates are unchanged.

## 1. What question are we answering?

The immediate question is whether the selected deterministic implementation correctly calculates a typical lenalidomide concentration curve, and later how those fixed predictions compare with suitable measured concentrations. This is narrower than predicting an individual's response.

Verification asks whether we calculated the specified equations correctly. Empirical evaluation asks whether the resulting predictions describe measured data for a defined population and intended use. Agreement with another solver or synthetic fixture answers the first question; it cannot answer the second.

The FDA's February 2022 Population Pharmacokinetics guidance connects evaluation rigor to intended use and emphasizes prespecified questions, representative data and assessment of accuracy, precision and misspecification. This project uses that general principle as a reference. These project targets are not FDA acceptance thresholds or regulatory approval.

Reference: https://www.fda.gov/media/128793/download (printed page 3).

## 2. Freeze the current implementation scope

The source is Hughes et al., DOI 10.1111/bcp.13873, Supplementary Material 2. The supplied document's SHA256 is `261734ad9632f1a0f19156b8b4b6cd88d6637cbefe89be4363791caeeda11849`.

The bounded educational implementation uses oral capsule inputs, zero initial amounts, all individual random effects set to zero and no observation error. It permits at most four daily events beginning at zero, at most 72 hours, a 0.1-hour display grid and RK4 maximum step 0.001 hour. Existing drug, formulation, disease, dose, covariate and context checks still apply. These execution limits are project policy, not published clinical regimen advice.

The typical algebra is:

- CL/F = 12 × (FFM / 55)^0.75 × (CrCl / 90)^0.224 L/h.
- V/F = 68.8 × (FFM / 55) L.
- KTR = 13.5 h⁻¹; elimination rate = (CL/F) / (V/F).

FFM is in kg; CrCl is in mL/min. Indexed eGFR is not substituted for CrCl. Covariate measurement/estimation methods and timing need explicit assessment; an estimated value is not silently treated as a measured quantity. Apparent oral parameters already contain F: adding a guessed bioavailability factor would change the model.

The eight precentral boxes are ABS and TRANS1–TRANS7. In source order, central is compartment 2, receiving inflow from compartment 9. These mathematical transit boxes are not anatomical organs.

The JSON binds the execution contract, numerical audit implementation, Step 65 source assessment and Step 66 data-access inventory by file SHA256. Those hashes describe the copies used to draft this protocol. If installed files differ, reconcile and rebind before locking; this document does not certify an unseen local installation.

## 3. Separate the evidence workstreams

| Workstream | Comparison | What it could establish | Current limitation |
|---|---|---|---|
| Source transcription | Selected source against equations, units, topology and typical algebra | Correct representation of the selected source | Step 65 was assisted and bounded; independent review remains outstanding |
| Mathematical verification | Solver outputs against analytic references and conservation identities | Numerical implementation correctness within the checked scope | Does not validate covariate methods or predict observed concentrations |
| Original source replay | Matched source-generated typical predictions against project predictions | Reproduction of specified source calculations | Original dataset, histories and numeric outputs not obtained |
| Internal empirical characterization | Fixed typical predictions against development observations | Fit/description in data used to develop the model | Not independent validation |
| External empirical evaluation | Fixed predictions against eligible independent-study observations | Performance for that defined dataset and use | Dataset suitability, rights and protocol decisions unresolved |

Reproducing the original population estimation, covariance and residual-error model is a separate task. The current deterministic workflow cannot reproduce a stochastic VPC or individual prediction intervals. A published aggregate plot or a visually similar curve is not a substitute for source outputs or participant observations.

## 4. Numerical verification criteria already in the project

Use `abs(actual − reference) ≤ atol + rtol × abs(reference)`, require finite values and equal expected lengths. All applicable audit checks must pass. These are existing engineering tolerances, not newly selected empirical success criteria.

| Existing audit check | Absolute tolerance | Relative tolerance |
|---|---:|---:|
| Analytic concentration, including event states | 5 × 10⁻⁷ ng/mL | 10⁻⁸ |
| Analytic cumulative AUC, event AUC, total AUC, reported window AUC | 5 × 10⁻⁵ ng·h/mL | 10⁻⁸ |
| Analytic compartment amounts, including event states | 5 × 10⁻⁸ mg | 10⁻⁸ |
| Requested amount schedule | 10⁻¹⁰ mg | 0 |
| Point amount conservation and addition to ABS | 10⁻⁹ × total requested amount in mg | 0 |
| Event times | 0 h | 0 |
| Event continuity: concentration / cumulative AUC / central amount | 5 × 10⁻⁷ ng/mL / 5 × 10⁻⁵ ng·h/mL / 5 × 10⁻⁸ mg | 0 |

Total AUC is compared with 1000 × total requested amount / (CL/F). Window AUC is also checked against the final cumulative integral. Window AUC and AUC to infinity are distinct endpoints.

The numerical audit receives derived parameters. It cannot independently establish that FFM and CrCl were transformed into those parameters correctly. Retain a separate parameter-algebra and source-topology review, with the existing four Step 65 cases and additional independently selected boundary cases if justified. Step 65 checked parameter agreement at 10⁻¹² absolute/relative tolerance; that is also a technical check, not a clinical threshold.

For a locked verification campaign, record all case inputs, contract/code versions, expected reference method and actual results. Include permitted single and repeated events, event boundaries and representative allowed covariates. Specify any added case set and convergence experiment before execution. This document does not claim a new campaign has run.

## 5. Original source replay: compare like with like

Obtain the actual permitted analysis data and dictionary; actual dosing and sampling histories; source control stream; software/version/settings; numeric reference outputs; and meanings of the output columns. The referenced filenames `nmprep_flagged.csv` and `run016_cl_crcl2_ffm_vpc.fit` are not supplied files.

Select the exact comparator before replay. Project ETA=0 concentrations can be compared to source ETA=0 concentrations under matching events, covariates, time origin, units and initial conditions. Do not compare to fitted individual predictions, residual-error simulations or observations and label the mismatch a numerical transcription error. Refitting the original dataset is not part of this replay.

Replay absolute/relative tolerances remain **unresolved** until output precision, source solver settings and scientific purpose can justify them. Record the justification before seeing comparison errors. Original histories outside the current execution scope require a separately reviewed harness or scope change; do not truncate history to make them fit.

## 6. Draft empirical analysis plan

The proposed estimand is the error of fixed, typical concentration predictions at actual eligible observation times. Parameters remain fixed; do not fit subject ETAs to the evaluation observations. That would answer a different question about fitted individual predictions.

Before performance evaluation, lock the dataset identity and permitted use, independence from development data, target population, formulation, dose history, covariate definitions and timing, observation units, assay information and eligibility/exclusion rules. Record participant overlap across studies and define any development/evaluation partition at participant or study level, not randomly across correlated samples.

### Time and initial state

Actual administration and sample times matter. The current display grid is 0.1 hour. Arbitrary observation times require a separately specified, tested and versioned evaluation approach: do not silently round times or interpolate the UI curve. Prior doses, interruption history and nonzero initial amounts must be known or represented by an appropriate validated method; never replace unknown history with zero.

The possible external dataset discussed in Step 66 was not downloaded or accepted. Sampling after five consecutive doses cannot be directly represented by this workflow's four-event limit and zero initial state. Its possible role remains unresolved.

### Proposed metrics, pending scientific review

For eligible, quantified observations with both observed and predicted concentration strictly positive, define `e_ij = ln(predicted_ij / observed_ij)`, for sample j of participant i. With n_i samples per participant and N eligible participants:

- Proposed bias: `B = (1/N) Σ_i [(1/n_i) Σ_j e_ij]`.
- Proposed precision/error magnitude: `R = sqrt((1/N) Σ_i [(1/n_i) Σ_j e_ij²])`.

Zero bias means no average log-ratio bias under this weighting. R includes bias and scatter; it is not an estimate of biological variability. Equal participant weighting prevents dense sampling in one participant from dominating. These formulas are proposals, not accepted clinical endpoints.

Report observed-versus-predicted plots and errors against actual time since dose, dose, FFM and CrCl. Report counts of participants and samples, study composition, covariate coverage, and every exclusion reason. Subgroups and sensitivity analyses must be selected before results; exploratory findings are labeled as such.

Acceptance limits, precision objectives and sample-size justification remain null. Do not borrow an arbitrary ±20% or 80–125% rule. Sparse observations do not establish measured AUC, Cmax or Tmax; agreement for those endpoints requires suitable sampling and a separately prespecified reference estimator.

### Missingness, BLQ and uncertainty

Lock handling of missing covariates, questionable records, assay limits and below-limit-of-quantification (BLQ) observations before computing errors. The proposed log metrics cannot handle zeros or BLQ by treating them as quantified positive values. Do not silently set BLQ to zero, remove it without reporting, or impute missing physiology. If the dataset cannot support a defensible handling method, narrow or stop the analysis and document why.

Any confidence interval method must account for repeated samples within participants. A participant-cluster bootstrap is a candidate, not an implemented or chosen method; its suitability, confidence level, resample count and handling of multi-study structure remain unresolved. Sampling uncertainty in a performance metric is not an individual concentration prediction interval or a source of drug-response uncertainty estimates.

## 7. Validation workflow architecture

Keep permitted real participant data separate from synthetic PatientState, saved synthetic scenarios and educational PK archives. A future validation harness should be read-only with respect to the product database, validate a documented data schema, preserve actual histories, and report rejected records explicitly. No data import or harness is implemented in this step.

Every future run should archive protocol version/digest, dataset digest and dictionary, permission reference, source/model/code/environment identities, transformations, exclusions, endpoint formulas, outputs and reviewer decisions. Keep participant identifiers protected according to the dataset's terms; provenance does not require publishing identifiable source rows.

Synthetic fixtures can verify ingestion, metrics and report integrity. They must be labeled synthetic and cannot serve as predictive validation evidence. Do not write this planning JSON into the existing validation manifest as if it were an accepted empirical result.

## 8. What must be resolved before locking?

- Assign the analysis owner, qualified independent source reviewer and scientific reviewer; record identities and conflicts where relevant.
- Accept a specific permitted dataset and define the target use, population, eligibility, overlap and attrition reporting.
- Resolve units, covariate methods/timing, dose/sample histories, initial state, BLQ, missingness and observation-time evaluation.
- Justify source-replay tolerances and empirical endpoint acceptance limits; specify sample-size/precision objectives, uncertainty methods and sensitivity analyses.
- Freeze code, source, data and environment identities; record whether performance results have already been inspected.
- Record dated review, lock time and locked protocol digest. Archive amendments with reasons. Changes informed by performance make that analysis exploratory; a confirmatory claim requires a new independent evaluation under a prespecified plan.

These are requirements for claiming a prespecified scientific evaluation, not an approval request blocking ongoing educational software development. This draft neither assigns reviewers nor obtains their signoff.

Even a successful future concentration evaluation would not establish individual applicability, clinical efficacy, toxicity, dosing recommendations, disease progression or clinical deployment readiness. Those need separate models, evidence and intended-use review.

## 9. Immediate next step

Resolve independent source review and which dataset can support a defined question. Original source material would enable reproduction work; a suitable independent dataset could enable external evaluation after protocol and harness decisions. Those are different paths and need not be conflated. Until then, continue bounded educational work with science-pending status visible.
