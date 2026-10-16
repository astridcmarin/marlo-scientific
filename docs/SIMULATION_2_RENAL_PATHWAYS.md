# Simulation 2.0 — lenalidomide elimination pathways (kidney-focused)

Status: **2.0a done** (pathway model and locked check). 2.0b, a patient view of the pathways, is next.

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

## Next

**2.0b:** for a saved synthetic patient, show how elimination splits between filtration, secretion and non-renal pathways at their kidney function, under reading A and labelled with this check's finding. This is the first "organ view": where the drug goes, not just how much is in plasma.
