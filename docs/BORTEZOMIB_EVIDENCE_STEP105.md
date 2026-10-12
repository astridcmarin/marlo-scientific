# Step 105 — Observed evidence and equation limits

This step adds a read-only evidence page, linked prominently from the Step 104 equation explorer, plus a standalone review command and JSON export. It makes a scientific limitation visible before more features depend on that equation.

## Source work completed

The model equation and parameter transcription were rechecked against directly retrieved primary-article HTML/MathML, including Equation 5 and Table 1. Reference 10 identifies the clinical source study. This remains an AI-assisted review, not independent verification.

Eight mean peak-inhibition summaries, standard deviations and endpoint-specific sample sizes were extracted from Reece et al., Table 3. Footnotes were included: the two 1.0 mg/m² day-11 Emax entries use n=11 despite n=12 in their column headers. Randomized arm size, evaluable arm size and endpoint-specific n are distinct.

Sources:

- Model: https://doi.org/10.1016/j.xphs.2018.11.024
- Clinical observations: https://doi.org/10.1007/s00280-010-1283-3

The extraction records retrieval dates, source locations and hashes of the reviewed HTML bytes. Whole articles are not redistributed. Website HTML can change across retrievals; those hashes identify the reviewed responses, not immutable publisher versions. PDF visual verification was not completed.

## Finding and interpretation

The deterministic Step 104 component caps inhibition at 71.1 percentage points. Seven of the eight observed summary means exceed this ceiling. This is a descriptive bound screen, not a prediction-error calculation or formal model-rejection test.

The summaries and model-fitted profiles need not represent the same statistical quantity. Individual peak times may differ; the mean of individual maxima can exceed the maximum of the mean profile. The implemented component also has no observation-error or between-patient variability model. The next investigation must check series selection, baseline normalization and aggregation before drawing conclusions about fit.

This source study contributed to model development. Reusing it does not establish independent external validation. The app deliberately does not calculate inferred concentrations, RMSE, p-values or confidence intervals from these summaries. An SD is not an SE or a prediction interval. Repeated-visit sample sizes are not summed into a patient count.

## What remains unchanged

The Step 104 equation, parameters and original source-extraction hash remain frozen. This review is an additional versioned record. Patient archives, database tables and efficacy/toxicity capability classifications are unchanged. The new page does not establish dose suitability, tumour response or toxicity.

## Architecture

A pure module checks the hashes of both the observed-summary extraction and the specific model-reference version. It constructs a deterministic review with explicit missing concentration/time pairs and absent fit metrics. The UI and CLI use this report. Missing or modified evidence blocks the review. The installer checks Step 104 prerequisites and source compatibility, backs up changed files, and requires no migration or new dependencies.

## Next scientific milestone

Extract matching concentration/activity series from the relevant figures with uncertainty and clear series identities. Check what was included in model fitting. Only then evaluate curve reproduction and consider a compatible bortezomib PK driver. A published equation's existence is not enough to justify patient-specific response predictions.
