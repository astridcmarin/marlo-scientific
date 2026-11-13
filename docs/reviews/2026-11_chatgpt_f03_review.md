# AI-generated methods review (ChatGPT), not an independent review

## Acceptance rule v2 (F03): the locked plan and its result

| | |
|---|---|
| Date | 12 November 2026 |
| Reviewer | ChatGPT (OpenAI), prompted by the platform owner (brief: supplemental-information/agent-collaborations/brief_chatgpt_f03_review_2026-11-12.md, not committed) |
| Repository read | `astridcmarin/marlo-scientific`, branch `batch-10`, commit `7efcabf` (the reviewer's statement); a code-and-report review, not a rerun |

The review is reproduced as received, then how each finding was handled.

---

Reviewed branch `batch-10` at [`7efcabf`](https://github.com/astridcmarin/marlo-scientific/tree/7efcabfefe55a7f1a834c3b1f6163b2e5354ad28). This was a code-and-report review, not an independent rerun.

**I found no obvious defect that invalidates the locked calculation. Its results are defensible as an assumption-dependent sensitivity analysis, not as calibrated model acceptance or a model ranking.**

1. **High — The pooled interval has a defensible target, but an assumed uncertainty distribution.**  
   **Files/sections:** `acceptance_rule_v2_plan_v1.json`, `rule.parameter_uncertainty`; `acceptance_rule_v2.py::simulate_ratios`.  
   Pooling replicated small-study ratios across parameter draws estimates an approximate **predictive distribution of the study statistic**. That is reasonable. However, marginal bootstrap interval endpoints do not specify a joint parameter distribution, and fitting distributions to them does not create a Bayesian posterior or guarantee frequentist predictive coverage.

   **Suggestion:** Call this an *approximate predictive sensitivity analysis*. Prefer complete joint bootstrap parameter vectors, or joint posterior draws for a Bayesian predictive check, then simulate the study design and compare the same statistic. A parameter-uncertainty VPC is another option when concentration data are available; it answers more than this aggregate check. FDA guidance recognises predictive checks and parameter-uncertainty assessment. [fda.gov](https://www.fda.gov/media/128793/download?attachment=\&utm_source=chatgpt.com)  
   **Status:** Limits interpretation; does not invalidate the calculation.

2. **High — Independence is neither conservative nor a “lower bound.”**  
   **Files/sections:** plan, `not_this`; `parameter_draws.py::draw`; the clearance equations in the original check modules.  
   Missing covariance can **widen or narrow** the ratio interval. Locally, variance depends on \(g^\mathsf{T}\Sigma g\); omitted covariance terms can have either sign.

   Crucially, in Hughes’s implemented AUC ratios, the shared typical CL/F factor cancels exactly, and volume is irrelevant. Thus **CL/F–renal-exponent covariance has no effect on these Hughes ratios**. In Kim’s primary multiplicative form, shared baseline clearance and fraction unbound also cancel; covariance between the remaining renal and body-size effects matters.

   Its magnitude cannot be recovered from marginal intervals. Illustratively, two equally sized uncertainty contributions with correlation ±0.8 give standard deviations approximately **0.45 or 1.34 times** the independent result—depending on their sensitivity signs.

   **Suggestion:** Remove the lower-bound claim now; test plausible joint correlation structures in a later version.  
   **Status:** Invalidates the *lower-bound assertion*, not the conditional simulation result. Particularly consequential for Kim’s borderline classifications.

3. **Medium — Matching three percentiles leaves consequential distributional choices.**  
   **Files/sections:** `parameter_draws.py::spreads`, `draw`; `hughes_parameter_precision_v2.json`, `theta_crcl`.  
   The sampler implements the specified quantile matching. But the point estimate need not equal the bootstrap median, and neither tail shape is known. Hughes’s exponent illustrates the issue: estimate 0.224 and interval 0.046–0.396 produce approximately **0.100–0.300 at the 16th–84th percentiles** under this sampler. That interior shape is imposed, not published evidence.

   **Suggestion:** In a later version compare plausible marginal families, prioritising parameters that survive ratio cancellation. Keep the present distribution explicitly labelled as an assumption.  
   **Status:** Sensitivity limitation, not an implementation failure.

4. **Medium — The 5% margin is a decision buffer, not statistical uncertainty or equivalence.**  
   **Files/sections:** plan, `indeterminate_margin`, `classes`; `acceptance_rule_v2.py::classify`.  
   Five percent avoids brittle calls, but has no demonstrated calibration to Monte Carlo error, source-data precision or scientific relevance. It cannot justify saying a model is sufficiently accurate. Adding parameter uncertainty generally broadens compatibility; it does not improve the model’s central predictions.

   **Suggestion:** Retain the locked margin and publish continuous discrepancies alongside labels. Later, separate a scientifically justified discrepancy tolerance from uncertainty in the simulated limits.  
   **Status:** Does not invalidate these labels; prevents interpreting “consistent” as equivalence or acceptance.

5. **Medium — Five seeds are useful, but 10,000 nested trials overstates independent parameter exploration.**  
   **Files/sections:** plan, `outer_parameter_sets`, `inner_trials_per_set`; `simulate_ratios`, `run_check`.  
   Each seed contains only **200 independent parameter vectors**, each reused 50 times. Those 10,000 ratios are dependent through their outer draws. Where parameter uncertainty dominates, tail precision depends much more on 200 than on 10,000. Seed disagreement sensibly flags numerical fragility, but unanimity across five seeds does not establish adequate precision. Percentile precision should be assessed directly. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9197539/?utm_source=chatgpt.com)

   **Suggestion:** Later, increase outer draws and estimate endpoint Monte Carlo uncertainty using outer-block resampling or independent repetitions. Distinguish “near boundary” from “numerically unstable.”  
   **Status:** Borderline results remain appropriately unresolved; no demonstrated invalidation.

6. **Medium — Observed sampling error is represented conditionally; some observation uncertainty remains absent.**  
   **Files/sections:** original modules’ `simulate*` functions; `simulate_ratios`.  
   Simulating both small groups and dividing their means represents sampling variation in numerator **and denominator under the model**. Comparing the single observed ratio with that distribution does not require another independently sampled observed ratio; adding one would generally double-count sampling variability. Bridoux correctly uses geometric means, unlike the arithmetic-mean CC-5013 checks.

   What remains absent includes NCA/measurement error, uncertainty in reconstructed covariate distributions and uncertainty in fixed variability estimates. Matching group sizes alone cannot establish that these components are reproduced.

   **Suggestion:** State this conditioning explicitly; later compare simulated group dispersion with published SDs/GCVs and assess missing components.  
   **Status:** Conditional validity, not complete observed-data uncertainty coverage.

7. **High — These are repeated analyses of two datasets, not independent confirmations.**  
   **Files/sections:** plan, `scope`, `datasets`; result, `results`.  
   The CC-5013 checks and study-matched recheck reuse the same observed exposures. Group ratios also share a normal-group denominator. Their classifications therefore cannot be counted as independent evidence. The rule was locked after observations were known, so it remains a retrospective sensitivity analysis despite being locked before execution.

   **Suggestion:** Organise conclusions by the **two source datasets**, with alternative simulations nested beneath them. Report central prediction errors and interval widths; an uncertain model should not win merely through wider intervals.  
   **Status:** Does not invalidate descriptive results; invalidates an interpretation as independent replication or superiority evidence.

8. **Medium — Reporting falls short of fully auditing the five-seed decision.**  
   **Files/sections:** plan, `reported`; `acceptance_rule_v2.py::run_check`; result rows.  
   Classification uses all five seeds, but the report retains percentile limits only in `simulated_ratio_first_seed`. Meanwhile, `margin_to_nearest_limit` takes the minimum across **all** seeds. Readers cannot reconstruct that margin or every seed classification from the saved limits.

   **Suggestion:** Preserve this result, and add a clearly identified supplementary report containing every seed’s limits and identifying which seed/limit determines the minimum margin. Future reports should also record code and dependency versions.  
   **Status:** Auditability gap; no evidence that the verdict calculation contradicts the plan.

For readers, I would write:

**“Under this retrospective check’s assumed parameter distributions and virtual-study designs, Hughes under-predicts moderate and severe exposure ratios, while Kim’s corresponding classifications are mostly indeterminate; Kim still under-predicts severe impairment in Bridoux, without establishing either model’s overall validity or superiority.”**

---

## Handling (12 November 2026, approved by the platform owner)

Claims about code and numbers were checked in the main session.

| # | Checked | Handling |
|---|---|---|
| 1 | Agreed. | The result is described as an approximate predictive sensitivity analysis under assumed parameter distributions, not model acceptance. Joint bootstrap vectors or posterior draws go to a later plan version. |
| 2 | **Confirmed.** In the Hughes checks the typical CL/F cancels within each parameter set and volume does not enter the ratio, so only the CrCl exponent's uncertainty acts on the Hughes ratios, and no covariance with it can matter. For Kim, the renal and body-size coefficients remain and their covariance could widen or narrow the interval. | The plan's phrase "Parameter uncertainty is a lower bound" is locked and stays as written; it is **withdrawn here**: omitted covariance can act either way, so the Kim verdicts are conditional on independence. Plausible correlation structures go to a later plan version. |
| 3 | **Confirmed**: the sampler gives the Hughes CrCl exponent about 0.100-0.300 at the 16th-84th percentiles; that interior shape is assumed. | Labelled as an assumption. Alternative marginal families, starting with the parameters that survive the ratio (Hughes CrCl exponent; Kim eGFR and BSA coefficients), go to a later plan version. |
| 4 | Agreed. | The 5% margin is described as a decision buffer. Continuous discrepancies are already in the report (`margin_to_nearest_limit`). |
| 5 | Agreed: 200 independent parameter sets per seed; unanimous seeds do not prove precise limits. | More outer draws and outer-block resampling for limit precision go to a later plan version. |
| 6 | Agreed. | The report's conditioning is stated here: group sampling under the model is simulated; NCA and measurement error, covariate reconstruction and the variability estimates' own uncertainty are not. |
| 7 | Agreed: the CC-5013-PK-001 checks and the recheck reuse one dataset, and ratios share the normal group. | Conclusions are read by dataset (CC-5013-PK-001; Bridoux 2016), not as replications. STATUS_BY_DRUG uses the reviewer's reader sentence. |
| 8 | **Confirmed**: the report keeps only the first seed's limits while the margin is the minimum over all five. | Supplement `docs/development/acceptance_rule_v2_seed_limits_v1.json`: every seed's 5th/50th/95th percentile and which seed and limit set the margin, recomputed with the same code and seeds; the first seed and every margin match the committed report exactly. The report itself is unchanged. |

**Invalidating?** No finding invalidates the locked calculation. Finding 2 withdraws the "lower bound" wording.
