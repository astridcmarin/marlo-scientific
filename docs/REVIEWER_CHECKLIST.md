# Reviewer's checklist: the lenalidomide workflow

Written 4 November 2026. Until user conversations are possible, this stands in for a reviewer's reading. It lists the questions a clinical pharmacology reviewer asks and scores what the lenalidomide workflow shows for each: guided path, special populations, dose view, body map, model scorecards, credibility records and the findings page. It was written by the AI assistant and is not a regulatory assessment. It does not imply that the platform supports a regulatory submission.

**Sources of the questions** (current versions checked on 4 November 2026):
- **R:** FDA, *Pharmacokinetics in Patients with Impaired Renal Function — Study Design, Data Analysis, and Impact on Dosing*, final guidance, March 2024 (docket FDA-2010-D-0133).
- **H:** FDA, *Pharmacokinetics in Patients with Impaired Hepatic Function: Study Design, Data Analysis, and Impact on Dosage*, draft guidance announced for 2 September 2026 (docket FDA-2026-D-8693). It replaces the May 2003 guidance.
- **M:** ICH M15, *General Principles for Model-Informed Drug Development*, Step 4 on 29 January 2026.
- **O:** the structure of an FDA Office of Clinical Pharmacology review: general attributes; intrinsic and extrinsic factors; exposure–response; bioanalytical methods. An example is the REVLIMID clinical pharmacology review for NDA 21-880, in the owner's source folder.

**Scores:**
- **Answered:** the platform answers the question with sourced values.
- **Partly:** some of the answer is there, or it is there but not where a reviewer would look.
- **Gap:** the question is not answered.
- **By design:** deliberately out of scope (for example dose recommendations).

## Renal impairment (R)

