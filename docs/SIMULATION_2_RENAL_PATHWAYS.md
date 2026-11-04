# Simulation 2.0 — lenalidomide elimination pathways (kidney-focused)

Status: **2.0a–2.0d done**: pathway model, locked check, patient organ view, end-stage kidney disease and dialysis, and the steeper-secretion test (not adopted). An AI review on 4 November 2026 found that the 2.0a moderate-band result depends on the assumed bioavailability; see the review section at the end.

## Why this, and not a full PBPK model

Lenalidomide is not metabolised by cytochrome P450, and about 85% of a dose leaves unchanged in urine. Renal clearance is at least 190 mL/min. That is more than filtration of unbound drug could achieve (about 0.77 × GFR, or about 85 mL/min at a GFR of 110), so the kidney tubules also actively secrete it. Kidney function is therefore the main patient factor for this drug.

A full PBPK model would also need organ volumes, tissue partition coefficients and the secretion transporters' kinetics. None of these are available: the EMA report says the transporters were still being investigated. Building one would mean inventing most of its parameters. What the evidence does support is a **semi-physiological clearance model**:

| Pathway | Physiology | How it is set |
|---|---|---|
| Filtration | unbound fraction × GFR | fu 0.77 (23% bound in myeloma plasma); measured creatinine clearance stands in for GFR |
| Tubular secretion | active transport into urine | renal clearance minus filtration, in the normal group |
| Non-renal | everything else | total clearance minus renal clearance, in the normal group; held constant |

## 2.0a — Locked check against study CC-5013-PK-001

- **Evidence:** EMA 2008 assessment report, pages 20–21, pinned in `lenalidomide_renal_pathways_evidence_v1.json`. It gives AUC, CL/F and the percentage of the dose excreted unchanged in urine for each renal-function group, after a single 25 mg dose.
- **Plan:** `lenalidomide_renal_pathways_plan_v1.json`, locked in commit `8941eca` before computation. Disclosed in the plan: the observed group means had been read, and a rough mental calculation had suggested reading A might fail in the moderate group.

**Calibration (normal group only).** Total clearance is 191 mL/min (25 mg ÷ mean AUC). It splits into:
- renal 162 mL/min (85% of the dose), of which filtration is 85 and secretion 78 at an assumed CrCl of 110;
- non-renal 29 mL/min.

**Two hypotheses for how secretion changes as kidney function falls:**
- **A, intact nephron:** secretion falls in proportion to creatinine clearance, like filtration.
- **B, secretion preserved:** secretion stays at its normal value.

**Result** (primary scenario; report `docs/verification/lenalidomide_renal_pathways_check_v1.json`):

| Group | Observed AUC (95% CI) | A: predicted | B: predicted | Observed % in urine | A: predicted |
|---|---|---|---|---|---|
| Mild | 2767 (1409–4125) | 3344, consistent | 2664, consistent | 69% | 77% |
| Moderate | 6021 (5132–6910) | 4751, **under** | 3038, **under** | 42% | 67% |
| Severe (no dialysis) | 8191 (6809–9573) | 7161, consistent | 3422, **under** | 44% | 51% |

**What it shows:**
- **Secretion falls with kidney function.** Reading B under-predicts exposure about two-fold in moderate and severe impairment in every scenario. Keeping secretion intact cannot explain the data.
- **Reading A is close but not enough.** It fits mild impairment in every scenario and severe impairment in the primary scenario only (not with normal CrCl at 90 or with the impaired groups at the ends of their ranges), but under-predicts moderate (0.79 of observed) and over-predicts the urine fraction there (67% vs 42%). That result depends on the assumed group creatinine clearances: A is consistent in moderate impairment when normal CrCl is set to 130, or when the impaired groups sit at the lower ends of their ranges.
- **Recorded finding (plan rule):** renal elimination of lenalidomide appears to fall *faster* than in proportion to creatinine clearance. [Corrected 4 November 2026: this sentence first said the finding was consistent with Hughes 2019 under-predicting, "since its clearance also scales with CrCl". Hughes scales clearance as CrCl^0.224, far flatter than proportional, so its under-prediction shows only that the decline is steeper than that, not steeper than proportional.] **This finding also depends on bioavailability F, taken as 1:** at F = 0.90, inside the range the data allow, reading A is consistent in the moderate group and over-predicts the severe group (review of 4 November). A plausible mechanism is reduced tubular transporter activity in kidney disease, but the source cannot show this.
- **Neither reading is "supported"** under the plan's rule (consistent in all three groups, primary scenario).

