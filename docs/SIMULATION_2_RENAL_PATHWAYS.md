# Simulation 2.0 — lenalidomide elimination pathways (kidney-focused)

Status: **2.0a and 2.0b done**: pathway model, locked check and a patient organ view.

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
- **The shared banner and run record.** The model is registered in `model_evidence_status_v4.json` (v1.3); its "secretion scales with kidney function" assumption is marked as partly contradicted.

**Example** (synthetic 65-year-old woman; Cockcroft–Gault with ideal body weight):

| Estimated CrCl | Filtration / secretion / non-renal (mL/min) | Leaving in urine | Exposure vs normal |
|---|---|---|---|
| 74 | 57 / 52 / 29 | 79% | 1.4× |
| 37 | 29 / 26 / 29 | 66% | 2.3× (real increase probably larger) |
| 18 | 14 / 13 / 29 | 48% | 3.5× |

This is the platform's first organ-level view: it shows where the drug goes, not only how much is in plasma.

## Next

- **Add the end-stage renal disease and dialysis groups** of CC-5013-PK-001 (not yet transcribed). Dialysis is an extra elimination route; the off-dialysis CL/F was 39 mL/min.
- **Test whether non-renal clearance changes with kidney function**, as the moderate group hints.

