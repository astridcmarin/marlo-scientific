# AI review: lenalidomide kidney pathway model, body map and time course (4 November 2026)

**What this is.** A separate AI reviewer agent, started with only the repository and this instruction, reviewed the work: "find errors, inconsistencies and overclaims; do not praise, do not fix". It had not seen the conversation in which the work was done. **It is not an independent review.** It is the same kind of model as the one that did the work, and it was set up by the same session. It is recorded because it found real problems.

**Scope:**
- `lenalidomide_renal_pathways.py` (2.0a), `lenalidomide_esrd_dialysis.py` (2.0c) and `lenalidomide_renal_pathways_v2.py` (2.0d), with their plans, evidence and reports;
- `body_map.py`, `reference_physiology.py` and `body_map_time_course.py`;
- the claims about them in the docs, the findings file, evidence status v14 and dataset ledger v2.

**Verification of the review.** The platform's assistant re-checked the main findings before acting on them:
- Finding 1 was recomputed: moderate and severe classifications at F = 1, 0.95, 0.90 and 0.85.
- Finding 2 was recomputed: moderate renal clearance 29.1 against filtration 30.1 mL/min.
- Finding 4 was read from the 2.0d report: Kim severe for the current model over-predicts in two of three sensitivity scenarios.
- Finding 8 was read from the evidence quote: "Renal clearance was at least 190 ml/min".
- Finding 13 was read from the Chen 2012 extract basis: whole blood ngEq/g over plasma ngEq/ml.

## Findings and what was done

| # | Finding (severity) | Disposition |
|---|---|---|
| 1 | **Bioavailability F = 1 is assumed and never varied** (error). Renal clearance does not depend on F, but the derived non-renal clearance does: 28.7 mL/min at F = 1, 9.6 at 0.90, about 0 at 0.85. At F = 0.90 the 2.0a moderate group becomes consistent and the severe group over-predicted, so the finding "renal elimination falls faster than proportional", which motivated 2.0d, depends on F. | Stated in the docs, the body-map band text and limitations, evidence status v15 and findings v2. **A locked re-check across F = 0.85–1.0 is planned (2.0e).** |
| 2 | **At fu 0.77 the moderate group's renal clearance is at or below filtration alone** (29.1 vs 30.1 mL/min), so no form with positive secretion can reach the observed urine fraction. The 2.0d plan did not say so (error, structural). | Recorded here and in the 2.0d docs. The 2.0e plan states it. |
| 3 | **Misattributions left in the docs** (overclaim): "already flagged by the Bridoux check" (Digital human 1.1 doc); "not something specific to myeloma" and "Bridoux and the time course show clearance too high" (2.0d section). | Corrected in place, marked as corrections. The locked plan is unchanged. |
| 4 | **The myeloma comparison holds in the primary scenario only** (overclaim). Kim severe is over-predicted in 2 of 3 sensitivity scenarios; Bridoux normal and mild are over-predicted. | Body-map note now generated with the sensitivity result; findings v2; evidence status v15. |
| 5 | **Kim's moderate group (eGFR 30–60, median about 50 mL/min de-indexed) straddles the body map's moderate band**, and Kim's endpoint is clearance, not exposure (inconsistency). | The note says so in the moderate band and names each study's endpoint. |
| 6 | **"Reading A consistent in severe" was stated without qualification;** it holds in the primary scenario only (overclaim). | Docs, findings v2 and evidence status v15 corrected. |
| 7 | **The non-renal limitation pointed the wrong way,** and "the spread is what groups of 5–7 produce" was asserted, not computed (inconsistency). | Both corrected. |
| 8 | **"Renal clearance at least 190 mL/min" (EMA) against the model's 162 mL/min,** never reconciled (inconsistency). | Recorded as a limitation; reconciliation to follow. |
| 9 | **Hughes cited as support for "faster than proportional",** although Hughes scales as CrCl^0.224 (logic). | Corrected. |
| 10 | **The band text called CC-5013-PK-001 an "outside check"** and said "probably" (overclaim). | Reworded: "Source study disagrees", with the F dependence. |
| 11 | **The map's 10 and 140 mL/min ends were described as "the range the pathway check covered"** (minor). | Message reworded; a limitation states the study's group centres (about 24 to 102 mL/min). |
| 12 | **Statistics mixed without saying so:** arithmetic means and 95% CIs (2.0a) against geometric means and 90% CIs (2.0d, time course); steady-state against single-dose; dexamethasone co-dosing in Bridoux (minor). | Recorded here; to be stated in the 2.0e plan. |
| 13 | **Blood-to-plasma ratio is per gram of blood over per mL of plasma;** per volume about 0.98, so extraction about 13.4% rather than 14.1% (minor, units). | Recorded; a corrected reference-physiology version to follow. |
| 14 | **The ESRD "39% of the dose removed by dialysis" figure is not reconciled with what Chen 2007 reports** (minor). | Recorded; to check against the publication. |
| 15 | **Ledger gaps:** time course v2 is built from the Kim model (Kim's patients), and the v1 time-course check had no entry of its own (minor). | Dataset ledger v3. |
| 16 | **Stale wording:** status line, "CrCl known only as a range", "first blind model check" without the deviation, and "for all k" in the 2.0d plan when six values are tested (minor). | Corrected in the docs; the locked plan's wording stays and is noted here. |

## What the review checked and found correct

- The 2.0a calibration: CL 191.04, CLR 162.39, CLNR 28.66, filtration 84.7, secretion 77.69 mL/min; all six scenarios' classifications.
- The ESRD check.
- The 2.0d fitted k, recomputed independently as 1.4787.
- Two Bridoux and two Kim comparisons.
- The 2.0d code against its plan.
- Insensitivity of 2.0d to fu.
- Extraction ratios.
- Unit conversions.
- Kim's unbound-to-total conversion.
- The time-course regimens.
- Every SHA-256 pin.
- The doc tables against their reports.
- The ledger's blindness labels.
