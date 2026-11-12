# AI-generated extraction (Claude Fable, second account), not a review

## Published parameter precision: Gupta 2017 (ixazomib), Luo 2021 (daratumumab), Li 2017 (pomalidomide)

| | |
|---|---|
| Date | 12 November 2026 |
| Model identifier | `claude-fable-5-2` |
| Purpose | Extraction only, for the platform's "acceptance rule v2" (finding F03). Nothing is computed, converted or proposed. Nothing here is validated for clinical use. |
| Repository read | `astridcmarin/marlo-scientific`, branch `main`, commit `0dce8e4452b2544fe1283b81ab2e1d0293eb6978` (read only; nothing changed; no pull request, issue or commit). Read: the three extracts named in the task and `hughes_parameter_precision_v2.json`. Nothing under `instance/` and no eligibility material was opened. |

## Summary

| Paper | Precision printed for the final model | Bootstrap interval printed? | Covariance or correlation matrix of the estimates? |
|---|---|---|---|
| Gupta 2017 | %RSE for every parameter (Table 3) | **No.** A bootstrap of 1000 datasets is described in the Methods; no bootstrap result appears in the article. | Not published |
| Luo 2021 | %RSE for every parameter (Table S1, supplement) | **No.** The article and Table S1 do not mention a bootstrap. | Not published. Table S1 gives only a condition number computed from it. |
| Li 2017 | **No %RSE or SE.** Bootstrap median and interval only (Tables 3 and 5) | **Yes, but 90%, not 95%,** for Table 3. One column of Table 5 is headed "95%". | Not published |

Two points matter for the rule:
- **None of the three papers prints a bootstrap 95% interval for the model the platform uses.** Gupta and Luo give %RSE only; Li gives a 90% interval and no %RSE.
- **Li 2017 has two "final" models** (renal function as categories, Table 3; as a continuous variable, Table 5). The platform's extract uses Table 3. Both are given below.

## How the values were read and checked

| File (as received) | SHA-256, first 16 | Matches the platform's pin? | How read |
|---|---|---|---|
| Gupta 2017, `s40262-017-0526-4.pdf`, 14 pages | `6100c8616805f0b6` | yes | Table 3 read from the rendered page image (PDF page 7) and from the text layer |
| Luo 2021, `JCPH-61-614.pdf`, 14 pages | `18157ed6db5d1c36` | yes | Text layer |
| Luo 2021 supplement, `JCPH-61-614-s003.docx` | `89c48633b71917d4` | yes | Table cells read from the Word document's XML |
| Li 2017, `cpaa-9-133.pdf`, 13 pages | `fc32441820ae03d5` | yes | Tables 3 and 5 read from the rendered page images (PDF pages 5 and 8) and from the text layer |

- **Row quotes** (in `code` type) are copied from the text layer (`pdftotext -layout`), with runs of spaces reduced to one. For Luo they are the Word table's cells joined by ` | `.
- **Quote check:** a script searched for every row quote and every quoted sentence in the extracted text. The result is at the end of this document.
- **Luo supplementary methods** (`JCPH-61-614-s002.docx`) were not attached and were not read.
- **Gupta supplementary material** was not attached and was not read.

---

## 1. Gupta 2017, ixazomib

**Source.** Gupta N, et al. *Clin Pharmacokinet* 2017;56(11):1355–1368. Table 3, "Model parameters estimated for the final model", PDF page 7 (article page 1361).

**What the columns are.** "Estimate" is on the log scale for the structural parameters; "RSE (%)" belongs to that estimate. The table note says: "Model parameters and RSEs correspond to the raw estimates provided by NONMEM. The untransformed parameters show the corresponding pharmacokinetic parameters". For the random effects: "Inter-individual variability shown as % coefficient of variation." and the starred RSE "is derived as" 100%·se(ω²)/ω² (the formula is typeset; in the text layer it reads `100%sex2/x2`).

**Interval type.** None is printed. No bootstrap median or interval appears in the article.

### Fixed effects and covariate effect

