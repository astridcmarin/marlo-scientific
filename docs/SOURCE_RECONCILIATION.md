# Source reconciliation: lenalidomide renal evidence

Recorded 31 October 2026. Pinned record: `intelligence_store/data/lenalidomide_renal_source_reconciliation_v1.json` (loader `lenalidomide_label.load_renal_reconciliation`; every number recomputed in `tests/test_lenalidomide_reconciliation.py`).

Three differences appeared when the REVLIMID label (revision 3/2023) was added next to the EMA assessment table already used by the platform. Locked check results are not changed by any of them.

## 1. Renal study group sizes: 3 or 7 subjects with normal function? (reconciled by inference)

| | EMA assessment (PDF page 20) | Label section 12.3 |
|---|---|---|
| Clearance method | **Measured** creatinine clearance | **Cockcroft–Gault** |
| Normal, > 80 mL/min | 7 | 3 (healthy) |
| Mild | 5 (50–80) | 8 (50–79) |
| Moderate | 6 (30–< 50) | 9 (30–49) |
| Severe, not on dialysis | 6 | 4 |
| ESRD on dialysis | 6 | 6 |
| Total | 30 | 30 |

The label's results reproduce from the EMA Table 4 group means:
- **Clearance:** 66% and 75% lower in moderate and severe impairment, and 81% lower in ESRD off dialysis. The label says "66% to 75%" and "an 80% decrease".
- **Half-life:** 3.2-, 2.8- and 4.7-fold longer. The label says "3-fold" and "approximate 4.5-fold".

So this is the same 30-subject study, classified by two clearance methods. The label's numbers come from the measured-clearance groups. The platform's reference (normal group, n = 7, mean AUC 2,181 ng·h/mL) is unaffected.

**To confirm:** Chen et al., *J Clin Pharmacol* 2007;47:1466–1475, the study's own publication.

## 2. Which clearance defined the groups in the Hughes and Kim checks? (correction)

Both locked plans recorded that the study's clearance method was not stated in the extracted pages. **That was wrong.** The EMA page states measured creatinine clearance. The weight basis is indeed not stated. Both checks treated the group ranges as Cockcroft–Gault values, the models' own covariate. The label's Cockcroft–Gault classification puts fewer subjects above 80 mL/min, so for some subjects the Cockcroft–Gault value was lower than the measured one.

**Post-hoc bound.** This is not a rerun. It uses only each model's covariate equation:
- **Hughes:** clearance ∝ CrCl^0.224. Going from 40 to 25 mL/min raises exposure only about 1.11-fold, so this cannot explain the 2.1-fold under-prediction in the moderate group. That finding stands.
- **Kim:** clearance ∝ exp(0.0131 × eGFR). An eGFR 5, 10 or 15 mL/min lower raises exposure about 1.07-, 1.14- or 1.22-fold. That is comparable to Kim's 1.3-fold under-prediction in the severe group, so part of that result may come from the method difference.

Recorded in evidence status v8 (`model_evidence_status_v8.json`) on both scorecards. The scope band edges (30 and 50 mL/min) come from the measured-clearance groups but are applied to each model's estimated clearance. This is recorded here; the scope files are unchanged.

## 3. First renal dose step: 50 or 60 mL/min? (difference recorded)

The label's Table 3 starts at creatinine clearance 30–60 mL/min. The platform's reference note quotes Chen 2017, a secondary source, describing reductions below 50 mL/min. No platform calculation uses a dose threshold. The 50 mL/min figures in scopes and summaries are the study's moderate-group boundary, not a dose threshold.

**To confirm:** an earlier REVLIMID label and the review for the supplement that set the 30–60 mL/min step.

## Also corrected in evidence status v8

The Hughes transcription layer said the supplementary control stream was not retrieved. It was reviewed on 13 October 2026 for the random-effect and residual-error blocks (`hughes_variability_extract_v1.json`). The structural parameters have not yet been cross-checked against it.