**Limits:**
- Group means of 5–7 subjects. When 2.0a was planned, group creatinine clearance was known only as a range; Chen 2007 Table I means (normal 102.2 mL/min) were added on 31 October and are used by 2.0d. The body map still calibrates at 110.
- Measured creatinine clearance overestimates GFR.
- Bioavailability is taken as 1 (urinary recovery implies at least about 0.85). Renal clearance (Ae/AUC) does not depend on F, but the non-renal clearance derived from CL/F does: 28.7 mL/min at F = 1, 9.6 at F = 0.90, about 0 at F = 0.85. The non-renal route and the moderate-band finding are therefore not separable from F with these data.
- The EMA report states renal clearance as "at least 190 mL/min"; the model's 162 mL/min (85% of the mean CL/F) is not reconciled with that statement.
- No SD for the urine fractions.

CLI: `flask --app app/app.py lenalidomide-renal-pathways-check`.

## 2.0b — Patient organ view

Page `…/patient-state/revisions/<id>/renal-pathways`, linked from the patient record as "Lenalidomide elimination pathways". Module `intelligence_store/patient_renal_pathways.py`.

**How it works:**
- **Kidney function:** the record's creatinine clearance is estimated with Cockcroft–Gault, using the documented weight-basis assumption.
- **Pathway split:** the 2.0a model divides clearance into filtration, tubular secretion and non-renal routes under the intact-nephron reading. The secretion-preserved reading was rejected in 2.0a and is not offered.

**What the page shows:**
- **A kidney diagram** (blood → kidney → urine, plus the non-renal route) for the patient and for normal kidney function. Arrow widths are proportional to clearance, on a shared scale.
- **A table** of each pathway in mL/min and as a share of the total, and the percentage of the dose leaving unchanged in urine.
- **Typical exposure at the same dose** relative to normal kidney function.
- **Warnings:**
  - in moderate impairment, the 2.0a check found renal elimination lower than this reading predicts;
  - outside about 10–140 mL/min, the split is an extrapolation.
- **The shared banner and run record.** The model is registered in `model_evidence_status_v4.json` (v1.3; from v1.4, `model_evidence_status_v5.json` also lists the 2.0c end-stage check as a further report); its "secretion scales with kidney function" assumption is marked as partly contradicted.

**Example** (synthetic 65-year-old woman; Cockcroft–Gault with ideal body weight):

| Estimated CrCl | Filtration / secretion / non-renal (mL/min) | Leaving in urine | Exposure vs normal |
|---|---|---|---|
| 74 | 57 / 52 / 29 | 79% | 1.4× |
| 37 | 29 / 26 / 29 | 66% | 2.3× (real increase probably larger) |
| 18 | 14 / 13 / 29 | 48% | 3.5× |

This is the platform's first organ-level view: it shows where the drug goes, not only how much is in plasma.

## 2.0c — End-stage kidney disease and dialysis

- **Evidence:** EMA 2008 Table 4, ESRD columns, pinned in `lenalidomide_esrd_dialysis_evidence_v1.json`. The same six subjects received 25 mg once on a non-dialysis day and once 3 h before a 4-hour haemodialysis session.
- **Plan:** `lenalidomide_esrd_dialysis_plan_v1.json`, locked in commit `382a301` before computation. It discloses that a mental estimate of about 1.3-fold over-prediction had been made.

**Primary test: does the normal-group non-renal clearance (29 mL/min, held constant) predict ESRD exposure?** Observed AUC was 11,121 ng·h/mL (95% CI 8,883–13,359).

| Assumed residual creatinine clearance | Predicted AUC | Ratio | Result |
|---|---|---|---|
| 0 (no kidney function) | 14,540 | 1.31 | over-predicts |
| 5 mL/min | 11,562 | 1.04 | consistent |
| 10 mL/min | 9,596 | 0.86 | consistent |

**Inconclusive under the plan's rule.** The ESRD subjects' residual kidney function is not reported. The data fit a constant non-renal route if a little kidney function remained, which is common in dialysis patients, but not if none did.