| Platform name | Paper label | Estimate (as printed) | Untransformed (as printed) | RSE (%) | Bootstrap median and interval | Fixed? | Row quote (Table 3, PDF p. 7) |
|---|---|---|---|---|---|---|---|
| `ka_per_h` | Absorption rate constant (log Ka) | −1.09 | 0.34/h ∼ t1/2 = 124 min | 8 | not reported | no | `Absorption rate constant (log Ka) -1.09 8 0.34/h * t1/2 = 124 min` |
| `cl_l_h` | Systemic clearance (log CL) | 0.62 | 1.86 L/h | 7 | not reported | no | `Systemic clearance (log CL) 0.62 7 1.86 L/h` |
| `v2_l` | Central volume of distribution (log V2) | 2.62 | 13.7 L | 4 | not reported | no | `Central volume of distribution (log V2) 2.62 4 13.7 L` |
| `f` | Absolute bioavailability (log F) | −0.55 | 58% | 9 | not reported | no | `Absolute bioavailability (log F) -0.55 9 58%` |
| `q3_l_h` | First inter-compartmental clearance (log Q3) | 1.65 | 5.18 L/h | 7 | not reported | no | `First inter-compartmental clearance (log Q3) 1.65 7 5.18 L/h` |
| `v3_l` | Volume of the first peripheral compartment (log V3) | 5.73 | 309 L | 1 | not reported | no | `Volume of the first peripheral compartment (log V3) 5.73 1 309 L` |
| `q4_l_h` | Second inter-compartmental clearance (log Q4) | 3.26 | 26.1 L/h | 2 | not reported | no | `Second inter-compartmental clearance (log Q4) 3.26 2 26.1 L/h` |
| `v4_l` | Volume of the second peripheral compartment (log V4) | 5.32 | 205 L | 1 | not reported | no | `Volume of the second peripheral compartment (log V4) 5.32 1 205 L` |
| `tlag_h` | Absorption lag time (log TLAG) | −1.52 | 13 min | 0 | not reported | not stated as fixed (see note) | `Absorption lag time (log TLAG) -1.52 0 13 min` |
| `bsa_exponent_on_v4` | Impact of BSA on V4 (V4[BSA]) | 2.06 | −37 and +46% at the 5th and 95th percentile (1.5 and 2.25 m2) on V4 relative to median BSA (1.87 m2) | 18 | not reported | no | `Impact of BSA on V4 (V4[BSA]) 2.06 18 -37 and ?46% at the 5th and 95th` |

### Random effects and residual error

| Platform name | Paper label | Estimate | RSE* (%) | η shrinkage (%) | Bootstrap median and interval | Fixed? | Row quote (Table 3, PDF p. 7) |
|---|---|---|---|---|---|---|---|
| `iiv_cl_cv_percent` | Inter-individual variability on log CL | 44% | 11 | 21 | not reported | no | `Inter-individual variability on log CL 44% 11 21` |
| `iiv_f_cv_percent` | Inter-individual variability on log F | 73% | 8 | 13 | not reported | no | `Inter-individual variability on log F 73% 8 13` |
| `correlation_log_cl_log_f` | Correlation between log CL and log F | 82% | 11 | (blank) | not reported | no | `Correlation between log CL and log F 82% 11` |
| `iiv_v4_cv_percent` | Inter-individual variability on log V4 | 79% | 12 | 37 | not reported | no | `Inter-individual variability on log V4 79% 12 37` |
| `residual_error.initial_sd` | Initial sd of the residual error (SD1) | 1.90 | 11 | (blank) | not reported | no | `Initial sd of the residual error (SD1) 1.90 11` |
| `residual_error.steady_state_sd` | Steady state sd of the residual error (SD0) | 0.46 | 3 | (blank) | not reported | no | `Steady state sd of the residual error (SD0) 0.46 3` |
| `residual_error.time_constant_sd_per_h` | Time constant of residual error sd (KSD) | 0.84 | 22 | (blank) | not reported | no | `Time constant of residual error sd (KSD) 0.84 22 t1/2 = 50 min` |
| (none) | Residual random variability | (blank) | (blank) | 7 | not reported | — | `Residual random variability 7` |

