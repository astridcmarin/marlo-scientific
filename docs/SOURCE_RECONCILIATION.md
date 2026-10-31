# Source reconciliation: lenalidomide renal evidence

Recorded 31 October 2026. Pinned record: `intelligence_store/data/lenalidomide_renal_source_reconciliation_v2.json` (v2 adds the renal study's conference abstract; v1 kept) (loader `lenalidomide_label.load_renal_reconciliation`; every number recomputed in `tests/test_lenalidomide_reconciliation.py`).

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

**Study abstract (added in v2).** The study's conference abstract (*J Clin Oncol* 2007;25(18_suppl):2520, the ASCO 2007 meeting supplement; authors not verified) confirms the 7/5/6/6/6 stratification by creatinine clearance. It doesn't say how clearance was determined. Its AUC increases reproduce from the EMA means:

| Group (vs pooled normal and mild) | Abstract | EMA means |
|---|---|---|
| Moderate | about 140% | 148% |
| Severe | 240% | 238% |
| ESRD (off dialysis) | 360% | 359% |

**To confirm:** Chen et al., *J Clin Pharmacol* 2007;47:1466–1475, the full publication, to see whether the label's Cockcroft–Gault grouping is reported there.

## 2. Which clearance defined the groups in the Hughes and Kim checks? (correction)

Both locked plans recorded that the study's clearance method was not stated in the extracted pages. **That was wrong.** The EMA page states measured creatinine clearance. The weight basis is indeed not stated. Both checks treated the group ranges as Cockcroft–Gault values, the models' own covariate. The label's Cockcroft–Gault classification puts fewer subjects above 80 mL/min, so for some subjects the Cockcroft–Gault value was lower than the measured one.

**Post-hoc bound.** This is not a rerun. It uses only each model's covariate equation:
- **Hughes:** clearance ∝ CrCl^0.224. Going from 40 to 25 mL/min raises exposure only about 1.11-fold, so this cannot explain the 2.1-fold under-prediction in the moderate group. That finding stands.
- **Kim:** clearance ∝ exp(0.0131 × eGFR). An eGFR 5, 10 or 15 mL/min lower raises exposure about 1.07-, 1.14- or 1.22-fold. That is comparable to Kim's 1.3-fold under-prediction in the severe group, so part of that result may come from the method difference.

Recorded in evidence status v8 (`model_evidence_status_v8.json`) on both scorecards. The scope band edges (30 and 50 mL/min) come from the measured-clearance groups but are applied to each model's estimated clearance. This is recorded here; the scope files are unchanged.

## 3. First renal dose step: 50 or 60 mL/min? (difference recorded)

The label's Table 3 starts at creatinine clearance 30–60 mL/min. The platform's reference note quotes Chen 2017, a secondary source, describing reductions below 50 mL/min. No platform calculation uses a dose threshold. The 50 mL/min figures in scopes and summaries are the study's moderate-group boundary, not a dose threshold.

**Origin of the 50 (v2).** The study's own conclusion was "dosage adjustment should be considered for patients with CLCr < 50 mL/min". Its recommended myeloma starting doses were:
- moderate impairment: 10 mg daily;
- severe impairment: 15 mg every 48 h;
- ESRD: 15 mg three times a week after dialysis.

The current label starts at 60 mL/min and gives 5 mg daily for patients on dialysis. So the 50 is the study's original recommendation; when and why the label changed is not established.

**Label history (v3).** Five earlier labels trace the myeloma threshold:

| Label | Myeloma kidney table |
|---|---|
| June 2006 (s001) | None. Renal impairment had not been studied, and patients with it were excluded from the trials. |
| About December 2008 (s006/s016/s017; the first table found) | **30 ≤ CLcr < 60** → 10 mg every 24 h. The text above says adjust below 60. |
| February 2015 (s041) | A separate myeloma table at **30–50**, while the MDS and MCL table and the text above both say below 60. The label contradicts itself. |
| February 2017 (s049) and September 2017 (s051) | One table at **30 to 60** for all indications. The 2023 label keeps it. |

So **60 was the label's threshold from the first kidney table**, even though the study abstract recommended below 50. The 2015 myeloma table is the exception. Not established: why the label set 60, and whether labels between 2009 and 2015 used 50 or 60.

**To confirm:** the review for the supplement that first added kidney dosing (about 2008).

## Who the renal study enrolled (v3)

The labels of about December 2008 and February 2015 both say the kidney dosing is "based on a pharmacokinetic study in patients with renal impairment due to non-malignant conditions". So CC-5013-PK-001 enrolled people whose kidney disease was not caused by cancer; it did not enrol myeloma patients. The pinned EMA extract and the Hughes scope still say the study's disease context is "not established". They are left unchanged here and should be updated in their next versions. When the myeloma-based Hughes and Kim models are compared with this study, the population difference is one possible reason for disagreement. This has not been tested.

## Observed creatinine clearance in each study group (v3)

The label of about December 2008 gives each group's actual creatinine clearance range:

| Group | n | CrCl (mL/min) |
|---|---|---|
| Normal (healthy subjects of similar age) | 7 | 83–145 |
| Mild | 5 | 57–74 |
| Moderate | 6 | 33–46 |
| Severe | 6 | 17–29 |
| ESRD on dialysis | 6 | — |

These are the same 7/5/6/6/6 groups as the EMA table. The 2023 label's 3/8/9/4/6 is a later regrouping of the same 30 people.

The Hughes and Kim checks sampled across the group definitions (moderate 30–50, severe 10–30 or similar), and each observed range lies inside the interval sampled, so the recorded results are unlikely to change. The observed moderate range partly lies below the Hughes model's data (36 mL/min), and the severe range lies wholly below it. Any recheck with these ranges needs a new locked plan.

## 4. Mild versus normal exposure: below 20% or 27%? (difference recorded, v2)

The abstract says the mean AUC difference between normal function and mild impairment was below 20%. The EMA Table 4 means (2,181 and 2,767 ng·h/mL) differ by 27%. The abstract may use a statistic it doesn't name, such as geometric or least-squares means. The platform uses the EMA arithmetic means, and both models' mild-group results were consistent either way.

## 5. Protein binding (difference recorded, v2)

The sources report different binding figures, by different methods and in different populations:

| Source | Protein binding |
|---|---|
| Label (in vitro) | about 30% |
| Study abstract (subjects) | about 35–44% |
| EMA report | 23% (myeloma patients), 29% (healthy volunteers) |
| Kim 2026 (estimated unbound fraction 0.614) | about 39% |

The only binding value any platform calculation uses is Kim's own estimate.

## Also corrected in evidence status v8

The Hughes transcription layer said the supplementary control stream was not retrieved. It was reviewed on 13 October 2026 for the random-effect and residual-error blocks (`hughes_variability_extract_v1.json`). The structural parameters have not yet been cross-checked against it.
