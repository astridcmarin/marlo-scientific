# 0006 — If eligibility round two misses its bar, protocol benchmarking is recorded as not a validated capability

**Date:** 18 November 2026 · **Status:** accepted by the owner, 18 November 2026, before either round-two record exists

## Problem

The second annotation's locked plan (`intelligence_store/data/eligibility_second_annotation_plan_v2_1.json`, `analysis.reading_rule`) reads round two by the lower bound of the overall exact-agreement interval against 0.90. If the bound falls below 0.90, the plan allows two outcomes and does not choose between them: lower the bar, with the new bar and its justification written down before any rescoring, or record protocol benchmarking as not a validated capability. It rules out a third round without a reason other than "try again". The choice is made here, before the result, so that the result is read against a rule fixed in advance.

## Options

1. **Record benchmarking as not a validated capability** and leave it out of the platform's first release.
2. **Lower the bar.** Round one's lower bound was 0.8475, so any new bar near 0.85, chosen after that result, would look fitted to it. An extractor would also be judged against a reference already known to be wrong in at least 31 of 400 pairs (adjudication, 16 November).
3. **Keep only the criterion types on which the readers agree.** Not workable at this sample size: with 50 trials per type, a Wilson lower bound reaches 0.90 only with agreement on all 50 (49 of 50 gives about 0.895).

## Decision

Option 1. It is consistent with the owner's decision of the same day to lead the first release with sourced evidence rather than with models or extractors (`docs/REGROUP_2026-11-18.md`, thread 3).

## If the bar is met

Nothing here applies. The plan's own reading stands: a two-reader reference under guide v3 is adequate at the 0.90 bar, and an adjudicated annotation version may be built under its own plan. Any extractor revision is then tested on trials posted after the cohort freeze, never on the 200 already used.

## Revisit when

A new plan, with new trials and a stated reason that is not "try again", proposes to measure benchmarking again.
