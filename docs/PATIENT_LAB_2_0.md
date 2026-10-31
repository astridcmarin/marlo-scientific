# Patient Lab 2.0 — covariate-aware virtual patient

Recorded 13 October 2026. Owner: Astrid. Status: 2.0a–2.0g done; 2.1 (Kim 2026) and 2.2 (platelets and the bortezomib curve for a patient) done.

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
| 2.0f | Run record and UI | Done for the three Patient Lab result pages (Hughes educational PK, saved Kim run, bortezomib platelets for a patient): one shared banner and one run-record panel. The weight-basis toggle already existed (2.0d). See "Run record (2.0f)" below. |
| 2.0g | Reproduction check | Done as an exploratory aggregate consistency check against study CC-5013-PK-001 (the renal-group data in `landscape_ui/data/renal_pk/`, extracted from the EMA assessment of Chen et al. 2007; earlier notes called this "Dahut", which was wrong). Plan locked and committed before computation (`hughes_renal_group_check_plan_v1.json`); report `docs/verification/hughes_renal_group_check_v1.json`; CLI `hughes-renal-group-check`. Result below. |

## Renal-group consistency check (2.0g)

Question: do group-mean exposures observed across renal-function groups fall within the range the Hughes model predicts for a study of the same design? Method: 10,000 simulated replicates of the study (single 25 mg dose, reported group sizes, creatinine-clearance ranges, Hughes between-subject variability); a group is *consistent* if its observed mean lies within the simulated 5th–95th percentile. Primary endpoint: AUC∞ relative to the normal group.

| Group (CrCl, mL/min) | Observed AUC ratio | Simulated 90% range | Classification | Observed ÷ median |
|---|---|---|---|---|
| Normal (>80) | — (absolute 2181 vs 1589–3334 ng·h/mL) | | consistent | |
| Mild (50–80) | 1.27 | 0.63–1.94 | consistent | 1.15 |
| Moderate (30–50) | 2.76 | 0.74–2.11 | model under-predicts | 2.2 |
| Severe (<30) | 3.76 | 0.85–2.55 | model under-predicts | 2.6 |

Identical classification in all four prespecified scenarios. Terminal half-life agrees with the same picture (observed ≈ 9–11 h vs ≈ 5–6 h simulated below 50 mL/min).

Interpretation: the model's weak renal exponent (0.224) holds down to about 50 mL/min and fails below it, including part of its own reported data range (36–50 mL/min). Consequence in the platform: `hughes_applicability_findings_v1.json` adds a warning to every covariate estimate with CrCl < 50 mL/min; calculations still run. This is an exploratory finding from aggregate data, not validation. The natural next model for reduced renal function is Kim 2026 (renally impaired MM patients, unbound and total concentrations), once its final tables are transcribed.

## 2.1 — Kim 2026 as a second model (renal impairment)

Motivated by 2.0g. Kim et al. (Drug Des Devel Ther 2026;20, doi 10.2147/DDDT.S605741) modelled total and unbound lenalidomide in 30 Korean multiple myeloma patients spanning eGFR 11–95 mL/min/1.73 m², sampled at steady state on 5–10 mg/day.

- **Model** (`kim_2026_model_extract_v1.json`, pinned): two compartments, first-order absorption (Ka 1.16 h⁻¹ fixed), parameters on the **unbound** scale; total = unbound ÷ Fu (0.614). Covariates: CKD-EPI 2021 eGFR (indexed) and Du Bois BSA. The 2025 conference abstract is superseded and not used.
- **Equation-form problem.** The printed CL/F equation adds the BSA term outside the exponential (in L/h), which makes body size nearly irrelevant and reverses the paper's own reported dose-escalation results. Both multiplicative readings reproduce them (`kim_cl_equation_form_assessment_v1.json`, script `scripts/assess_kim_cl_equation_form.py`). Primary reading: linear multiplicative; the form is an explicit argument with no default, and status stays *unresolved* until the authors confirm.
- **Formulas.** `covariate_formula_registry_v2.json` adds CKD-EPI 2021 and Du Bois BSA; every v1 formula is unchanged and v1 stays in the repository as the record behind earlier estimates.
- **Engine** (`kim_model.py`): exact two-compartment oral solution with superposition, unbound and total curves; checked against an independent RK4 integration, near-coincident rates and AUC = dose/CL. Scope: MM only, study doses 5/7.5/10 mg, same schedule limits as Hughes. CLI `patient-pk-kim`.
- **Internal reproduction** (`kim-internal-reproduction`): typical total CL/F at each group's median covariates lies within one SD of the authors' Table 2 group means for all three readings (severe 3.76 vs 3.39, moderate 5.66 vs 5.74, control 8.74 vs 8.01 L/h). Same patients as the fit, so this confirms transcription and the unbound→total conversion, not predictive performance.
- **Model comparison** (`pk-model-compare`): for a 68-year-old 70 kg woman on 10 mg, the two models agree at normal renal function (Kim/Hughes AUC 0.98) and diverge as it falls (1.38 at eGFR 47, 1.63 at 26, 1.70 at 14) — the direction the 2.0g check found missing from Hughes.

