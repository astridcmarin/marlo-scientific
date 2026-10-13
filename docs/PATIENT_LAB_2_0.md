# Patient Lab 2.0 — covariate-aware virtual patient

Recorded 13 October 2026. Owner: Astrid. Status: in progress (2.0a–2.0e done).

## Goal

A synthetic patient's declared characteristics produce, through documented formulas and one published population PK model, an individual lenalidomide exposure prediction with variability, applicability flags and full provenance.

Today the Hughes 2019 model runs only on covariates typed in directly (`pk_model_inputs`, `educational_pk`). Patient Lab 2.0 connects the patient state to those covariates, so changing a patient's weight, height or creatinine changes the curve for a traceable reason.

## Why lenalidomide and renal function first

Lenalidomide is cleared mostly by the kidneys as unchanged drug, and its label adjusts dose by creatinine-clearance bands. Renal function is therefore the covariate that matters most, and it is the first link in the long-term feedback loop (kidney function → clearance → exposure). Only that forward arrow is in scope. Toxicity feeding back on the kidney belongs to a later Simulation version.

## In scope

1. Derive physiology from declared inputs with recorded provenance (formula, version, inputs, assumptions).
2. Resolve each model's covariates exactly as its source defined them.
3. Check applicability against the source study's reported ranges; flag extrapolation, never hide it.
4. Typical-value and population (between-subject variability) predictions.
5. Compare virtual patients.
6. A provenance record for every run.

## Explicitly not in scope

| Not yet | Reason |
|---|---|
| Dose recommendations or suitability statements | Not validated. Patient-specific dosing output can also fall under clinical-decision-support / device regulation. Show exposure, never advice. |
| PBPK organ compartments | Partition coefficients and organ flows are unsourced. A checked one-compartment model is worth more than an unchecked organ model. |
| PD, efficacy, toxicity | No exposure-response model has been selected or checked. |
| Pharmacogenomic inputs for lenalidomide | Minimal CYP metabolism; a genotype input would be decorative. |
| Multiple drugs or mechanistic interactions | One drug end to end first. |
| Real patient data | Synthetic only. |
| 3D anatomy, ML | Nothing to visualize beyond one compartment; no data that would justify ML. |

## Architecture (extends existing modules)

```
patient_state (v1) ─► covariate_estimation ─► pk_model_inputs ─► educational_pk ─► run record
 declared fields       formula registry         range checks        typical curve      provenance
 (origin, source)      weight-basis assessment  parameter preview   (2.0e: + BSV)
```

| Component | Module / data | Status |
|---|---|---|
| Patient state | `patient_state.py` | Existing, unchanged. Estimates are kept in a separate record keyed by the state SHA-256 rather than adding a `calculated` origin to the state schema. |
| Formula registry | `data/covariate_formula_registry_v1.json` | New (pinned). BMI, Janmahasatian FFM, Devine IBW, adjusted body weight (0.4), Cockcroft–Gault. |
| Covariate estimation | `covariate_estimation.py`, CLI `flask covariate-estimate` | New. Explicit weight basis, no default; coverage checks; side-by-side basis comparison. |
| Adapter to model inputs | `covariate_estimation.to_hughes_model_inputs` | Emits `hughes-model-inputs-v1` fields with `origin: assumption` and the estimate SHA-256 in `source_ref`. |
| Estimated PK run | `estimated_pk.py`, `educational_pk_runs.save_estimated_pk_run`, `landscape_ui/estimated_pk_pages.py` | 2.0d. Revision → estimate → existing calculation; v2 saved runs archive the estimate. |
| Variability | `data/hughes_variability_extract_v1.json` | New (pinned). OMEGA matrix from the final control stream; not yet used by a simulation. |
| Weight-basis assessment | `data/hughes_weight_basis_assessment_v1.json`, `scripts/reconstruct_hughes_crcl_weight_basis.py` | New (pinned). See below. |

## Phases

