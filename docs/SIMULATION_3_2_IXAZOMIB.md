# Simulation 3.2a — ixazomib: Gupta 2017 population PK model, checked against the renal and hepatic impairment studies

Exploratory external consistency check. Not validation, not a dosing tool, and nothing on the platform changes because of it.

## Why ixazomib

Lenalidomide (Hughes, Kim) and bortezomib (Iwasaki) are each waiting on author replies. Ixazomib is the next-best test case for the platform's kidney and liver chain:

- It is oral, so it tests absorption (lag, first-order absorption, bioavailability), which no registered model covers yet.
- Its population model (Gupta 2017) is open access and fully tabulated: every parameter, the between-patient variability, and the ten studies it was built from.
- Two dedicated studies, in severe renal impairment/ESRD and in moderate/severe hepatic impairment, are **not** among those ten studies. They are an outside check, and both changed the label (3 mg starting dose).

## Sources (pinned)

| File | Content | Checksum (first 8) |
|---|---|---|
| `intelligence_store/data/ixazomib_pk_gupta_2017_extract_v1.json` | Model structure, Table 3 parameters, covariates, studies used | d4fe97e4 |
| `intelligence_store/data/ixazomib_impairment_observed_v1.json` | Renal study Tables II-III (Gupta, Br J Haematol 2016); hepatic study Tables 2-3 (Gupta, Br J Clin Pharmacol 2016) | 95fbf4c6 |
| `intelligence_store/data/ixazomib_pk_gupta_check_plan_v1.json` | Plan v1.0, locked in commit `982044c` before any concentration was computed | 9b8ef3d8 |
| `intelligence_store/data/ixazomib_pk_gupta_check_plan_v1_1.json` | Plan v1.1 = v1.0 + amendment 1, locked in commit `63c97f1` before any group result | 2c910747 |
| `docs/verification/ixazomib_pk_gupta_check_v1.json` | Locked report (regenerated exactly by its test) | report_sha256 dcaae11c |

All tables were read from the rendered page images. The renal article's text layer drops decimal points, for example "258" for 25.8 ng/mL.

## The model, in plain terms

Three compartments:
- **Central (V2 = 13.7 L)**, which is the plasma;
- a **slow peripheral compartment (V3 = 309 L)** and a **faster one (V4 = 205 L)**, which are tissues that take up the drug and release it back.

Oral doses wait 13 minutes (lag), then enter at a first-order rate (Ka = 0.34/h, absorption half-time about 2 h). 58% of the dose reaches the circulation (F). Clearance from the central compartment is 1.86 L/h.

The very large peripheral volumes explain the long terminal half-life, about 9.5 days. Most of the drug sits in tissue, and only a small fraction is in plasma to be cleared at any moment.

The only covariate is body surface area, on V4. The form V4 × (BSA/1.87)^2.06 is inferred from the stated −37%/+46% effects, which it reproduces exactly.

The model has **no kidney or liver covariate**. It gives the same exposure whatever the organ function. That is what this check probes.

**Solving it.** The platform solves the model in closed form, without step-by-step integration. The response to a dose in plasma is a sum of three exponentials, one per disposition rate. The rates are the roots of a cubic equation: 2.52, 0.037 and 0.0031 per hour, half-lives 0.27 h, 19 h and 9.4 days. Oral input is that response convolved with first-order absorption. The closed form matched fourth-order Runge-Kutta integration to 5×10⁻¹² relative, its AUC equalled F·dose/CL, and mass balanced to 10⁻¹⁴.

## How the check works

Each virtual trial simulates both studies at their reported group sizes, doses and sampling times:
- kidney study: 3 mg in all groups;
- liver study: 4, 2.3 and 1.5 mg.

Each simulated patient gets their own clearance, bioavailability (correlated with clearance, r = 0.82) and V4, drawn from the model's between-patient variability. Their concentrations go through the same calculation the studies used: Cmax is the highest sample, and AUC0-last runs to the last sample at or above 0.5 ng/mL.

Each group's geometric mean is computed, and 2,000 trials give the range a group of that size would show if the model were right. An observed value outside the 5th–95th percentile is classified as over- or under-predicted.

There are six scenarios:
- the primary one;
- the % CV read as ω;
- F capped at 1;
- BSA 1.5 m² and BSA 2.25 m²;
- log-down trapezoids.