**2.1b — Hughes and Kim on the page.** The estimated-PK page has a “Compare Hughes and Kim” action and a selector for the Kim CL/F reading (primary preselected, the others labelled as sensitivity readings). Both models run on the same saved record and request; each estimates its own covariates and keeps its own assumption, warnings and blockers. A model that cannot run is shown as not run with the reason, never replaced by the other. In practice:
- the two studies share only 5 and 7.5 mg, so only those doses run both models;
- Kim needs the MM context;
- Hughes refuses estimated CrCl below its study minimum (36 mL/min), so in severe impairment only Kim runs. That is extrapolation avoided, not a missing feature.
The overlay shows both total curves and Kim's unbound curve; Hughes's transit delay and Kim's peripheral-compartment accumulation are visible in it.

**2.1c — External check of Kim against CC-5013-PK-001.** This is the same exploratory design as 2.0g: the plan (`kim_renal_group_check_plan_v1.json`) was committed and pinned before any virtual trial of this design ran, and the report is `docs/verification/kim_renal_group_check_v1.json` (CLI `kim-renal-group-check`).

The study reports only creatinine-clearance ranges, so each virtual subject gets assumed demographics. Serum creatinine is back-solved from Cockcroft–Gault, and eGFR and BSA then follow from that same subject. This construction is the largest assumption in the check:
- About 60% of simulated normal-group subjects have an eGFR above Kim's data (94.7), where its exponential renal effect is extrapolated.
- About a third of the severe group falls below 11.1.

Primary endpoint (each group's AUC ÷ the normal group's), observed vs Kim's simulated median:

| Group | Observed | Kim median (5th–95th) | Classification | Hughes, observed ÷ median |
|---|---|---|---|---|
| Mild | 1.27 | 1.62 (1.26–2.06) | consistent | 1.15 (consistent) |
| Moderate | 2.76 | 2.24 (1.80–2.78) | consistent, at the edge | 2.22 (under-predicts) |
| Severe | 3.76 | 2.84 (2.27–3.54) | under-predicts, about 1.3× | 2.56 (under-predicts) |

Across the seven scenarios, mild is consistent in every one. Moderate and severe switch between consistent and under-predicts depending on the assumptions; the severe group passes only when CrCl is assumed computed from ideal body weight or Korean body size is used. Absolute AUC: normal consistent, moderate and severe about 1.3–1.4× above Kim's median. Terminal half-life, which Hughes put at about 5–6 h against an observed 9–11 h, is reproduced in the severe group (9.5 vs 9.2 h) but under-predicted in moderate (7.6 vs 10.6 h).

Reading: Kim describes the renal effect much better than Hughes, but likely still somewhat under-predicts exposure in severe impairment.

**2.1d — Review outcome and dose evidence.** The 2.1c result was reviewed with the platform owner on 2026-10-14, and two records were added.
- **Kim finding** (`kim_applicability_findings_v1.json`): severe impairment only. Kim estimates with eGFR below 30 now carry a warning that exposure may be under-predicted by roughly 1.2–1.5-fold. That range is what all seven scenarios span; Kim under-predicted in 5 of them. Moderate impairment is not warned. The threshold is Kim's own severe boundary and corresponds only approximately to the study's CrCl < 30 group.
- **Dose proportionality** (`lenalidomide_dose_proportionality_evidence_v1.json`). Source: page 20 of the pinned EMA report already in the repository, which says exposure is dose-proportional over 5–400 mg; a test checks the quotes against the PDF. The FDA label section 12.3 says the same, but was read only through a mirror. This resolves the 2.1c known difference about scaling from Kim's 5–10 mg to the study's 25 mg.
- **Noted, not acted on:** the label gives protein binding of about 30% (Fu ≈ 0.7), while Kim estimated 0.614. This is for a later review of the unbound-to-total conversion.

