# Simulation 4.0 — evidence scan and 4.0a (relative odds of severe cytopenia)

Recorded 16 October 2026. This is a literature check only; nothing was built.

## Why a scan first

Simulation 4.0 links a patient's own exposure to a drug effect over time. For lenalidomide, which has the two best-checked PK models, no usable exposure–effect model exists (`PATIENT_LAB_2_0.md`, evidence scan of 14 October). The pooled exposure–safety analysis cannot be reconstructed, the Guglieri hazard model lacks its baseline hazard, and every quantitative mechanism input is still missing. Building lenalidomide PK/PD now would mean inventing the effect half.

**Criteria for a candidate:**
- one of the nine curated drugs;
- a published effect-over-time model with every equation and parameter reported;
- the effect for a patient changes with patient characteristics, not only with the dose;
- outside data exist, or could exist, to check it.

## Candidates

| Drug | Exposure model | Effect model | Verdict |
|---|---|---|---|
| Lenalidomide | Hughes 2019, Kim 2026 (installed) | none usable | blocked (see above) |
| Pomalidomide | Li et al., *Clin Pharmacol Adv Appl* 2017;9:133–145 (open access; renal impairment; parameter tables are images) | none in that paper; *J Clin Pharmacol* 2020;60(8):1061–1075 has an exposure–response analysis, not read | PK only for now |
| Daratumumab | Luo et al., *J Clin Pharmacol* 2021;61(5):614–627 (open access): 2 compartments, linear plus saturable target-mediated clearance that falls over time, weight on volumes; final parameters in supplement Table S1, not obtained | graphical and logistic only (response rate against trough; adverse events against body weight); no neutropenia–exposure relationship found | no effect-over-time model |
| Melphalan | Nath et al., *Br J Clin Pharmacol* 2010 (open access; high-dose therapy; found by title only, not read) | not found in this scan | PK only for now |
| Carfilzomib | Ou et al., *J Clin Pharmacol* 2017;57(5):663–677, doi:10.1002/jcph.850 (population PK; used by Lignet). Paywalled; abstract read: **body surface area was the only significant covariate on clearance**, and no exposure–adverse-event relationship was found | **Lignet 2022, Table 2**: the same platelet model as bortezomib, fitted to **individual** platelet counts (Alsina et al.) with between-patient variability in the starting count. Myelosuppression variant: γ 0.35, MTT 82 h (within the published 37–134 h), Circ0 114, slope 0.014. Lignet reports this variant "described the observed data well". | **does not meet the patient-dependence criterion** (see below) |
| Bortezomib | Lignet 2022 PK (installed; 3.0f found first-dose exposure overstated) | Lignet 2022 platelets (installed) | installed; PK needs a time-dependent-clearance model |

## What this means

- **Carfilzomib fails the patient-dependence criterion.** Its platelet parameters are good: fitted to individual counts, with biologically plausible values. But carfilzomib is dosed per m², and body surface area is the only covariate on its clearance (Ou 2017 abstract). So every patient gets essentially the same concentration curve once dose is scaled to body size. The platelet model depends only on the starting count, so a carfilzomib patient simulation would add nothing beyond Patient Lab 2.2. It remains a possible second *drug-effect* module, for comparing drugs rather than patients.
- **No curated drug meets all four criteria today.** Where patient characteristics clearly change exposure (lenalidomide and renal function), the effect model is missing. Where an effect model exists (proteasome inhibitors and platelets), exposure barely depends on the patient.

## Next step

The most promising route back to lenalidomide is the **public FDA and EMA reviews**. The pooled exposure–safety analysis (AUC against grade 3/4 thrombocytopenia and neutropenia; Chen 2017 reports an odds ratio of 3.34 for thrombocytopenia) was sponsor work submitted for approvals. Regulatory clinical pharmacology reviews often print the full logistic model: intercept, slope and AUC units. That is exactly what the published summary lacks. If found, it gives a patient-dependent link: renal function → exposure (Hughes or Kim) → probability of a grade 3/4 event. It would be a probability per treatment course, not a time course, and would be labelled as such.