**Notes on the cells.**
- **Characters the text layer garbles.** On the page image the Ka row reads "0.34/h ∼ t1/2 = 124 min" and the BSA row reads "+46%"; the text layer prints `*` and `?`. The minus signs are printed as "−". The values themselves are clear on the image.
- **Lag time, RSE "0".** The table prints 0. The article does not say the parameter was fixed, and does not explain the zero. Whether it is a rounded small value or a fixed parameter is not stated.
- **Correlation row.** The estimate is printed "82%" and the RSE "11". The starred RSE definition in the note refers to inter-individual variability; whether it also applies to the correlation is not stated.
- **Residual error rows.** Their units are not printed in Table 3 (the platform's extract names the third one "per h"; the table itself gives only "t1/2 = 50 min").

### Sentences about precision and the bootstrap

- Methods, PDF page 6 (article page 1360): "Model robustness and parameter estimates were assessed by bootstrap based on 1000 resampled datasets (with replacement)."
- Results, PDF page 7 (article page 1361): "The final model provided parameter estimates with good precision (relative standard error" ≤22%). The "≤" sign prints as `B` in the text layer.
- No sentence reports how many bootstrap runs were successful, and no bootstrap result is given.

### Not reported in the article

- Bootstrap medians and intervals, for any parameter.
- The number of successful bootstrap runs.
- A covariance or correlation matrix of the estimates. (The Methods list "condition number" among the criteria used; no value is printed in the article.)
- Standard errors on the untransformed scale.
- How %CV was obtained from ω².
- Whether the lag time was fixed.

---

## 2. Luo 2021, daratumumab

**Source.** Luo MM, et al. *J Clin Pharmacol* 2021;61(5):614–627. Supplement file `JCPH-61-614-s003.docx`, "Table S1. Parameter Estimates of the popPK Model of DARA Based on Combined DARA SC and DARA IV Data". The article points to it on PDF page 5 (article page 618): "The parameter estimates of the final model resulting from covariate analysis are provided in Table S1."

**What the columns are.** Parameter, unit | Estimate | RSE (%) | IIV (%CV) | RSE (%). The table note says: "For IIV, RSE% is given for %CV and is an approximate value."

**Interval type.** None is printed. The file is a Word document and has no page numbers; the location is the table row.

### Fixed effects, covariate effects, random effects and residual error