**2.1e — Recheck of both models with study-matched virtual subjects (2026-10-31).** The 2.0g and 2.1c checks gave every virtual subject assumed demographics, which 2.1c called its largest assumption. The study publication (Chen et al. 2007, Table I, recorded in `lenalidomide_renal_source_reconciliation_v3.json`) gives each group's sex counts and the ranges of age, weight and measured creatinine clearance. The recheck draws virtual subjects from those, with the exact sex counts, and keeps the observed data, endpoint and decision rule of the first checks. Heights are still assumed (men 165–185 cm, women 152–172 cm). The plan (`lenalidomide_renal_recheck_plan_v1.json`) was committed and pushed at d163781 before computation; report `docs/verification/lenalidomide_renal_recheck_v1.json`; CLI `lenalidomide-renal-recheck`. Four scenarios, 10,000 virtual trials each.

Primary endpoint (each group's AUC ÷ the normal group's), observed vs simulated median (5th–95th percentile), primary scenario:

| Group | Observed | Hughes | Kim | Change from the first check |
|---|---|---|---|---|
| Mild | 1.27 | 1.14 (0.65–1.98), consistent | 1.50 (1.20–1.86), consistent | none |
| Moderate | 2.76 | 1.11 (0.66–1.88), under-predicts | 2.09 (1.71–2.57), under-predicts | **Kim: consistent → under-predicts** |
| Severe | 3.76 | 1.57 (0.93–2.69), under-predicts | 2.91 (2.38–3.58), under-predicts | none |

Every classification is the same in all four scenarios. Absolute AUC in the normal group is consistent for both models. About half of the simulated normal-group eGFR values (54%) still lie above Kim's data (94.7 mL/min/1.73 m²).

Reading: with subjects that look like the study's, Kim under-predicts the moderate group by about 1.3-fold as well as the severe group, and no longer passes in any scenario. The first check's consistent moderate result depended on virtual subjects who did not match the study. Hughes is unchanged. The study population had non-malignant renal impairment, so this says how the models extrapolate to that population; it is not a check in myeloma patients.

What this does not change by itself: the plan's decision rule says scope and warnings change only in a separate, documented step. The Kim finding (`kim_applicability_findings_v1.json`) still warns only below eGFR 30. Extending the warning to the moderate band is proposed, not done.

**Evidence scan: exposure–response (2026-10-14).** Before building any drug-effect module, I searched for a published, transcribable model linking lenalidomide exposure to neutrophil or platelet counts over time. None was found:
- **Chen, Zhou & Palmisano (Clin Pharmacokinet 2017)** summarise a pooled six-study analysis. AUC predicted grade 3/4 thrombocytopenia (odds ratio 3.34, 95% CI 1.18–9.42), and the neutropenia link was not clearly established (odds ratio 1.98, CI 1.00–3.92). Neither was apparent in cycle 1. The review does not give the AUC units or baseline risk, so the probability model cannot be reconstructed.
- **Guglieri-López et al. (Cancer Chemother Pharmacol 2017; 15 patients)** is PK only. It has one compartment, three transit stages, CrCl on CL/F and BSA on V/F. It is not implemented: Hughes has a similar structure, and 15 patients is too few to rely on the covariate estimates. Its claim that the model can individualise dose is not adopted. The associated thesis (Valencia 2017) may contain PK/PD work; it is unread.
- **Mechanistic neutropenia models exist for a related cereblon modulator (avadomide).** Transferring their parameters to lenalidomide would be borrowing biology from a different molecule.

Decision: no blood-count time-course module. Revisit if the full pooled exposure–safety analysis can be obtained.