**Descriptive results:**
- **Non-renal clearance implied by each group's own data:** normal 29, mild 47, moderate 40, severe 29 mL/min. There is no trend with kidney function. [Corrected 4 November 2026: the original text said the spread "is what groups of 5–7 people produce", which was asserted, not computed (the urine fractions have no reported spread). It also concluded the moderate shortfall was better explained by renal elimination falling faster; that conclusion now also depends on bioavailability, see 2.0a.] The moderate group's implied non-renal clearance (40 mL/min) is higher than normal, which would lower exposure, so it cannot explain the moderate under-prediction.
- **Dialysis:** with the subjects' own non-dialysis clearance (37.5 mL/min) applied through the dialysis day, their own routes eliminated 15.4 mg. One 4-hour session started 3 h after dosing therefore removed about **9.6 mg, 39% of the dose**, and exposure that day was 0.61 times the non-dialysis day. Dialyser clearance itself cannot be computed: concentrations during the session were not reported.

**Patient page:** for an estimated creatinine clearance below 10 mL/min, the 2.0b page now warns that the model fits end-stage disease only with some residual function, and that dialysis is an extra route not drawn.

Report `docs/verification/lenalidomide_esrd_dialysis_check_v1.json`; CLI `lenalidomide-esrd-dialysis-check`.

## Next

- **A dialysis route on the patient page,** if session-level concentration data can be found; today only the total removed by one session is known.
- **Why renal elimination falls faster than creatinine clearance:** literature on lenalidomide's tubular transporters.


## Simulation 2.0d: secretion that falls faster than filtration — plan locked (4 November 2026)

`intelligence_store/data/lenalidomide_renal_pathways_plan_v2.json`, pinned in `tests/test_renal_pathways_plan_v2.py` before the model is built or run.

**Why.** Every check of the 2.0a model in moderate and severe impairment finds clearance too high: CC-5013-PK-001 itself, Bridoux 2016 and the body-map time course. In CC-5013-PK-001's moderate group, 42% of the dose left unchanged in urine against the model's 67%. Renal clearance (about 30 mL/min) was close to what filtration of unbound drug alone would give. The hypothesis is that tubular secretion falls faster than filtration as kidney function declines. [Corrected 4 November 2026: this paragraph also said "this is the problem in the model's structure, not something specific to myeloma", which the 2.0d result contradicts, and cited Bridoux and the time course as showing clearance too high; neither did for this model. The plan stays as locked.]

**Model.** Secretion = S_ref × (CrCl / 110)^k. Everything else is the 2.0a calibration the body map uses, so k = 1 is the current model. **One parameter, k, is fitted, on CC-5013-PK-001's impaired groups only** (mean AUC; measured creatinine clearance from Chen 2007). No other form is tried under this plan.

**Checks.** Both use data the analyst has seen but no fit has used; neither is blind, and the report will say so.
- **Bridoux 2016** (French myeloma patients, steady state): AUC24 per group, against the 90% CI of the geometric mean.
- **Kim 2026 Table 2** (Korean myeloma patients, steady state): total CL/F per group, against the 90% CI of the mean. Kim groups are by eGFR; the input is the median eGFR de-indexed by median BSA.
- The current model (k = 1) is classified side by side.

**Decision, fixed in advance.** v2 replaces v1 wherever the pathway model is used only if:
- k is not at a bound;
- v2 is consistent in the moderate and severe groups of **both** studies (four of four);
- v2 does no worse than v1 in the other groups.

Three of four means v2 is reported but not adopted. Otherwise the result is recorded as a failure of this form. The existing warnings stay in both cases. If adopted, the time course is re-checked under its own plan before its warnings change, and pages say "consistent with two myeloma studies not used to fit it", never "validated".

**Search for unseen data (4 November 2026).** Kim 2026 and its PAGE 2025 abstract (same patients), the Guglieri-López 2017 thesis (15 patients with PK; set aside on 14 October), and the REVLIMID EMA reports II-0056 (its renal section is CC-5013-PK-001) and II-0107 (no PK section) were searched by headings and table titles only. None holds unseen group-level renal-impairment data.

## Simulation 2.0d result (4 November 2026): partial, not adopted — and the current model fits the myeloma studies

Module `intelligence_store/lenalidomide_renal_pathways_v2.py`; report `docs/verification/lenalidomide_renal_pathways_check_v2.json`. Built and run exactly as the locked plan states, after the plan was applied on the owner's computer. Numerical checks pass (k = 1 reproduces the 2.0a model exactly; secretion stays non-negative and falls with creatinine clearance; the fit is at least as good as every grid point).