| Platform name | Paper label | Estimate | RSE (%) | Platform name for IIV | IIV (%CV) | RSE (%) of IIV | Bootstrap median and interval | Fixed? | Row quote (Table S1) |
|---|---|---|---|---|---|---|---|---|---|
| `cl_l_h` | CL (L/h) | 0.00496 | 8.4 | `iiv_cl_cv_percent` | 58.7 | 4.9 | not reported | no | `CL (L/h) \| 0.00496 \| 8.4 \| 58.7 \| 4.9` |
| `alb_exponent_on_cl` | ALB on CL | −1.85 | 12.1 | — | - | - | not reported | no | `ALB on CL \| −1.85 \| 12.1 \| - \| -` |
| `wt_exponent_on_cl` | WT on CL | 1.24 | 10.6 | — | - | - | not reported | no | `WT on CL \| 1.24 \| 10.6 \| - \| -` |
| `igg_shift_on_cl` | TPMM on CL | 1.26 | 14.4 | — | - | - | not reported | no | `TPMM on CL \| 1.26 \| 14.4 \| - \| -` |
| `v1_l` | V1 (L) | 5.25 | 4.1 | `iiv_v1_cv_percent` | 36.9 | 3.7 | not reported | no | `V1 (L) \| 5.25 \| 4.1 \| 36.9 \| 3.7` |
| `wt_exponent_on_v1` | WT on V1 | 0.91 | 11.5 | — | - | - | not reported | no | `WT on V1 \| 0.91 \| 11.5 \| - \| -` |
| `sex_shift_on_v1` | Sex on V1 | −0.105 | 45.4 | — | - | - | not reported | no | `Sex on V1 \| −0.105 \| 45.4 \| - \| -` |
| `v2_l` | V2 (L) | 3.78 | 7.0 | — | - | - | not reported | no | `V2 (L) \| 3.78 \| 7.0 \| - \| -` |
| `q_l_h` | Q (L/h) | 0.00955 | 8.0 | — | - | - | not reported | no | `Q (L/h) \| 0.00955 \| 8.0 \| - \| -` |
| `vmax_mg_h` | Vmax (mg/h) | 1.15 | 9.7 | `iiv_vmax_cv_percent` | 67.4 | 8.4 | not reported | no | `Vmax (mg/h) \| 1.15 \| 9.7 \| 67.4 \| 8.4` |
| `kdes_per_h` | KDES (1/h) | 0.0000783 | 33.3 | `iiv_kdes_cv_percent` | 145.9 | 20.8 | not reported | no | `KDES (1/h) \| 0.0000783 \| 33.3 \| 145.9 \| 20.8` |
| `km_ug_ml` | Km (µg/mL) | 2.56 | 16.0 | — | (empty cell) | (empty cell) | not reported | no | `Km (µg/mL) \| 2.56 \| 16.0 \|  \| ` |
| `ka_per_h` | Ka (1/h) | 0.0117 | 5.8 | `iiv_ka_cv_percent` | 36.1 | 12.4 | not reported | no | `Ka (1/h) \| 0.0117 \| 5.8 \| 36.1 \| 12.4` |
| `f_sc` | F1 | 0.689 | 2.7 | — | - | - | not reported | no | `F1 \| 0.689 \| 2.7 \| - \| -` |
| `residual_error.additive_log_scale_cv_percent` | ADD ERR (%CV) | 34.8 | 0.3 | — | - | - | not reported | no | `ADD ERR (%CV) \| 34.8 \| 0.3 \| - \| -` |

**Notes on the cells.**
- **Km.** Its two IIV cells are empty, where every other parameter without IIV has a hyphen. The table does not say why.
- **Subscripts.** V1, V2, Vmax, KDES, Km and Ka are printed with subscripts in the Word file; they are written on one line here.
- **Minus signs** are the character "−" in the file.
- **No parameter is marked as fixed** in the table or its note.
- **Correlations between random effects** are not in the table.

### Sentences about precision and the bootstrap

- Table S1 note: "Objective function value = −1759.836. Conditional number = 42.8. Conditional number was calculated as the ratio of the largest to smallest eigenvalue of correlation matrix of estimate."
- Table S1 note: "For IIV, RSE% is given for %CV and is an approximate value."
- Article, Methods, PDF page 3 (article page 616): the model "was further evaluated by the" goodness-of-fit "(GOF) plots and visual predictive checks."
- **The word "bootstrap" does not occur** in the article text or in Table S1.

### Not reported in the article or Table S1

- Any bootstrap: runs, medians or intervals.
- Any confidence interval for a parameter.
- The covariance or correlation matrix of the estimates. Only the condition number derived from the correlation matrix is given.
- Standard errors (only %RSE).
- IIV, or a statement of its absence, for Km.
- Correlations between random effects.
- Whether the supplementary methods (`s002`) say more: that file was not read here.

---

## 3. Li 2017, pomalidomide

**Source.** Li Y, et al. *Clin Pharmacol Adv Appl* 2017;9:133–145.

**Interval type.** Nonparametric bootstrap, 5th to 95th percentiles: a **90%** interval, from 500 datasets. No %RSE and no standard error is printed anywhere in the article.

### 3.1 Table 3: final model with renal function as a categorical variable (the model in the platform's extract)

"Table 3 Pharmacokinetic parameter estimates from the final model with renal function treated as a categorical variable", PDF page 5 (journal page 137). Columns: PK parameter | Estimate | Bootstrap median estimate | 90% bootstrap CI.

