# 0004 — Acceptance rule v2 extends to models that publish %RSE or 90% intervals by converting them, with correlation scenarios

**Date:** 17 November 2026 · **Status:** accepted by the owner, 17 November 2026

## Problem

Acceptance rule v2 compares a published model with observed data by drawing many parameter sets from the model's published uncertainty. When the observation falls within the spread those draws produce, the verdict is indeterminate rather than a disagreement. It has been applied to the four lenalidomide checks (`docs/verification/acceptance_rule_v2_lenalidomide_v1.json`).

The extension to ixazomib, daratumumab and pomalidomide needs uncertainty in a form the papers do not publish (`docs/reviews/2026-11_precision_extraction_gupta_luo_li.md`):

| Paper | Published precision |
|---|---|
| Gupta 2017 (ixazomib) | %RSE only, on the log scale (Table 3) |
| Luo 2021 (daratumumab) | %RSE only (Table S1) |
| Li 2017 (pomalidomide) | 90% bootstrap intervals and no %RSE (Table 3, the model the platform's extract uses) |

None of the three publishes a covariance or correlation matrix of the estimates.

## Options

1. **Exclude** any model without published 95% bootstrap intervals. In practice the rule then never extends beyond lenalidomide.
2. **Convert, with parameters drawn independently.**
3. **Convert, with correlation scenarios** alongside the independent case.

## Decision

Option 3.

## What the plan must fix before it runs

These are decided in the locked plan, not here:

- the scale each %RSE is on and the resulting distribution (Gupta's are on the log scale, so log-normal);
- how a 90% interval becomes a spread: on which scale, and whether it is treated as symmetric;
- which parameter pairs get a correlation, and at what values;
- the number of draws, and the alternative distribution shapes run as sensitivity analyses (from ChatGPT's review, `docs/reviews/2026-11_chatgpt_f03_review.md`).

The report states that each conversion adds an assumption the paper does not support. Neither the independent case nor any one correlation scenario is the paper's own, so the verdict is shown under each.

## Revisit when

A source publishes its covariance or bootstrap distribution; or a verdict changes across the correlation scenarios. In that case the rule cannot decide for that model, and the report says so rather than picking a scenario.
