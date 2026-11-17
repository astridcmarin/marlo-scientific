# Repository checkpoint — 10 November 2026, end of batch 4

**Verified tree:** branch `batch-4`, 9 commits on top of `main` after PR #115 (3 updates of 9 November, 5 review-fix updates of 10 November, this checkpoint). CI runs when the pull request is opened; the owner chose to push before a run on the iMac, so the unit-test count is the CI run's.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-10.json`](verification/repository_checkpoint_2026-11-10.json).
**Previous checkpoint:** 6 November (b), end of batch 3, in [`history/`](history/REPOSITORY_CHECKPOINT_2026-11-06b.md). CI on PR #115 matched the iMac run (1,330 tests).

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered (batch 4)

| Area | What | Main files |
|---|---|---|
| Model analysis report (M3) | The exposure–safety odds ratios, stating plainly that the model has no locked check | `model_analysis_report.py`, narrative file |
| Parameter uncertainty (M7) | The Hughes typical curve's uncertainty from the published %RSE, shown as a lower bound | `population_pk.py` v1.1, `hughes_parameter_precision_v2.json` |
| Digital human 1.1e | The body-map timeline: one dose over 48 hours, with the locked check and the observed urine share beside it | `body_map_time_course.timeline` v1.1 |
| AI review (Track A) | A Fable review of the lenalidomide work: 29 findings, 28 open (1 high, 8 medium, 19 low); handled in five updates | `docs/reviews/2026-11_fable_review.md` |
| Review fixes | Kim moderate band reread; the Bridoux check no longer called blind; checklist corrected; provenance notes and a quote-check script; dose view renamed | see the review file's "Handling" section |

## Checks

| Check | Result |
|---|---|
| Unit tests | **CI on the pull request.** In the cloud session without the database packages, all tests that can run there pass (1,338 collected; the database-backed and page tests cannot run there). |
| Compile all modules | **Pass.** |
| Migration chain | **Unchanged.** 9 revisions. |
| Pinned data | **Pass.** 191 data files; 190 pinned (the observation template is unpinned by design). |
| Locked checks | **Unchanged.** 27. Three carry blind roles; the two Bridoux uses are now labelled "prespecified, outcome largely known beforehand". |
| Validation flags | **Pass.** None set to true. |
| Repository hygiene | **Pass.** No source PDFs, correspondence or email addresses tracked. |

## Findings

1. **The AI review found interpretation errors, not arithmetic ones.** All ten lenalidomide check reports regenerate byte for byte, and every transcription checked against its PDF is correct (Hughes, Kim, Bridoux, EMA, Chen 2007, TGA). The moderate-band warning for Kim, the "blind" label and three checklist scores overstated what the checks show; each is corrected in a new versioned file.
2. **A supplied PDF was misnamed in the session copy.** `280_2011_Article_1760.pdf` is Chen 2012 (mass balance), not Hughes 2019; the Hughes article was in the owner's folder under its own name.
3. **One quote is not verbatim.** The TGA population quote ends with a full stop where the report has a comma; recorded in `lenalidomide_source_notes_v1.json`, words and numbers unchanged.
4. **Superseded narrative texts were briefly unpinned** when their v2 replaced them; caught by the pin count before this checkpoint and fixed in the same updates.

## Scientific state

- Reviewer's checklist for lenalidomide (self-assessed): 19 of 29 answered, 8 partly, 2 gaps (O7 exposure–efficacy, M8 independent review). The AI review is not an independent review.
- 27 locked checks. No model is validated for clinical prediction.

## Remaining gates

- **This batch:** the pull request and CI; the owner merges with "Create a merge commit".
- **Deferred review findings:** F03, F04 (a)–(d), F08 sampling, F17, F19, F20, F24 (method changes or new locked plans).
- **Owner work:** review round 3 (now 121 entries); the eligibility annotation (46 of 200, on the iMac); the two FDA guidance PDFs and Chen 2017.
- **Independent review:** none yet. **Authors:** Hughes (weight basis, CRCL2), Kim, Iwasaki.
