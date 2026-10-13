# Patient Lab 2.0 — covariate-aware virtual patient

Recorded 13 October 2026. Owner: Astrid. Status: in progress (2.0a done, 2.0b delivered in this change).

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
| Adapter to model inputs | `covariate_estimation.to_hughes_model_inputs` | New. Emits `hughes-model-inputs-v1` fields with `origin: assumption` and the estimate SHA-256 in `source_ref`. |
| Variability | `data/hughes_variability_extract_v1.json` | New (pinned). OMEGA matrix from the final control stream; not yet used by a simulation. |
| Weight-basis assessment | `data/hughes_weight_basis_assessment_v1.json`, `scripts/reconstruct_hughes_crcl_weight_basis.py` | New (pinned). See below. |

## Phases

| Step | Deliverable | Status |
|---|---|---|
| 2.0a | Model selection | Done. Hughes 2019 is the first executable model: open access, full parameter table and control stream, covariates match the state. Kim 2026 (renal impairment, unbound drug, two compartments) is the candidate for a later renal-impairment model once its final tables are transcribed. Connarn stays a comparator until its supplement is available. |
| 2.0b | Formula registry and covariate estimation | Delivered in this change. |
| 2.0c | Covariate resolution and applicability | Range checks exist in `pk_model_inputs`; the estimate adds input and covariate coverage checks. Remaining: carry estimate provenance into saved runs. |
| 2.0d | Individualized typical-value run | Next. Feed `to_hughes_model_inputs` output into `educational_pk` and archive the estimate with the run. |
| 2.0e | Population mode | Sample (eta_CL, eta_V) jointly from the OMEGA block and eta_KTR separately; seeded; percentile bands. |
| 2.0f | Run record and UI | Provenance panel, applicability badges, weight-basis toggle, persistent "simulated, synthetic, not a clinical prediction" banner. |
| 2.0g | Reproduction check | Compare predicted exposure by renal group with the Dahut 2009 groups already in `lenalidomide_pk_v1.json`; record pass, fail or discrepancy in the validation-gap register. Expect under-prediction in severe impairment (see below). |

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