Plan v1.0 did not say what to do with a simulated patient with no quantifiable sample. The first run stopped on one before any group result existed. Amendment 1, locked before rerunning, treats patients with fewer than 3 quantifiable samples as not PK-evaluable and replaces them, as the studies did. Three patients were replaced in 2,000 primary trials, all in the 1.5 mg group.

## Results (primary scenario)

| Group | Observed AUC0-last (GM) | Model, 5th–95th percentile | Result | Robust |
|---|---|---|---|---|
| Kidney study, normal (MM), 3 mg | 575 | 445–755 (median 596) | **consistent** | yes |
| Severe renal impairment, 3 mg | 813 | 402–800 | under-predicts | no (consistent in 2 of 6) |
| ESRD on dialysis, 3 mg | 783 | 360–855 | consistent | no |
| Liver study, normal (solid tumours), 4 mg | 1160 | 610–1037 | **under-predicts** | yes |
| Moderate hepatic impairment, 2.3 mg | 846 | 278–602 | under-predicts | yes |
| Severe hepatic impairment, 1.5 mg | 489 | 117–335 | under-predicts | yes |

| Impaired / normal AUC0-last | Observed | Model with no organ effect, 5th–95th | Result |
|---|---|---|---|
| Severe renal impairment | 1.41 | 0.63–1.52 | not distinguishable from no effect at n = 10 vs 15 |
| ESRD | 1.36 | 0.59–1.61 | same, n = 6 |
| Moderate hepatic (dose-normalised) | 1.27 | 0.57–1.42 | same |
| Severe hepatic (dose-normalised) | 1.12 | 0.37–1.21 | same |

The **locked decision** is consistent with one normal-function group: the MM group, robustly. The model is not proposed for registration, because the rule required both normal groups.

## What this means

1. **Exposure in myeloma patients with normal kidney function matches.** The observed 575 h·ng/mL is 0.97 × the model median, in all six scenarios. This is the population the model was built on: mostly MM, oral.
2. **Solid-tumour patients have about 40% more exposure than the model predicts**, even with normal liver function. The two normal groups differ by 1.51× after dose normalisation, at the edge of what chance allows (simulated 95th percentile 1.50). The model's oral data are almost all MM; its 80 solid-tumour patients received IV ixazomib, so they inform clearance but not oral bioavailability. A population difference in absorption or bioavailability is a plausible reading. It is not tested here.
3. **The impairment ratios cannot separate an effect from chance at these group sizes.** With 6–15 patients per group and 40–80% variability, a model with no organ effect produces ratios from about 0.6 to 1.5. This is **not evidence of no effect**:
   - The study's own pooled analysis (severe RI + ESRD vs normal, total AUC 1.39, 90% CI 1.04–1.86) excludes 1.
   - The label lowers the dose.

   What the check shows is narrower: these single studies alone cannot test an organ-function covariate with confidence.
4. **Peaks are under-predicted 2–4× in five of six groups, robustly.** The likely reason is in the model's own design rather than a transcription error: its residual error is on the log scale and starts at SD 1.90, falling to 0.46 with a half-life of 50 minutes (equation 3, Table 3). At 1 h after the dose that SD is still about 1.1, so one SD of unexplained noise is a factor of about 3 either way. It was built to describe exposure over time, not peaks.

   **Correction to the plan.** The plan's known-differences note said leaving out residual error matters little for geometric means. That holds for a single concentration but not for Cmax, which is the highest of several noisy samples. This model should not be used for Cmax.
5. **Bioavailability above 100%.** About 20% of simulated patients have F > 1, because the published form is log-normal and unbounded. Capping F at 1 changed no classification.

## What the platform does with this

Nothing yet:
- The ixazomib model is not registered and has no patient-facing output.
- If it is registered later, its applicability would be AUC (not Cmax), in MM patients, inside the model's covariate range (creatinine clearance down to about 30 mL/min, mild hepatic impairment).
- Severe renal impairment, ESRD and moderate or severe hepatic impairment would be shown as outside applicability, with the observed study values.
- Registration would be a separate step with its own record.

## Open items

- **Independent review** of the three transcriptions.
- **Supplementary Tables 2–3 of Gupta 2017** (the covariate tests) were not reviewed.
- **Two unexplained details in the article:**
  - steady-state volume 543 L vs 527.7 L from Table 3;
  - Table 2 median BSA 1.88 vs 1.87 m² in Table 3.
- **A Cmax analysis with the model's residual error** would be a new, separately planned step, not a change to this one.