| Platform name | Paper label | Estimate | %RSE or SE | Bootstrap median | Interval as printed | Interval type | Fixed? | Row quote (Table 3, PDF p. 5) |
|---|---|---|---|---|---|---|---|---|
| `ka_per_h` | Ka (1/h) | 0.724 | not reported | 0.774 | 0.533–1.23 | 90% bootstrap | no | `Ka (1/h) 0.724 0.774 0.533–1.23` |
| `v_f_l` | V/F (L) | 58.300 | not reported | 58.521 | 51.597–66.055 | 90% bootstrap | no | `V/F (L) 58.300 58.521 51.597–66.055` |
| `cl_f_normal_renal_l_h` | CL/Fnormal (L/h) | 5.130 | not reported | 5.159 | 4.283–6.069 | 90% bootstrap | no | `CL/Fnormal (L/h) 5.130 5.159 4.283–6.069` |
| `cl_f_ratio_moderate` | CL/F ratio (group 2 vs group 1) | 1.020 | not reported | 1.019 | 0.848–1.195 | 90% bootstrap | no | `CL/F ratio (group 2 vs group 1) 1.020 1.019 0.848–1.195` |
| `cl_f_ratio_severe_no_dialysis` | CL/F ratio (group 3 vs group 1) | 1.010 | not reported | 1.018 | 0.871–1.169 | 90% bootstrap | no | `CL/F ratio (group 3 vs group 1) 1.010 1.018 0.871–1.169` |
| `cl_f_ratio_severe_dialysis` | CL/F ratio (group 4 vs group 1) | 0.724 | not reported | 0.729 | 0.606–0.844 | 90% bootstrap | no | `CL/F ratio (group 4 vs group 1) 0.724 0.729 0.606–0.844` |
| `tlag_h` | Tlag (h) | 0.154 | not reported | 0.183 | 0.002–0.43 | 90% bootstrap | no | `Tlag (h) 0.154 0.183 0.002–0.43` |
| `omega2.ka` | ω2 (Ka) | 0.782 | not reported | 0.804 | 0.441–1.387 | 90% bootstrap | no | `ω2 (Ka) 0.782 0.804 0.441–1.387` |
| `omega2.v_f` | ω2 (V/F) | 0.139 | not reported | 0.136 | 0.069–0.236 | 90% bootstrap | no | `ω2 (V/F) 0.139 0.136 0.069–0.236` |
| `omega2.cov_v_cl` | ω (V/F):ω (CL/F) | 0.163 | not reported | 0.156 | 0.088–0.236 | 90% bootstrap | no | `ω (V/F):ω (CL/F) 0.163 0.156 0.088–0.236` |
| `omega2.cl_f` | ω2 (CL/F) | 0.198 | not reported | 0.189 | 0.121–0.273 | 90% bootstrap | no | `ω2 (CL/F) 0.198 0.189 0.121–0.273` |
| `residual_delta2` | δ2 | 0.341 | not reported | 0.321 | 0.194–0.459 | 90% bootstrap | no | `δ2 0.341 0.321 0.194–0.459` |

**Notes on the cells.**
- **Random effects are variances** (the table note: "ω2, variance of interpatient variability; δ2, variance of intra-patient variability"), not %CV.
- **The row "ω (V/F):ω (CL/F)"** is printed without a superscript 2 and is not defined in the table note. The Results call it "associated covariance". Whether the value is a covariance or a correlation is not stated in the table; the platform's extract names it `cov_v_cl`.
- **Residual error symbol.** Table 3 uses δ2; Equation 2 in the Methods calls the residual variance σ2.
- **Group definitions** are in the table note: group 1 normal renal function; group 2 moderately impaired; group 3 severely impaired not requiring haemodialysis; group 4 severely impaired requiring haemodialysis.
- **Location.** The platform's extract gives Table 3 as "journal page 139". In this file Table 3 is on PDF page 5, which is journal page 137 (PDF page 4 is numbered 136). Journal page 139 holds Table 4.

### 3.2 Table 5: final model with renal function as a continuous variable (no platform names)

"Table 5 Pharmacokinetic parameter estimates from the final model with renal function treated as a continuous variable", PDF page 8 (journal page 140). Two models side by side. **The interval column for the CrCl model is headed "95% bootstrap CI"; the one for the eGFR model is headed "90% bootstrap CI".** The Methods describe only a 90% interval, so the "95%" heading may be a misprint; the article does not say. No bootstrap median is printed in this table.