**Fit (CC-5013-PK-001 impaired groups):** k = 1.48, not at a bound. In-sample AUC moves toward observed (moderate 5,512 vs 6,021 observed, against 4,824 at k = 1; severe 7,550 vs 8,191, against 6,517), but the moderate group's fraction excreted unchanged stays far off (62% vs 42% observed).

**Checks (seen, never fitted; not blind):**

| Study, group | Observed (90% CI) | v2 (k = 1.48) | v1, current (k = 1) |
|---|---|---|---|
| Bridoux, normal | AUC24 1,747 (1,500–2,035) | 2,240: over | 2,229: over |
| Bridoux, mild | 2,605 (2,215–3,063) | 3,678: over | 3,372: over |
| **Bridoux, moderate** | 1,800 (1,631–1,987) | **2,164: over** | 1,897: consistent |
| **Bridoux, severe** | 2,329 (1,786–3,037) | 2,391: consistent | 2,065: consistent |
| Kim, control | CL/F 8.01 L/h (6.25–9.77) | 8.16: consistent | 8.65: consistent |
| **Kim, moderate** | 5.74 (4.81–6.67) | 5.45: consistent | 6.12: consistent |
| **Kim, severe** | 3.39 (2.95–3.83) | 3.27: consistent | 3.78: consistent |

**Decision, as pre-specified:** three of the four deciding comparisons are consistent (Bridoux moderate is over-predicted), so **v2 is reported and not adopted**. All three sensitivity scenarios give the same three of four (k 1.48–2.18). Nothing on the platform changes.

**What this shows, and a correction.**
- **The current model (k = 1) is consistent with both myeloma studies in the moderate and severe groups**, four of four, in the same pre-specified comparison. The plan's rationale said Bridoux showed the 2.0a model's clearance too high there. That was wrong: the 2.1h Bridoux check compared the **Hughes and Kim** models, not the pathway model. The pathway model's moderate and severe gap is seen in **CC-5013-PK-001**, the study it was built from, whose subjects did not have cancer.
- So the question changes. Steeper secretion loss fits CC-5013-PK-001 better and the myeloma studies worse. The gap may come from that study's population or methods (for example, its moderate group's mean weight of 96 kg, or creatinine clearance from 24-hour urine collection), not from how myeloma kidneys handle the drug. This is a hypothesis, not a finding.
- **Both versions over-predict exposure in Bridoux's normal and mild groups** (myeloma patients with good kidney function cleared the drug faster than the CC-5013-PK-001 calibration implies). That is a calibration question for later.
- **What the pages may say now:** the existing moderate and severe warnings stay, because they come from the locked 2.0a check. This report adds, for the current model, the pre-specified comparator result: consistent with Bridoux and Kim (myeloma, seen but not fitted) in the moderate and severe groups. Whether and how scope pages show that next to the warning is an owner decision.

**Shown on the platform (owner decision, 4 November 2026).** The comparator result is now shown beside the existing warning, not in place of it:
- **Body map, moderate and severe bands** (alert, numbers panel, kidney and flow cards in 3D): "That check is CC-5013-PK-001, the study the model was built from, in people without cancer. In two studies of myeloma patients never used to fit it (Bridoux 2016, Kim 2026), the model is consistent with the observed exposure in this band. Both studies had been seen before this comparison, so it is not a blind test; why the studies differ is not known." The text is generated from the pinned 2.0d report (`body_map.myeloma_note`), so it would change with a different result. The band status, its colour and the run-record warning are unchanged.
- **Run records** of the body map carry the note under the secretion assumption and the 2.0d report's checksum.
- **Model scorecard** (evidence status v14, v13 kept): the 2.0d report is a further report on the pathway model's external-consistency layer, listing all seven pre-specified comparisons, including the two disagreements (Bridoux normal and mild, exposure too high).

## AI review of 4 November 2026

A separate AI reviewer agent, with no access to the conversation in which this work was done, reviewed 2.0a–2.0d, the body map and the time course ([record](reviews/2026-11-04_ai_review_renal_pathways.md)). It is not an independent review. Its main finding:
- **The 2.0a result depends on bioavailability F, which was taken as 1.** Renal clearance does not depend on F, but the non-renal clearance derived from CL/F does. At F = 0.90, inside what the data allow (about 0.85 to 1), the intact-nephron reading is consistent in the moderate group and over-predicts the severe group.
- The finding that renal elimination falls faster than in proportion to creatinine clearance is therefore not robust, and neither is the reason 2.0d was run.
- It also showed that at fu 0.77 the moderate group's renal clearance (29.1 mL/min) is at or below filtration alone (30.1), which no secretion term can reach.

