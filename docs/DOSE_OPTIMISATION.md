# Phase 4.3 — Dose-optimisation view (design plan)

Written 30 October 2026, before anything is built.

## Purpose

FDA's Project Optimus asks sponsors to justify an oncology dose by comparing more than one dose level on exposure, activity and tolerability, rather than carrying the maximum tolerated dose forward. For one drug, this view puts in one place what the platform holds on that question:

- which dose levels have been studied in trials;
- how exposure changes between dose levels, and with kidney function, within each model's scope;
- what the published exposure–response evidence says about the change.

It is a research reference for trial designers and clinical pharmacologists. It is not dosing guidance, and it proposes no dose.

## First drug: lenalidomide

Lenalidomide is the only drug for which the platform holds all three parts:

| Part | Pinned source | Status |
|---|---|---|
| Exposure versus dose | Dose proportionality over 5–400 mg (`lenalidomide_dose_proportionality_evidence_v1.json`, EMA 2008) | Pinned |
| Exposure versus kidney function | Hughes 2019 and Kim 2026, through their scopes (Phase 2.5) | Pinned; moderate and severe impairment flagged where outside checks disagree |
| Reference exposure | Mean AUC after 25 mg, normal renal function, CC-5013-PK-001 (n = 7) | Pinned |
| Exposure → safety | Odds ratio per unit ln AUC for grade 3/4 thrombocytopenia (2.972, 95% CI 1.027–8.598) and neutropenia (1.982, 0.924–4.249, not significant), MM, monotherapy (TGA CER) | Pinned; used since Simulation 4.0a |
| Exposure → efficacy | None | **Gap** |
| Label dose levels and renal dose reductions | REVLIMID label, revision 3/2023 (`lenalidomide_label_2023_v1.json`, added 31 October 2026) | Pinned; quoted on the page (view v1.2) |
| Trial dose levels | The pinned corpus holds intervention names only, not arm descriptions or doses | **Gap** in v1 (decision 1) |

## What the view shows

1. **Exposure by dose level for one synthetic patient.** The user enters a synthetic patient (age, sex, weight, height, serum creatinine, disease), as on the ixazomib exposure page. The two models' scopes are evaluated once for that patient (Phase 2.5). Rows are dose levels; columns are Hughes 2019 and Kim 2026. Each cell shows the typical daily AUC, its ratio to the 25 mg normal-function reference, and the scope tier for the patient: checked, model data only, or flagged with observed data. Out of scope means no value.
   - **Dose levels are the models' own study doses, not a list chosen by the platform.** Hughes 2019 lists 2.5, 5, 7.5, 15, 20, 25, 30, 35, 50 and 75 mg (`hughes_coverage_contract_v1.json`); Kim 2026 executes only 5, 7.5 and 10 mg. The view shows 2.5–25 mg: the Hughes amounts up to the reference dose, plus 10 mg from Kim. A model shows no value at a dose outside its own study doses. Hughes at 10 mg, inside its range but not a listed amount, is shown with the existing coverage flag.
   - The single-dose reference stands for a steady-state daily AUC only under linear PK (5–400 mg, `lenalidomide_dose_proportionality_evidence_v1.json`). Both models are linear, so a cell's ratio needs no further scaling.
2. **Relative odds of grade 3/4 thrombocytopenia and neutropenia** for each cell against the reference, with the 95% interval carried from the odds ratio, using the existing `lenalidomide_relative_odds` method. Not a probability: the intercept was not published, so absolute risk cannot be computed.
3. **Trials** testing lenalidomide in the myeloma corpus: counts by phase and status, with links. Dose levels are not shown in v1 (decision 1).
4. **What is missing**, shown as gaps: exposure–efficacy, label dose reductions, combination-regimen exposure–response and trial dose levels.

## Scientific limits to show on the page

- **Dose proportionality makes the dose axis simple.** Both models are linear, so for one patient each row is the 25 mg row scaled by the dose ratio. The models add the effect of the patient's kidney function and body size, not of dose.
- **The odds ratio was not estimated across these doses.** The doses and AUC range in the exposure–safety analysis are not reported, so applying it at 2.5 mg may be an extrapolation. The page says so.
- **The safety evidence is narrow.** It comes from one pooled monotherapy analysis (MCL, MM, MDS). The AUC window was not reported. The thrombocytopenia interval is wide (1.03–8.6 per unit ln AUC). Most myeloma trials give lenalidomide in combination (with dexamethasone, bortezomib or daratumumab), and this analysis says nothing about those regimens.
- **There is no efficacy side.** Without exposure–efficacy evidence the view cannot show a trade-off. It shows only how the safety odds move with exposure. Presenting a lower dose as "better" would be misleading, so the page will not rank cells.
- **Moderate and severe impairment.** Both models under-predict exposure there (Hughes about 2-fold, Kim about 1.3-fold in severe). Those cells carry the flag and the observed data, as in the Patient Lab.

## Decisions (platform owner, 30 October 2026)

1. **Trial dose levels: left out of v1.** The doses are in the ClinicalTrials.gov arm descriptions, which the pinned corpus does not hold. v1 shows trial counts and links only. Doses are added later, once a dose extractor passes a hand-checked sample with thresholds locked beforehand, as for protocol benchmarking.
2. **Drug: lenalidomide**, for the reasons above. Ixazomib could follow with exposure only.

## Data model