| Paper label | CrCl model: estimate | CrCl model: interval (headed "95% bootstrap CI") | eGFR model: estimate | eGFR model: interval (headed "90% bootstrap CI") | %RSE or SE | Fixed? | Row quote (Table 5, PDF p. 8) |
|---|---|---|---|---|---|---|---|
| Ka (1/h) | 0.68 | 0.522–0.931 | 0.678 | 0.526–0.948 | not reported | no | `Ka (1/h) 0.68 0.522–0.931 0.678 0.526–0.948` |
| V/F (L) | 60.7 | 54.393–68.717 | 60.5 | 54.502–69.225 | not reported | no | `V/F (L) 60.7 54.393–68.717 60.5 54.502–69.225` |
| Intercept (L/h) | 3.71 | 2.321–4.796 | 3.96 | 2.577–5.086 | not reported | no | `Intercept (L/h) 3.71 2.321–4.796 3.96 2.577–5.086` |
| Slope | 0.0469 | 0.013–0.095 | 0.0483 | 0.001–0.115 | not reported | no | `Slope 0.0469 0.013–0.095 0.0483 0.001–0.115` |
| CrCl0 (mL/min) or eGFR0 (mL/min/1.73 m2) | 37.7 | 35.027–50.343 | 26.0 | 25.01–30.899 | not reported | no | `CrCl0 (mL/min) or eGFR0 (mL/min/1.73 m2) 37.7 35.027–50.343 26.0 25.01–30.899` |
| ω2 (Ka) | 0.986 | 0.638–1.467 | 0.99 | 0.64–1.46 | not reported | no | `ω2 (Ka) 0.986 0.638–1.467 0.99 0.64–1.46` |
| ω2 (V/F) | 0.0293 | 0–0.081 | 0.0278 | 0–0.082 | not reported | no | `ω2 (V/F) 0.0293 0–0.081 0.0278 0–0.082` |
| ω2 (intercept) | 0.163 | 0.076–0.383 | 0.147 | 0.062–0.297 | not reported | no | `ω2 (intercept) 0.163 0.076–0.383 0.147 0.062–0.297` |
| ω2 (slope) | 0.3 | 0–0.813 | 0.516 | 0–3.837 | not reported | no | `ω2 (slope) 0.3 0–0.813 0.516 0–3.837` |
| δ2 | 0.351 | 0.217–0.471 | 0.351 | 0.221–0.492 | not reported | no | `δ2 0.351 0.217–0.471 0.351 0.221–0.492` |

**Notes on the cells.**
- No lag-time row is printed in Table 5.
- The unit of "Slope" is not printed.
- Several lower bounds are printed as "0".

### Sentences about the bootstrap

- Methods, PDF page 3 (journal page 135): "The nonparametric bootstrap approach was used to evaluate the stability of the final PK parameter estimates and 90% CI. There were 500 bootstrap data sets, and the final model was fit to each. Every model parameter was estimated for each set; 96% of the bootstrap runs were successful. For each of the 500 estimates, median and nonparametric 90% CI (5th-95th percentiles) were calculated for each parameter."
- Results, PDF page 5 (journal page 137): "The model parameters were precisely estimated with the base model as observed from the narrow 90% bootstrap CI. The estimated IIV and associated covariance were reasonably precise."
- Results, PDF page 5: "The bootstrap replicates showed similar median values of the parameters with narrow 90% CIs, compared with the original NONMEM estimates (Table 3)."
- Table notes (Tables 3 and 5): "Bootstrap CI values were taken from bootstrap calculation."

Two things in these sentences are unclear and are left as printed:
- "96% of the bootstrap runs were successful" is followed by "each of the 500 estimates". Whether the medians and intervals use all 500 runs or only the successful ones is not stated.
- The Results sentence says "with the base model" while Table 3 is titled "final model".

### Not reported in the article

