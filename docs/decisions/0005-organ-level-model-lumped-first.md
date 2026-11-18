# 0005 — The organ-level lenalidomide model starts lumped, with no organ partition; predicted partition comes later

**Date:** 18 November 2026 · **Status:** accepted by the owner (answers of 17 November 2026; written as step 5 of the phased plan on 18 November)

## Problem

Step 5 of the organ-level design's phased plan (`docs/reviews/2026-11_organ_level_design_draft.md`, section 9) asks whether the first organ-level model of lenalidomide uses lumped compartments only, or also predicts how the drug partitions into each organ. The evidence behind the question (sections 2–4 of the draft):

- No lenalidomide concentration has been measured in any human solid organ in the sources held. Human observations exist for plasma, whole blood and red cells, urine, faeces and semen. Kidney, brain and "tissues" are covered by rat statements without numbers, and bone marrow by nothing.
- Predicting organ partition (Rodgers & Rowland, Poulin & Theil) needs logP and pKa, which no pinned source gives, as well as fraction unbound and the blood-to-plasma ratio, which pinned sources do give.
- Every human dataset that could test the model has been seen, so its check cannot be blind.

## Options

1. **Lumped only.** Gut lumen, blood, kidneys (filtration plus secretion into urine), urine, one rest-of-body lump (a second only if a locked plan shows one cannot fit both the peak and the terminal phase), and a small non-renal loss assigned to no organ. The portal vein and liver are drawn as the way in, with no elimination. This is the structure of section 2.2.
2. **Lumped plus predicted organ partition.** Option 1 with an organ-by-organ partition coefficient from a published method, once logP and pKa are pinned from a primary source.
3. **No organ-level model.** The body map keeps the one-compartment time course.

## Decision

**Option 1 now, option 2 later, as the work progresses** (owner, 17 November 2026). Option 2 needs logP and pKa pinned from a primary source first; without them, organ partition stops at this record, as the phased plan says.

Inputs fixed by the owner's answers of 17 November, recorded in the draft's Handling section:

| Input | Decision |
|---|---|
| Renal clearance calibrating the model | 162 mL/min, unchanged. Changing it would be a new clearance model under its own plan. |
| Fraction unbound | As decided on 31 October (`lenalidomide_pathway_unbound_fraction_assessment_v1.json`): 0.77 is the value the model and its check use; about 0.60 (ex vivo) is shown beside it. Totals do not depend on the choice; the filtration–secretion split does. |
| Physiology | ICRP 89, women and men separately (`reference_physiology_icrp89_v2.json`). The women's liver blood flow is the sum of its parts, 27.5%, with the printed 27.0% recorded. |
| Women | Physiology from the first version. No female picture until there is a female body mesh. |
| Parent drug's share of plasma radioactivity | Both 92% and 77.44% are quoted, each with the method that produced it. |
| Mouse tissue check | Not now. It becomes part of the plan when the model moves beyond lumped compartments. |
| Semen finding | Shown as text only, never drawn on the map. |

## What this does not decide

Everything else in section 5.2 belongs to the locked check plan (step 6): endpoints and the one acceptance rule, every fitted parameter and the data it is fitted to, how a group of women and men is represented, the bioavailability scenarios, and the numerical tests run on synthetic values before the lock.

Phased-plan steps 2 (the tissue-distribution evidence extract and its ledger update) and 4 (evidence classes on the existing map) are not done. Step 6 needs step 2's ledger update, and step 8 (the organ-level view) needs step 4.

## Consequences

- No organ concentration is shown. The lump is never painted onto individual organs.
- The check is not blind: its plan uses `checked_not_blind` or `tuned_on` roles and does not pass through `assert_blind_allowed`.
- One expectation is disclosed now so that it cannot count as a finding later (draft, section 5.1): calibrated on CC-5013-PK-001, the model will predict too much exposure and too slow a urine recovery for the young healthy men of Chen 2012, whose apparent clearance is about 1.5 times higher.

## Revisit when

logP and pKa are pinned from a primary source (option 2 becomes possible, with the mouse check); human tissue data for any organ appear; or the lumped model fails its check in a way more compartments could explain.