**Thesis review (Guglieri-López, Universitat de València 2017; reviewed 2026-10-14 from the platform owner's local copy, not stored in the repository).** 54 myeloma patients at one hospital, observational; 15 contributed PK samples. Two exposure–response analyses, both time-to-event:
- **Time to severe (grade 3/4) neutropenia** (section 5.3.2.2; Table 5.21; model file in appendix 8.7.3). 27 of 54 patients had an event within 600 days. The model uses a constant hazard modified by:
  - baseline neutrophil count: hazard ratio 0.78 per 10⁹/L
  - age: 1.04 per year
  - Cmax: 1.02 per 10 ng/mL (95% CI 1.01–1.03)

  AUC was not significant (p = 0.39), unlike the Celgene pooled analysis.

  Not implemented, for four reasons:
  - The final baseline hazard is not reported; the model file shows only the initial estimate. So absolute risk over time cannot be computed.
  - Cmax for 65% of patients was a typical value from the 15-patient PK model, whose absorption rate the thesis itself says was poorly estimated.
  - The effect is tied to that PK model's Cmax, not to Hughes or Kim.
  - The author advises caution because the confidence intervals sit close to 1.

  Thrombocytopenia was too rare to model (fewer than 10% of patients).
- **Time to progression** (section 5.3.2.1; Table 5.17). Above an AUC of 1,110 ng·h/mL, progression risk rose by a hazard ratio of 1.19 per 100 ng·h/mL. Higher exposure going with faster progression is very likely confounding in observational data (renal function, disease severity, dose changes), not a drug effect. It will not be presented as exposure → efficacy.
- **Use:** evidence for the knowledge layer only. In this single-centre cohort, low baseline neutrophils and older age were the main risk factors for severe neutropenia, and the drug-exposure effect was weak. The pooled Celgene analysis (ASH 2013 abstract 3234) remains the only lead for an exposure–safety model.

**2.1e — Comparison with a measured reference exposure.** The Hughes–Kim comparison now shows each model's typical daily AUC divided by the mean AUC measured after the approved 25 mg starting dose in subjects with normal renal function (CC-5013-PK-001: 2181 ± 703 ng·h/mL, n = 7; `lenalidomide_reference_exposure_v1.json`).
- **Why it compares like with like:** dose proportionality makes a single-dose AUC equal to one day's AUC on daily dosing.
- **Why the reference is fair to both models:** each reproduced this normal-group value in its renal check (observed ÷ median: Hughes 0.95, Kim 1.06).
- **Regulatory context:** the renal dose reductions were described as aiming for comparable daily AUC. This is a secondary source, Chen 2017, not checked against its full text.
- **What it is not:** the ratio carries no band, target, toxicity prediction or dose recommendation, and the page says so beside it.

Example, moderate impairment on 7.5 mg daily: Hughes 0.42, Kim 0.60. The models disagree about where this patient sits relative to the reference, and the disagreement itself is the information.

**2.1f — Saved Kim runs.** Kim runs are saved from the estimated-PK page (“Calculate and save Kim 2026 run”) or the CLI (`patient-pk-save-kim`, `patient-pk-export-kim`). They live in their own table, `kim_pk_run`, created by migration `585bc7cb8d18`. They are kept apart because every existing saved-run reader expects the Hughes report structure.
- **What is archived:** the full report, including the eGFR/BSA estimate, the CL/F reading with its evidence, and the warnings shown at save time.
- **Verification on every read:** the report and estimate checksums, the link to the patient-state record, the request, and the validation flags. The model is never re-run.
- **Not saved:** blocked calculations (a dose outside the study, a non-MM context, missing inputs).

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

## Run record (2.0f)

Every Patient Lab result page now opens with the same banner and ends with the same run record, so a result is never read without its provenance.

- **Banner** (`run_record_macros.html`, `simulation_banner`): "Simulated · Synthetic patient record · Not a clinical prediction", what kind of result this is, what it is *not*, and both validation flags (false). Two result types are defined in `intelligence_store/run_record.py`: a typical-value concentration curve and a hypothetical typical effect curve.
- **Run record** (`patient-lab-run-record-v1`, built by `run_record.py`, shown by `run_record_panel`):
  - model, citation and DOI;
  - the patient record used (revision, schema, checksum), each input with its origin, and each derived input with its formula and version;
  - assumptions, each with the reading used, its status (unresolved, assumed, settled by a locked check, by design, fixed) and its basis;
  - coverage of the source data ("within reported range", "outside", "below entry threshold") and warnings;
  - **what has been checked about the model**, in the four validation layers below;
  - limitations and every checksum, plus a checksum of the record itself.
- **Nothing is recalculated.** The record copies values from the page's report and from pinned files; the tests check that it is deterministic and that its fields match the report.
- **Model evidence status** (`model_evidence_status_v1.json`, pinned): per model and layer, done / partial / not done, with a one-line finding. Where a verification report is cited, the tests check its file checksum and that the quoted classification and per-group results are the ones in the report. Current state:

| Model | Software | Transcription | Reproduction | External consistency |
|---|---|---|---|---|
| Hughes 2019 | done | partial (control stream not retrieved) | not done | exploratory: mild consistent; moderate, severe under-predicted |
| Kim 2026 | done | done, CL/F form open | done (Table 2 group CL/F) | exploratory: mild, moderate consistent; severe under-predicted (primary scenario) |
| Lignet 2022 (platelets) | done | partial (independent review pending) | done (locked check, fitting data) | not done; searched, no usable outside data (see below) |
| Lignet 2022 PK component (drives the platelet model) | done | partial | not done | exploratory (Ogawa 2008): day 11 exposure consistent; day 1 2.9-fold too high; day 1 → 11 rise 1.9- vs 5.1-fold |

**Search for outside platelet data (15 October 2026, evidence status v1.1, `model_evidence_status_v2.json`).** The only candidate found is the Japanese phase I/II study (NCT00752518; Ogawa et al., *Cancer Sci* 2008; sponsor report CR009058; 0.7, 1.0 and 1.3 mg/m² on the same schedule). Neither the paper nor the public synopsis gives platelet counts over time (the paper reports thrombocytopenia only by grade: grade 3/4 in 11 of 25 patients at 1.3 mg/m²); the full report, which tabulated hematology values by testing time, is not public. Incidences alone are not used, because a typical curve without between-patient spread cannot predict how many patients cross a threshold. A possible route is a data request through the sponsor's data-sharing program (YODA Project for Janssen).

The table is the honest summary of the platform's evidence today: no model has external consistency at the individual level, and none is validated for clinical prediction.

## Validation layers (kept separate)

1. Software verification — the code computes the intended equations (worked-example tests, pinned sources).
2. Transcription verification — parameters match the paper and control stream.
3. Reproduction — the model reproduces its own published results.
4. External consistency — agreement with data not used to fit it (done for the CC-5013-PK-001 renal groups in 2.0g, as an aggregate check; that study was not part of the Hughes dataset).

Passing all four supports research use. `clinical_prediction_validated` stays false.

## 2.2 — Baseline platelets and the bortezomib platelet curve for a patient

**2.2a, patient-state schema v2.** v2 adds `platelet_count` (10⁹/L); see `PATIENT_STATE_SCHEMA.md`. v1 revisions are untouched: same canonical form, same checksums.

**2.2b, page `…/patient-state/revisions/<id>/bortezomib-platelets`.** It is linked from the patient-state record page.
- **How the curve is drawn.** The Simulation 3.0 platelet model is exactly scale-invariant: all compartments start at baseline, the feedback uses the ratio baseline/current, and the drug term does not involve counts. Its fraction-of-baseline curve is therefore identical for any starting count; this is tested at 40, 171 and 400 ×10⁹/L. A patient's typical absolute curve is their baseline × that fraction.
- **The same pattern in the data.** Lonial 2005 found the mean percentage fall independent of baseline. A low start therefore reaches low absolute counts sooner, which fits the observed risk depending strongly on baseline.
- **Observed context** (`bortezomib_platelet_context_v1.json`, pinned; quotes checked against the source text):
  - grading as the source used it (NCI CTC v2.0: grade 2 from 50 to under 75, grade 3 from 10 to under 50, grade 4 under 10). The incidences below use this definition, so it is kept as the primary grading; current CTCAE v5.0 grades are added alongside (see below);
  - entry thresholds (50, or 30 with extensive marrow involvement);
  - incidences: 42% any grade and 30% grade 3/4, overall; grade 4 in 24% of patients with a baseline under 70 versus at most 1% above;
  - the roughly 60% average individual fall, drawn as an illustrative line.
- **Current grading as well** (`platelet_grading_ctcae_v5_v1.json`, pinned; read from the NCI CTCAE v5.0 PDF, page 83, with every boundary checked against its text). Grades 1–2 match CTC v2.0. Grade 3 is 25 to under 50 (v2.0: 10 to under 50) and grade 4 is under 25 (v2.0: under 10). The page draws the v5.0 grade-4 line separately and gives each variant's lowest typical point under both systems. Lonial's "grade 4" (under 10) is a deeper fall than today's grade 4, so its 24% figure would be larger under v5.0 definitions.
- **Interpretation on the page.** The typical curve dips less than individual patients do, because averaging smooths dips that happen on different days. The grade lines are references, not this patient's grade. The observed incidence for the patient's baseline is presented as the better guide to risk.
- **Not run:** a record without a platelet count (any v1 record) gets an explanation and a link to add one; a baseline below the source's entry thresholds gets a warning.

