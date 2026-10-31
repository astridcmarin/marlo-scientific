# Source reconciliation: lenalidomide renal evidence

Recorded 31 October 2026. Pinned record: `intelligence_store/data/lenalidomide_renal_source_reconciliation_v2.json` (v2 adds the renal study's conference abstract; v1 kept) (loader `lenalidomide_label.load_renal_reconciliation`; every number recomputed in `tests/test_lenalidomide_reconciliation.py`).

Three differences appeared when the REVLIMID label (revision 3/2023) was added next to the EMA assessment table already used by the platform. Locked check results are not changed by any of them.

## 1. Renal study group sizes: 3 or 7 subjects with normal function? (reconciled)

The study publication (Chen et al., *J Clin Pharmacol* 2007;47:1466–1475) settles this. Subjects were grouped by creatinine clearance **measured from a 24-hour urine collection**: 7 normal, 5 mild, 6 moderate, 6 severe and 6 ESRD. That is the grouping used by the EMA table and the 2008 label. The authors also reclassified everyone by the **Cockcroft–Gault** estimate (Table IV), which gives 11 normal-or-mild, 9 moderate, 4 severe and 6 ESRD. The 2023 label's 3 healthy + 8 mild (= 11), 9, 4 and 6 is that reclassification.

The label's clearance and half-life results match the measured-clearance groups. The platform's reference (normal group, n = 7, EMA arithmetic mean AUC 2,181 ng·h/mL; publication geometric mean 2,091) is unaffected.

The conference abstract (*J Clin Oncol* 2007;25(18_suppl):2520) gives the same 7/5/6/6/6 grouping.

## 2. Which clearance defined the groups in the Hughes and Kim checks? (correction)

Both locked plans said the study's clearance method was not stated. **That was wrong.** The EMA page and the publication both say measured creatinine clearance (24-hour urine). The checks treated the group ranges as Cockcroft–Gault values, the models' own covariate.

**How much this matters, from the publication (Table IV).** The same subjects were classified both ways:

| Group | Exposure ratio, measured CrCl grouping | Exposure ratio, Cockcroft–Gault grouping |
|---|---|---|
| Moderate | 259% | 237% |
| Severe | 352% | 374% |
| ESRD | 477% | 472% |

The difference is under 10%. It does not explain the Hughes model's 2-fold under-prediction in moderate impairment, and it explains little of Kim's 1.3-fold under-prediction in severe impairment. The earlier model-based bound (up to 1.22-fold for Kim) is superseded. Evidence status v9 records this on both scorecards.

The scope band edges (30 and 50 mL/min) come from the measured-clearance groups but are applied to each model's estimated clearance. This is recorded here; the scope files are unchanged.

## 3. First renal dose step: 50 or 60 mL/min? (difference recorded)

The label's Table 3 starts at creatinine clearance 30–60 mL/min. The platform's reference note quotes Chen 2017, a secondary source, describing reductions below 50 mL/min. No platform calculation uses a dose threshold. The 50 mL/min figures in scopes and summaries are the study's moderate-group boundary, not a dose threshold.

**Origin of the 50.** The publication's Table V and the abstract both recommend dose adjustment below 50 mL/min. The abstract's conclusion was "dosage adjustment should be considered for patients with CLCr < 50 mL/min". Its recommended myeloma starting doses were:
- moderate impairment: 10 mg daily;
- severe impairment: 15 mg every 48 h;
- ESRD: 15 mg three times a week after dialysis.

The current label starts at 60 mL/min and gives 5 mg daily for patients on dialysis. So the 50 is the study's own recommendation. As the label history below shows, the label used 60 from its first kidney table, apart from the February 2015 myeloma table.

**Label history (v3).** Five earlier labels trace the myeloma threshold:

| Label | Myeloma kidney table |
|---|---|
| June 2006 (s001) | None. Renal impairment had not been studied, and patients with it were excluded from the trials. |
| About December 2008 (s006/s016/s017; the first table found) | **30 ≤ CLcr < 60** → 10 mg every 24 h. The text above says adjust below 60. |
| February 2015 (s041) | A separate myeloma table at **30–50**, while the MDS and MCL table and the text above both say below 60. The label contradicts itself. |
| February 2017 (s049) and September 2017 (s051) | One table at **30 to 60** for all indications. The 2023 label keeps it. |

So **60 was the label's threshold from the first kidney table**, even though the study abstract recommended below 50. The 2015 myeloma table is the exception. Not established: why the label set 60, and whether labels between 2009 and 2015 used 50 or 60.

**To confirm:** the review for the supplement that first added kidney dosing (about 2008).

## Who the renal study enrolled

The publication: "subjects with renal impairment due to nonmalignant conditions", in most cases caused by "cardiovascular and/or endocrine disorders". The 2008 and 2015 labels say the same. The authors note that the dose recommendations "remain to be evaluated in renally impaired MM and MDS patients". So the outside study behind the Hughes and Kim checks did not enrol cancer patients. The population difference is one possible reason the models disagree with it; this has not been tested.

The pinned EMA extract and the Hughes scope still say the study's disease context is "not established". They are left unchanged here and should be updated in their next versions.

## Observed creatinine clearance in each study group (v3)

The label of about December 2008 gives each group's actual creatinine clearance range:

| Group | n | CrCl (mL/min) |
|---|---|---|
| Normal (healthy subjects of similar age) | 7 | 83–145 |
| Mild | 5 | 57–74 |
| Moderate | 6 | 33–46 |
| Severe | 6 | 17–29 |
| ESRD on dialysis | 6 | — |

These are the same 7/5/6/6/6 groups as the EMA table. The publication's Table I adds each group's sex, age and weight, and its mean measured clearance (SD):

| Group | Mean CrCl (SD), mL/min | Mean weight, kg | Mean age, years |
|---|---|---|---|
| Normal | 102.2 (21.9) | 80 | 58 |
| Mild | 64.6 (8.3) | 74 | 68 |
| Moderate | 39.1 (5.9) | 96 | 59 |
| Severe | 23.9 (4.3) | 75 | 66 |
| ESRD | — | 97 | 50 |

A new locked check could use these in place of the assumed demographics.

The Hughes and Kim checks sampled across the group definitions (moderate 30–50, severe 10–30 or similar), and each observed range lies inside the interval sampled, so the recorded results are unlikely to change. The observed moderate range partly lies below the Hughes model's data (36 mL/min), and the severe range lies wholly below it. Any recheck with these ranges needs a new locked plan.

## 4. Mild versus normal exposure: below 20% or 27%? (resolved)

The abstract says the mean AUC difference between normal function and mild impairment was below 20%. The publication's Table II gives geometric means of 2,091 and 2,627 ng·h/mL, a 26% difference. Its text calls the normal-versus-mild differences "minor to modest (11%–32%)" and not statistically significant. The EMA arithmetic means differ by 27%. So the abstract's "< 20%" is not supported by the full paper. The models' mild-group results were consistent either way.

## 5. Protein binding (difference recorded)

The sources report different binding figures, by different methods and in different populations:

| Source | Protein binding |
|---|---|
| Label (in vitro) | about 30% |
| Publication (ex vivo, study subjects) | 40.2% normal; 35.4–44.3% across impaired groups |
| EMA report | 23% (myeloma patients), 29% (healthy volunteers) |
| Kim 2026 (estimated unbound fraction 0.614) | about 39% |

The only binding value any platform calculation uses is Kim's own estimate.

## Also corrected in evidence status v8

The Hughes transcription layer said the supplementary control stream was not retrieved. It was reviewed on 13 October 2026 for the random-effect and residual-error blocks (`hughes_variability_extract_v1.json`). The structural parameters have not yet been cross-checked against it.