Searched sources for carfilzomib, kept for reference: the FDA clinical pharmacology review for NDA 202714 (2012) and an EMA variation assessment report for Kyprolis. Neither could be downloaded from this workspace.

## Update (16 October): the lenalidomide exposure–safety analysis in the TGA review

The Australian clinical evaluation report (AusPAR lenalidomide, February 2016, Attachment 2, section 4.2.4.1; read from the platform owner's local text copy) describes sponsor study **CC-5013-MCL-001-PK** (8 October 2012).

**The study:**
- 147 subjects with mantle cell lymphoma, myeloma or MDS, from 7 studies; 2,495 samples.
- PK model: two compartments with a lagged, two-stage absorption. Typical CL/F was 10.2 L/h at the mean CrCl of 79.36 mL/min, and CrCl was the only significant covariate on clearance. The CL and V equations are images and did not survive in the text copy.

**Exposure–safety in myeloma** (logistic regression on ln AUC):

| Endpoint | Odds ratio per 1-unit increase in ln AUC | 95% CI | Adjusted for |
|---|---|---|---|
| Grade 3/4 thrombocytopenia | 2.972 | 1.027–8.598 | baseline platelet count |
| Grade 3/4 neutropenia | 1.982 | 0.924–4.249 (not significant) | — |

Disease type and baseline counts also contributed; in MDS, the disease was a stronger predictor than exposure.

**Still not reported:**
- the intercept and the baseline-count coefficient;
- the exact AUC definition;
- the number of myeloma patients.

So **absolute risk cannot be computed.** The thrombocytopenia odds ratio is close to, but not the same as, the 3.34 in Chen 2017; that is probably a different analysis set and is to be reconciled.

**What it allows.** An odds ratio per unit of ln AUC does not depend on AUC units. For two patients with the same baseline platelet count and disease, it gives the **relative** odds from the ratio of their exposures: OR_rel = (AUC_patient / AUC_reference)^ln(2.972) = (AUC ratio)^1.089, with the CI carried through. This would connect renal function → exposure (Hughes or Kim) → relative odds of grade 3/4 thrombocytopenia. It would be labelled as relative odds, never as a probability.

The EMA reports II/0107 (2019, follicular lymphoma) and II/0056 (only 3 of 123 pages in the copy) gave nothing further.

## 4.0a — Relative odds of grade 3/4 cytopenia (built 16 October)

**What it does.** On the patient's "Compare Hughes and Kim" view, each model's typical daily AUC is already divided by the measured reference: the mean after 25 mg with normal renal function, 2181 ng·h/mL (2.1e). 4.0a turns that ratio into relative odds of a grade 3/4 event, using the TGA odds ratios:

relative odds = (AUC ÷ reference)^ln(OR), with the 95% CI of the published OR carried through.

Grade 3/4 thrombocytopenia is the primary endpoint. Neutropenia is shown but marked not significant in the source.

**Files:**
- `intelligence_store/data/lenalidomide_exposure_safety_tga_v1.json` (pinned; every quote checked against the TGA text);
- `intelligence_store/lenalidomide_relative_odds.py`;
- a fenced panel on the model-comparison view.

**This is the first patient-dependent exposure–effect chain on the platform:** renal function → exposure (Hughes 2019 or Kim 2026, both externally checked) → relative odds.

Example for a synthetic 65-year-old woman with myeloma (Kim 2026, 10 mg daily):

| Kidney function | Relative odds, thrombocytopenia (95% CI) |
|---|---|
| CrCl about 56 mL/min | 0.53 (0.29–0.98) |
| CrCl about 18 mL/min | 1.13 (1.00–1.28) |
| CrCl about 10 mL/min | 1.29 (1.01–1.65) |

**Why it is labelled the way it is:**
- **Relative, not absolute.** The intercept was not published, so the same relative odds can mean a small or a large change in risk. The page says so above the numbers.
- **Wide uncertainty.** The lower CI limit of the OR is 1.027, so every interval nearly touches 1.
- **The source model is not reproduced.** The odds ratio was estimated on AUC from the sponsor's own PK model; here the ratio of a different model's AUC to a measured reference stands in for it. Ratios are more robust to that swap than absolute AUC, and both models reproduce the reference within about 5% at normal renal function.
- **Probably understated in severe impairment**, where both models under-predict exposure.
- **No absolute or individual outputs.** No probability, monitoring advice or dose recommendation is produced.

**Not done:** any external check. No outside data on cytopenia by exposure have been found.

## 4.0b — Reconciliation and between-patient variability (16 October)

**The two odds ratios are the same analysis, cut two ways.** Chen, Zhou and Palmisano (*Clin Pharmacokinet* 2017, §6.2; open access, read through the publisher page and still to be checked against the PDF) report the sponsor's exposure–safety meta-analysis. It covered six studies of myeloma, MDS and mantle cell lymphoma at 5–50 mg, adjusted for disease and baseline counts, over all cycles up to one year. That gives the **all-disease** thrombocytopenia odds ratio of 3.337 (1.183–9.415). The TGA reports the **myeloma-only** value from the same analysis, 2.972 (1.027–8.598); both cite the Blood 2013 abstract 3234 / study CC-5013-MCL-001-PK. The myeloma-only value remains the one used. The TGA's "7 studies" versus Chen's "six" is noted but unresolved.

**New caveat from Chen 2017:** "These relationships were not apparent during the first treatment cycle." Relative odds therefore apply to a course of treatment, and the page now says so.

**Between-patient variability.**
- **Method:** daily AUC = dose ÷ CL, and each model publishes a between-patient SD for ln CL/F: Hughes 0.544 (ω² = 0.296, control stream) and Kim 0.189 (18.9% CV, with the CV-to-SD reading recorded as an assumption). The middle 90% of relative odds among patients with identical covariates is therefore (ratio)^ln OR × e^(±1.645 · ln OR · SD).
- **Display:** a separate column, next to the odds-ratio CI and not combined with it, because they are different kinds of uncertainty.
- **What it shows:** at twice the reference exposure, the middle 90% of patients range from 0.8 to 5.6 (Hughes) and from 1.5 to 3.0 (Kim) in relative odds. Variation between patients often outweighs the uncertainty in the odds ratio, so the typical value says little about any one person.

Files:
- `lenalidomide_exposure_safety_v2.json` (pinned; v1 kept unchanged and tested);
- `lenalidomide_relative_odds.py` (method v1.1, `between_patient_range`);
- `estimated_pk._clearance_variability`.


## 4.0c — Run record for relative odds (16 October)

The relative-odds panel was the only Patient Lab result without a run record. It now has one.

- `model_evidence_status_v5.json` (v1.4; v4 kept) adds `lenalidomide_exposure_safety_2016`, the odds-ratio source, with its four layers stated plainly:
  - software verification: done;
  - transcription: partial (TGA checked against the AusPAR text, Chen 2017 not yet against the PDF);
  - reproduction: not done (intercept, baseline-count coefficients and AUC definition were not published);
  - external consistency: not done (Chen 2017 is the same analysis, so it is not independent confirmation).
- The same file adds the end-stage kidney disease check (2.0c) to the renal pathway model as a further report, so the renal pathway page now shows it.
- `run_record.record_for_relative_odds` builds a record for the "Compare Hughes and Kim" result. It lists:
  - the patient-record inputs and each model's exposure ratio;
  - the assumptions: exposure measure, odds ratios used, time window, same baseline, and each model's clearance variability (Kim's marked as assumed because it is converted from a CV);
  - the declared disease, flagged when it is not myeloma;
  - checksums.
- The panel states its own result type, because the page banner describes the concentration curve, not the odds.
- Test fix: `tests/test_migrations.py` opened SQLite with `with sqlite3.connect(...)`, which commits but does not close. This was the source of the stray ResourceWarning; it now uses `contextlib.closing`.