- `intelligence_store/dose_optimisation.py`: builds the view from pinned sources only. Nothing new is fitted.
- `intelligence_store/data/dose_optimisation_lenalidomide_v1.json` (pinned): dose levels shown, kidney bands, and the gap list, each with its source.
- Page: `/landscape/drugs/lenalidomide/dose-optimisation`, with a JSON download, linked from the special-populations page and the model library.

## Checks before release

- Every number shown regenerates from the pinned sources in a test.
- A cell is never computed outside its model's scope or its model's study doses.
- The page names no recommended dose and does not rank dose levels.

## Status

**Built 30 October 2026 (v1).** `intelligence_store/dose_optimisation.py` (schema `lenalidomide-dose-view-v1`) and the page `/landscape/drugs/lenalidomide/dose-optimisation`, with a JSON download, linked from the lenalidomide special-populations page. Tests: `tests/test_dose_optimisation.py`.

- **Sources.** The dose levels, the reference, the odds ratios, the scopes and the corpus are read from files the platform already pins. One new pinned file, `lenalidomide_exposure_response_guglieri_2017_v1.json` (31 October 2026, view v1.1), holds the thesis findings. They are shown on the page and never used in a calculation (see the evidence search below). The gap list is in the module.
- **Assumptions are fixed to each model's primary reading:** Hughes uses the recorded primary Cockcroft–Gault weight basis, Kim the primary CL/F equation form. Both are shown on the page.
- **Trials:** 380 of 3,450 corpus trials have an intervention named exactly Lenalidomide or Revlimid. Another 78 mention it only inside a longer name and are counted separately, not matched. Phase 1 and early phase 1 trials are listed with links.

## Evidence search: lenalidomide exposure–efficacy (31 October 2026)

Done to find out whether the efficacy gap is a gap in the platform or in the published evidence. The platform owner supplied the four sources; every quote below was checked against the supplied file. The files are kept on the owner's computer, not committed.

| Source (file SHA-256) | What it says on efficacy | Check |
|---|---|---|
| FDA clinical pharmacology and biopharmaceutics review, NDA 21-880, Revlimid for del 5q MDS, 2005 (`021880s000_Revlimid_BioPharmR.pdf`, `59be36a9…`) | "Clinical studies assessing the relationship between exposure and efficacy were not performed." "The relationship between dose-concentration and response is largely unknown. … The efficacy of lower doses is unknown. Determination of an optimal dose is an unresolved dosing issue." This concerns MDS at 10 mg, not myeloma. | Scanned file; text located by OCR on PDF pages 10–11 |
| Chen N, Zhou S, Palmisano M. Clin Pharmacokinet 2017;56:139–152 (`0f2c0098…`), sponsor authors | In a phase II study of myeloma patients with renal impairment on lenalidomide with dexamethasone, "no apparent pattern was observed between lenalidomide Cmax and the grade of hematologic AEs or efficacy". The renal dose reductions are AUC-matched to the full dose. | Text layer |
| Guglieri-López et al., PAGE 24 (2015), poster 3317 (`6855bc84…`) | M-protein tumour growth inhibition model in 39 patients. The drug effect declines with time on treatment; there is no dose, concentration or AUC term. | Text layer |
| Guglieri López B, doctoral thesis, Universitat de València, 2017 (`835991d6…`) | Time to progression in 54 patients, 26 events: hazard ratio 1.19 (bootstrap 95% 1.08–1.35) per 100 µg·h/L of AUC above 1,110 µg·h/L (the sample median). **Higher exposure was associated with faster progression.** Time to severe neutropenia, 27 events: hazard ratio 1.02 (1.01–1.03) per 10 ng/mL of Cmax; AUC was not significant. | Text layer; pinned as `lenalidomide_exposure_response_guglieri_2017_v1.json` |

**The thesis is the only myeloma exposure–efficacy analysis found, and the platform does not use it.** It is shown on the dose page as a cited finding, with these reasons for not using it:

1. **Exposure here is mostly dose history.** Concentrations were measured in 15 of 54 patients. For the rest, AUC is a typical value computed from the dose and covariates, so the analysis cannot separate exposure from the doses clinicians chose.
2. **Doses were not assigned at random.** In routine practice doses are reduced for toxicity, for renal function and over time. Who keeps a high dose depends on how the patient is doing, which opens a time-varying exposure covariate to confounding and reverse causation. The thesis reports no analysis addressing this.
3. **Some early progressions could not be seen.** Patients entered only after at least one month on lenalidomide, but time was counted from its start. Progressions before enrolment could not be observed, and no correction is reported.
4. **The study is small and the threshold is data-driven.** 54 patients and 26 events at one centre, with the AUC threshold set at the sample median.
5. **The direction is the opposite of expectation.** The author proposes acquired resistance; the data do not test it.

Showing it as a dose–hazard curve would suggest that lower doses are more effective. The evidence cannot support that.

**Conclusion:** no usable exposure–efficacy relationship for lenalidomide in myeloma was found. The efficacy side of the dose view stays a gap. A usable source would be a sponsor exposure–response analysis with randomised dose levels or adequate adjustment, for example in a later FDA or EMA review.

**31 October 2026 (view v1.2):** the page now quotes the label's myeloma starting doses, the 2.5 mg floor, the capsule strengths and Table 3. Grid rows that are not capsule strengths are marked; 7.5 mg is the average of the label's "15 mg every other day". The page does not pick a label dose for the record: the label does not state its Cockcroft–Gault weight basis, and the Hughes estimate uses an assumed one.