- %RSE or standard errors, for any parameter in either table.
- A 95% bootstrap interval for the Table 3 model.
- Bootstrap medians for the Table 5 models.
- A covariance or correlation matrix of the estimates.
- The number of successful bootstrap runs as a count (only "96%").
- Which of the Table 5 headings ("95%" or "90%") is intended, if they are not both correct.
- Whether "ω (V/F):ω (CL/F)" is a covariance or a correlation.
- A lag time for the Table 5 models.

---

## Quote check

A script compared every row quote and every quoted sentence in this document with the extracted text of the files (PDF text layers in layout and reading order; the Word table's cells), after reducing runs of spaces and removing line-break hyphens.

| Checked | Found | Not found |
|---|---|---|
| Row quotes, Gupta Table 3 | 18 of 18 | 0 |
| Row quotes, Luo Table S1 (exact match of the Word table row) | 15 of 15 | 0 |
| Row quotes, Li Tables 3 and 5 | 22 of 22 | 0 |
| Quoted sentences and table-note phrases (all three papers) | 18 of 18 | 0 |

Limits of the check:
- It confirms that the quoted text is in the file's text layer. It does not confirm that the text layer matches the printed page; for that, Gupta Table 3 and Li Tables 3 and 5 were also read from the page images, and they agree.
- Two Gupta row quotes carry text-layer characters that differ from the printed page (`*` for "∼", `?` for "+"), as noted in section 1.
- The Gupta BSA row quote stops at the end of the first printed line of that cell.

## Sources

1. Gupta N, Diderichsen PM, Hanley MJ, Berg D, van de Velde H, Harvey RD, Venkatakrishnan K. Population pharmacokinetic analysis of ixazomib, an oral proteasome inhibitor, including data from the phase III TOURMALINE-MM1 study to inform labelling. *Clin Pharmacokinet* 2017;56(11):1355–1368. <https://doi.org/10.1007/s40262-017-0526-4>
2. Luo MM, Usmani SZ, Mateos MV, et al. Exposure-response and population pharmacokinetic analyses of a novel subcutaneous formulation of daratumumab administered to multiple myeloma patients. *J Clin Pharmacol* 2021;61(5):614–627, with supplement Table S1. <https://doi.org/10.1002/jcph.1771>
3. Li Y, Wang X, O'Mara E, et al. Population pharmacokinetics of pomalidomide in patients with relapsed or refractory multiple myeloma with various degrees of impaired renal function. *Clin Pharmacol Adv Appl* 2017;9:133–145. <https://doi.org/10.2147/CPAA.S144606>
4. Marlo Scientific, <https://github.com/astridcmarin/marlo-scientific>, branch `main`, commit `0dce8e4452b2544fe1283b81ab2e1d0293eb6978`: `intelligence_store/data/ixazomib_pk_gupta_2017_extract_v1.json`, `daratumumab_pk_luo_2021_extract_v1.json`, `pomalidomide_popk_li_2017_extract_v1.json`, `hughes_parameter_precision_v2.json`.

*End of extraction. AI-generated; not reviewed by a human; not a review.*

---

## Handling (12 November 2026, main session)

- **Spot-checked against the owner's files:** Gupta 2017 (SHA-256 `6100c8616805…`, matches the pin), Li 2017 and the Luo 2021 Table S1 document. Seven row quotes and sentences were found in the text layers (two only after joining line breaks), the Luo values and the condition-number note are in the Word table, and the word "bootstrap" does not occur in Table S1. Not every row was re-checked.
- **What it means for acceptance rule v2:** none of the three papers publishes a 95% bootstrap interval for the model the platform uses. Gupta 2017 and Luo 2021 give %RSE only (Gupta's on the log scale); Li 2017 gives 90% bootstrap intervals and no %RSE, and its Table 5 heads one column "95%". The rule cannot be extended to these models unchanged. A later plan version must decide, before running, how %RSE (on the estimation scale) and 90% intervals are turned into draws.
- **Two corrections for the platform's extracts**, for a new versioned file when they are next touched: Li 2017 Table 3 is on journal page 137 (PDF page 5), not 139; and Li's "ω (V/F):ω (CL/F)" is not stated to be a covariance.
- Nothing is pinned from this document yet.

