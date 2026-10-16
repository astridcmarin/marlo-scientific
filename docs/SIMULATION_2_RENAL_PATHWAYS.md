# Simulation 2.0 — lenalidomide elimination pathways (kidney-focused)

Status: **2.0a–2.0c done**: pathway model, locked check, patient organ view, and end-stage kidney disease and dialysis.

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
- **Reading A is close but not enough.** It fits mild and severe impairment, but under-predicts moderate (0.79 of observed) and over-predicts the urine fraction there (67% vs 42%). That result depends on the assumed group creatinine clearances: A is consistent in moderate impairment when normal CrCl is set to 130, or when the impaired groups sit at the lower ends of their ranges.
- **Recorded finding (plan rule):** renal elimination of lenalidomide appears to fall *faster* than in proportion to creatinine clearance. That is consistent with Hughes 2019 under-predicting exposure in moderate and severe impairment, since its clearance also scales with CrCl. A plausible mechanism is reduced tubular transporter activity in kidney disease, but the source cannot show this.
- **Neither reading is "supported"** under the plan's rule (consistent in all three groups, primary scenario).

**Limits:**
- Group means of 5–7 subjects, with group creatinine clearance known only as a range.
- Measured creatinine clearance overestimates GFR.
- Bioavailability is taken as 1 (urinary recovery implies at least about 0.85).
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
- **Non-renal clearance implied by each group's own data:** normal 29, mild 47, moderate 40, severe 29 mL/min. There is no trend with kidney function; the spread is what groups of 5–7 people produce. The constant non-renal assumption therefore stands, and the moderate-group shortfall in 2.0a is better explained by renal elimination falling faster than creatinine clearance.
- **Dialysis:** with the subjects' own non-dialysis clearance (37.5 mL/min) applied through the dialysis day, their own routes eliminated 15.4 mg. One 4-hour session started 3 h after dosing therefore removed about **9.6 mg, 39% of the dose**, and exposure that day was 0.61 times the non-dialysis day. Dialyser clearance itself cannot be computed: concentrations during the session were not reported.

**Patient page:** for an estimated creatinine clearance below 10 mL/min, the 2.0b page now warns that the model fits end-stage disease only with some residual function, and that dialysis is an extra route not drawn.

Report `docs/verification/lenalidomide_esrd_dialysis_check_v1.json`; CLI `lenalidomide-esrd-dialysis-check`.

## Next

- **A dialysis route on the patient page,** if session-level concentration data can be found; today only the total removed by one session is known.
- **Why renal elimination falls faster than creatinine clearance:** literature on lenalidomide's tubular transporters.