| # | Reviewer's question | What the workflow shows | Score |
|---|---|---|---|
| R1 | Which renal-function categories are used? The 2024 guidance uses ≥ 90, 60 to < 90, 30 to < 60 and < 30 mL/min (the last including kidney failure not on dialysis). | Bands follow CC-5013-PK-001 (> 80, 50–80, 30–< 50, < 30); the label's dose table uses 30–60. **Since 5 November** the lenalidomide special-populations page sets the guidance's Table 1 beside both, with the ranges each shares, and the body map shows where the chosen value falls in each. The guidance values are not yet owner-reviewed. | **Answered** (was Partly) |
| R2 | How was renal function estimated? The guidance prefers eGFR in mL/min, not per 1.73 m², and alternative body weights for Cockcroft–Gault in obesity. | Recorded in the docs. Hughes uses Cockcroft–Gault, with its weight basis an open author question. Kim uses CKD-EPI eGFR indexed to 1.73 m², as published. The study measured 24-hour creatinine clearance. **Since 5 November** the special-populations page states each source's measure, with the guidance's two quotes (mL/min, not indexed; alternative weights for Cockcroft–Gault in obesity) and how Kim and Hughes differ from them. | **Answered** (was Partly) |
| R3 | Are AUC, Cmax, fu, CL/F, CLR, CLNR/F, V/F and half-life reported by group? | AUC, Cmax, CL/F, CLR and half-life are shown (special populations, body map numbers panel, EMA 2013 extract); the non-renal split is in the body map. Protein binding in renal impairment is not measured: the model holds fu constant across bands (0.77 in vitro, with 0.60 ex vivo shown as the alternative). | **Partly** |
| R4 | Is PK regressed on continuous renal function, which the guidance prefers to categories? | The EMA 2013 regressions on measured clearance are pinned and shown in the body map's observed-data panel. | **Answered** |
| R5 | Are estimates given with their precision? | Observed values carry 90% CIs in every check. Model outputs are typical values; Hughes and Kim show population bands. Parameter uncertainty is not propagated. | **Partly** |
| R6 | Were confounding covariates (age, sex, weight) considered? | Recheck 2.1e drew virtual subjects matched to each group's age, weight and sex. | **Answered** |
| R7 | What is known in dialysis? | The label's dialysis dose is quoted. The end-stage check was inconclusive (residual function not reported). Dialysis clearance is not modelled. | **Partly** |
| R8 | What population was studied, and is renal function stable? | CC-5013-PK-001's non-malignant population is recorded (2.1g); Bridoux and Kim are myeloma patients. | **Answered** |
| R9 | How was the dose for each band chosen (exposure matching, or the reference group's 5th–95th percentile)? | The label's adjusted doses are quoted. **Since 5 November** the lenalidomide special-populations page shows, descriptively, how exposure on each band's label dose compares with the reference: Bridoux 2016 observed in myeloma patients on those doses (ratio to normal 1.03 moderate, 1.33 severe, 1.16 dialysis), CC-5013-PK-001's single-dose ratios scaled to the label dose by dose proportionality (1.04, 1.06, 0.95) and the sponsor's simulation (1.05 severe). No threshold is set and no dose is recommended. | **Answered** (was Gap; descriptive) |
| R10 | What does the label say on renal elimination and dosing? | Label Table 3 and the renal-study text are quoted and reviewed by the owner. | **Answered** |

## Hepatic impairment (H)

| # | Reviewer's question | What the workflow shows | Score |
|---|---|---|---|
| H1 | What is known by hepatic function category? | The label's mild-impairment statement and "no data" for moderate to severe are shown as such. | **Answered** (a gap in the evidence, shown as a gap) |
| H2 | Is the hepatic classification stated? The 2026 draft guidance discusses classification systems. | The label's NCI-style definition (bilirubin and AST) is quoted. No comparison with Child–Pugh or the draft guidance's approach. | **Partly** |

## General attributes, intrinsic and extrinsic factors, exposure–response (O)

| # | Reviewer's question | What the workflow shows | Score |
|---|---|---|---|
| O1 | Absorption: Tmax, food effect, bioavailability. | **Since 5 November**, quoted from the label on the special-populations page and summarised in the guided path: peak at 0.5–6 h; a high-fat meal lowers AUC about 20% and Cmax about 50%; no accumulation. The label states no absolute bioavailability, and the page says so; the platform's bound (0.90–1.0, Chen 2012 mass balance) and its effect on the moderate and severe bands are in 2.0e. Not yet reviewed by the owner. | **Answered** (was Gap) |
| O2 | Distribution and elimination: half-life, clearance, fraction excreted. | EMA 2008 and 2013 (85% unchanged in urine; group half-lives, CL/F, CLR) and, **since 5 November**, the label's section 12.3 on the special-populations page: half-life 3 h healthy and 3–5 h in patients; limited metabolism; 90% of the radioactive dose in urine, 82% unchanged within 24 h; renal clearance above GFR; about 30% removed by a 4-hour haemodialysis. | **Answered** (was Partly) |
| O3 | Dose proportionality and time dependence. | The label's linearity statement and the EMA dose-proportionality evidence are pinned. | **Answered** |
| O4 | Age, body size, sex, race. | Special populations (age, body size, other covariates); Hughes's fat-free-mass effect; Kim's BSA effect. | **Answered** |
| O5 | Drug interactions. | **Since 5 November**, the label's section 7 (digoxin, thrombosis risk, warfarin) and section 12.3 interaction studies and transporter findings are quoted on the special-populations page and summarised as a guided-path step. No interaction is modelled. Not yet reviewed by the owner. | **Answered** (was Partly) |
| O6 | Exposure–response for safety. | Relative odds of grade 3/4 cytopenia (TGA AusPAR), in each model's scope. | **Answered** |
| O7 | Exposure–response for efficacy. | None; the evidence scan found no usable source. Shown as a gap. | **Gap** (shown honestly) |
| O8 | Bioanalytical method: is the assay adequate? | The assay quality review covers one published assay. The assays behind CC-5013-PK-001, Bridoux and Kim are not summarised. | **Partly** |

## Model credibility (M)

| # | Reviewer's question | What the workflow shows | Score |
|---|---|---|---|
| M1 | Question of interest, context of use, model influence, consequence of a wrong decision, model risk. | Credibility records for every model, in the M15 structure. | **Answered** |
| M2 | Was the analysis planned before the data were accessed? | Every check followed a plan locked before computation, but only 3 of 27 before the data were seen. Each plan and the dataset ledger say which. | **Partly** (stated honestly) |
| M3 | Is there a model analysis report with summary, methods, results, discussion and conclusions? | **Since 5 November**, one model has one: the kidney pathway model, at `/models/lenalidomide_renal_pathways_2026/report`, in the section order of ICH M15 Appendix 2. Results, data, plans and assumptions are read from the pinned reports, ledger and credibility record; the summary, introduction, discussion and conclusions are AI-written and pinned. Hughes, Kim and the exposure–safety relationship have none yet. | **Partly** (1 of 4 lenalidomide models) |
| M4 | Verification of the implementation. | Numerical checks (closed form against ODE solver, mass balance) in every report; transcription reviewed by the owner. | **Answered** |
| M5 | Validation against data not used to build the model. | Outside checks for both population models (two studies); the pathway model's checks were not blind. All on `/models/findings`. | **Partly** (stated honestly) |
| M6 | Applicability: are the inputs inside the model's data? | Enforced scopes refuse requests beyond each model's data; flagged bands carry warnings. | **Answered** |
| M7 | Uncertainty: parameter, between-subject and residual. | Population bands for Hughes and Kim; no parameter uncertainty. | **Partly** |
| M8 | Was the work reviewed by someone independent? | Owner review of transcription only. No independent scientific review. | **Gap** |
| M9 | Are deviations from the plan documented? | Yes, for example the Bridoux stage-1 deviation and the 2.0d rationale correction. | **Answered** |

## Score

Of 29 questions (updated 5 November 2026, after R1, R2, R9, O1, O2 and O5):
- **18 Answered** (including H1, where the evidence itself is missing and shown as missing);
- **9 Partly**;
- **2 Gap**.

Three of the new answers (O1, O2, O5) rest on label values not yet reviewed by the owner (round 3).

The strengths are where the platform has invested: provenance, locked plans, scopes and honest reporting of failures.

## What a reviewer would ask for first: candidate work, smallest first

1. **Done 5 November.** **Show the FDA 2024 renal categories** alongside the study's bands and the label's dose bands, with the mapping between them (R1). Small; no new data.
2. **Done 5 November.** **State each model's renal-function measure on the pages** (Cockcroft–Gault weight basis, Kim's indexed eGFR, the study's measured clearance), with the guidance's preference noted (R2).
3. **Done 5 November.** **Extract the rest of the lenalidomide label's section 12.3** (absorption, food, elimination) for the owner's review round 3 (O1, O2). Small; the label PDF is already pinned.
4. **Done 5 November.** **Does each band's label dose restore reference exposure?** Show it descriptively from Bridoux (myeloma patients on label-adjusted doses, AUC by group) and from the models, without recommending a dose (R9). Medium; data already pinned.
5. **Started 5 November (kidney pathway model).** **One readable model analysis report per model,** in M15's section order (summary, background, goals, data and methods, results, discussion, conclusions), generated from the pinned plans, reports and credibility records (M3). Medium.
6. **Done 5 November.** **Interactions in the guided path and on the special-populations page** (O5). Small.

Larger, later:
- parameter uncertainty (M7, R5);
- assay summaries for the three renal studies (O8);
- protein binding in renal impairment (R3);
- an independent reviewer (M8).
