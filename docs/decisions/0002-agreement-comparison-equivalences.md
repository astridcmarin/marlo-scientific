# 0002 — The agreement comparison gets a second version that applies the equivalences the extractor scoring already uses

**Date:** 17 November 2026 · **Status:** accepted

## Problem

The platform holds two rules for deciding whether two readings of a threshold are the same, and they disagree.

`eligibility_extractor_v1_1.canonical`, whose docstring calls it "exact equivalences allowed by the plan, for de-duplication and scoring", converts within a type: µmol/L to mg/dL for creatinine and bilirubin, g/L to g/dL for haemoglobin, and × 10⁹/L, × 10³/µL, /mm³ and cells/µL to a common per-microlitre basis for ANC and platelets. The extractor validation scores against the reference through it.

`eligibility_reference_review._same` compares the comparator, the value **as written** and the unit **as written**, with no normalisation. The reference re-reading's reproducibility count and the whole second-annotation agreement analysis are scored with it.

Two of the 43 second-annotation disagreements are artefacts of that difference: `>= 8 g/dL` against `>= 8.0 g/dL`, and `> 1000 cells/uL` against `> 1000 /mm3 (= /uL)`. The adjudicators independently judged both pairs to be two correct readings (`eligibility_adjudication_v1`). Overall exact agreement is 0.8925 as scored and 0.8975 with the equivalences applied.

The second case has a cause worth naming: `anc_min`'s unit list offers both `/mm3 (= /uL)` and `cells/uL`, which are two spellings of one unit in one picker. Two careful readers can pick differently and be scored as disagreeing on a threshold they read identically.

Annotation guide v2 told annotators that those spellings are "the same unit to the scoring". That is true of the extractor scoring and false of the agreement analysis. Guide v3 initially recorded this as the guide being wrong; it was the agreement analysis that was inconsistent with the rest of the platform.

## Options

1. **Leave both rules as they are.** The locked results stay reproducible and the inconsistency stays, so a second round under guide v3 pays the same tax again, now knowingly.
2. **Change `_same` to apply `canonical`.** One rule across the platform, but it silently alters the scoring of two committed locked results, and their reports could no longer be reproduced from the code that claims to produce them.
3. **Add a second comparison version, keeping v1 as the default.** Locked results reproduce byte-for-byte from v1; a plan that wants the platform's equivalences pins v2. The cost is two rules in the code, distinguished by version rather than by accident.
4. **Remove the duplicate unit spelling from `anc_min`.** Prevents the second artefact at source rather than normalising it away, but changes a pinned type vocabulary that locked records were made against.

## Decision

**Option 3**, with option 4 raised separately for the owner.

`_same` is unchanged and remains the default, pinned by a regression test added before this work. `_same_v2` applies `canonical` within a type and compares values numerically where both parse as numbers. `agreement` takes `comparison='v1'|'v2'`, defaulting to v1, so the committed reports stay byte-identical including their digests.

Round two's plan pins comparison v2, because measuring two readers against each other should not count a difference in spelling as a difference in reading.

What v2 does **not** do: it never converts between magnitudes the guide tells annotators to record as written. `canonical` does convert × 10⁹/L to a per-microlitre basis, so `1.0 x 10^9/L` and `1000 /mm3` compare equal under v2. That is the platform's existing convention for extractor scoring and this decision adopts it rather than inventing a third rule — but it means v2 is more permissive than "same spelling", and a reader who writes the number in a different unit is no longer scored as disagreeing.

The 0.8925 figure in `eligibility_second_annotation_v1` stands as the locked result. Its verdict rests on the lower bound of the bootstrap interval, 0.8475, against a 0.90 bar, and 0.8975 does not move that verdict.

## Still open for the owner

`anc_min` offering both `/mm3 (= /uL)` and `cells/uL` is a defect in the vocabulary, not only in the scoring. Removing one would prevent the artefact instead of forgiving it, and would make round two's readings cleaner. It changes a pinned type definition that the existing annotation and annotator B's record were made against, so it needs its own decision and probably a types v3 used by round two only.

## Revisit when

A third comparison version is proposed; a plan needs an equivalence `canonical` does not cover; or the unit vocabularies change.