Wording was corrected in this document, the Digital human 1.1 document, the status-by-drug page, the body map (band text, myeloma note, limitations), findings v2 and evidence status v15. The dataset ledger v3 adds two missing uses. No model, result, scope or warning band changed. **Next: 2.0e**, a locked re-check of 2.0a across F = 0.85–1.0, deciding in advance what the moderate-band warning says.

## Simulation 2.0e: bioavailability re-check — plan locked (4 November 2026)

`intelligence_store/data/lenalidomide_renal_pathways_plan_v3.json`, pinned in `tests/test_renal_pathways_plan_v3.py`. Not blind: every value it uses has been seen, and the review already gave the 2.0a classifications at four values of F. The lock fixes what the body map will say, before computation.

- **The bound on F, newly pinned** (`lenalidomide_mass_balance_chen_2012_v1.json`): in the radiolabel study, 90.3% of the radioactive dose (range 87.0–94.6%) was recovered in urine, and more than 90% of that was lenalidomide, so absorption was at least about 0.90. Unchanged drug in urine (about 84–85%) is the hard lower bound.
- **Scenarios:** F = 1.0, 0.95 and 0.90 decide (the best-supported range); 0.85 is reported only.
- **Decided in advance:**
  - **Band status:** if the moderate or severe classification changes across F = 0.90–1.0, that band's status becomes *depends on bioavailability* (amber), with the result at each F.
  - **The faster-than-proportional finding:** "not established" if moderate is consistent at any F in that range.
  - **The non-renal arrow:** carries its range across F.
  - **The myeloma note:** says whether its result holds across F.
- Scopes and patient-record outputs are not changed by this plan.

## Simulation 2.0e result (4 November 2026): no single bioavailability fits every study

Module `intelligence_store/lenalidomide_renal_pathways_f.py`; report `docs/verification/lenalidomide_renal_pathways_check_v3.json`. Run as plan v3 states, after the plan was applied on the owner's computer. At F = 1 the model reproduces 2.0a exactly. At F = 0.85 the non-renal clearance is zero, which is the hard lower bound by construction.

| Absorbed (F) | Non-renal (mL/min) | CC-5013-PK-001 moderate | CC-5013-PK-001 severe | Bridoux moderate | Kim severe (CL/F) | End-stage, no residual function (observed 95% CI 8,883–13,359) |
|---|---|---|---|---|---|---|
| 1.00 | 28.7 | too little exposure | consistent | consistent | consistent | 14,540 |
| 0.95 | 19.1 | too little exposure | consistent | too much exposure | consistent | 20,719 |
| 0.90 | 9.6 | consistent | too much exposure | too much exposure | clearance too low | 39,258 |
| 0.85 | 0 | consistent | too much exposure | too much exposure | clearance too low | not computable |

**Reading.**
- Lower absorption fits CC-5013-PK-001's moderate group. It fits that study's severe group, both myeloma studies and the end-stage group worse.
- The end-stage group argues most strongly for near-complete absorption: even with 10 mL/min of residual kidney function, F = 0.90 predicts 15,423 against an upper limit of 13,359.
- So no single value of F reconciles the moderate group of CC-5013-PK-001 with the rest. Together with the review's finding 2 (that group's renal clearance is at or below filtration alone), the moderate group looks more like an outlier, or a study-specific effect, than evidence about how lenalidomide is eliminated. That is a reading, not a finding.

**Decisions, as fixed in plan v3:**
- **D1:** both the moderate and severe bands now have the status *depends on bioavailability* (amber), with text giving the result at each F.
- **D2:** the 2.0a finding that renal elimination falls faster than in proportion to creatinine clearance is recorded as **not established**.
- **D3:** the non-renal arrow carries its range, 10–29 mL/min, across 90–100% absorbed.
- **D4:** the myeloma note says its consistency holds at full absorption only (moderate: not at 95% or 90%; severe: not at 90%).

Scopes and patient-record outputs are unchanged, except that the record summary's elimination row now shows *partly checked* rather than *flagged* for these bands, because it reads the band status. Recorded in findings v3, evidence status v16 and dataset ledger v4 (which adds the mass-balance study).