| Step | Deliverable | Status |
|---|---|---|
| 2.0a | Model selection | Done. Hughes 2019 is the first executable model: open access, full parameter table and control stream, covariates match the state. Kim 2026 (renal impairment, unbound drug, two compartments) is the candidate for a later renal-impairment model once its final tables are transcribed. Connarn stays a comparator until its supplement is available. |
| 2.0b | Formula registry and covariate estimation | Delivered in this change. |
| 2.0c | Covariate resolution and applicability | Done. Range checks in `pk_model_inputs`; the estimate adds input and covariate coverage checks; saved v2 runs carry the estimate. |
| 2.0d | Individualized typical-value run | Done. `estimated_pk.py` estimates covariates from a saved revision and runs `educational_pk` unchanged; `save_estimated_pk_run` stores `saved-educational-pk-run-v2` with the estimate, verified on every read. Page: `…/revisions/<id>/estimated-pk` (ideal body weight preselected and labelled; compare-all-bases overlay). CLI: `patient-pk-estimated`, `patient-pk-save-estimated`. |
| 2.0e | Population mode | Done. `population_pk.py` draws seeded (η_CL, η_V) jointly from the OMEGA block and η_KTR independently, solves each virtual patient exactly (closed-form transit chain, verified against the numerical solver to < 1e-9 in every regime and against the typical curve on every run) and reports 5/25/50/75/95th percentile bands plus AUC and peak distributions. Page action "Show population band"; CLI `patient-pk-population`. Excludes residual error, parameter uncertainty and between-occasion variability (stated in every report). |
| 2.0f | Run record and UI | Next. Provenance panel, applicability badges, weight-basis toggle, persistent "simulated, synthetic, not a clinical prediction" banner. |
| 2.0g | Reproduction check | Compare predicted exposure by renal group with the Dahut 2009 groups already in `lenalidomide_pk_v1.json`; record pass, fail or discrepancy in the validation-gap register. Expect under-prediction in severe impairment (see below). |

## Typical value vs individual prediction (2.0d)

A 2.0d curve is the model's **typical value for a patient with these covariates**: every random effect (η) is zero. It is not an individual prediction. Predicting a specific person requires that person's measured concentrations and Bayesian (MAP) estimation, which is out of scope. Two patients with identical covariates can differ about twofold in exposure (CL/F between-subject variability ≈ 54% CV), which is why 2.0e adds the population band.

## The population band (2.0e)

The band answers: how far would patients with exactly these covariates spread around the typical curve under this model? For the example record (three daily 5 mg requests), median AUC matched the typical value (1661 vs 1660 ng·h/mL) and the 5th–95th percentile range spanned about 5.7-fold, which is what ω²_CL = 0.296 implies (exp(2 × 1.645 × 0.544) ≈ 6).

Two points worth keeping in view:
- The band is model-implied variability, not uncertainty about the model. It omits residual error (relevant when comparing with observed concentrations), uncertainty in the published estimates, and anything the model leaves out.
- Between-subject variability dwarfs the unresolved weight-basis effect (≈ 6-fold vs ≈ 1.06-fold for the example). The weight basis matters for traceability far more than for the numbers.

## Scientific notes recorded during 2.0a/2.0b

- **No study patient had CrCl below 36 mL/min** (Table 1 range 36–211; inclusion required serum creatinine < 177 µmol/L). The abstract's "22% lower clearance below 30 mL/min" is the equation extrapolated. Below 36 mL/min every output is extrapolation.
- **The renal effect is weak by construction**: CL/F ∝ (CrCl/90)^0.224. Dedicated renal-impairment studies show a much larger effect; the authors attribute the flat curve to tubular secretion. Treat this as a model property to test in 2.0g, not a settled fact.
- **Reference values are 55 kg and 90 mL/min** (Table 2 and the control stream), not the Table 1 medians (58.4, 75.5) that Equation 2 implies. Equation 4 omits the FFM term; Table 2 is authoritative.
- **Variability convention resolved**: Table 2 %CV = 100·√ω² (0.296 → 54.4%). Use the OMEGA matrix directly. CL/F and V/F random effects correlate at 0.862 and must be sampled jointly; independent sampling would invent half-life spread.

### Cockcroft–Gault weight basis

The paper cites Cockcroft–Gault without a weight basis. The control stream reads CrCl as a precomputed column (`CRCL2`) normalized by 90, commented as the mean.

A virtual population matched to Table 1 (checked independently: simulated FFM 57.5 kg vs reported 57.7 kg) gives these CrCl means: total body weight ≈ 110, adjusted ≈ 93, **ideal ≈ 82**, FFM ≈ 72 mL/min, against a reported 80.1. Ideal body weight matches Table 1 in all tested scenarios; adjusted weight is not excluded because it agrees with the control stream's "mean 90" comment; total body weight is disfavored.

Decision: primary assumption `ideal_body_weight_devine`, labeled `inferred_by_population_reconstruction`, with adjusted and total body weight as sensitivity branches. Every estimate carries its basis and evidence level. For this model the choice moves typical CL/F by only about 6% for a 30% CrCl spread, because of the 0.224 exponent.

Resolution path: ask the corresponding author what weight produced `CRCL2` and whether a cap applied. A documented answer becomes a new assessment version.

## Validation layers (kept separate)

1. Software verification — the code computes the intended equations (worked-example tests, pinned sources).
2. Transcription verification — parameters match the paper and control stream.
3. Reproduction — the model reproduces its own published results.
4. External consistency — agreement with data not used to fit it (Dahut renal groups, if independent of the fitting data).

Passing all four supports research use. `clinical_prediction_validated` stays false.
