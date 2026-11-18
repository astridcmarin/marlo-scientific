# Repository checkpoint — 18 November 2026, batches 17 to 20

**Verified tree:** `main` at the merge of PR #130 (batch 19), plus batch 20 (`batch-20`, open). This checkpoint covers batches 17 to 20.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-18.json`](verification/repository_checkpoint_2026-11-18.json).
**Previous checkpoint:** 16 November, end of batch 16, in [`history/`](history/REPOSITORY_CHECKPOINT_2026-11-16.md).

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered

| Batch | PR | What |
|---|---|---|
| 17 | #128 | Checkpoint of 16 November; handoff corrections; the adjudication of the 43 second-annotation disagreements |
| 18 | #129 | Agreement comparison v2 (decision 0002); round two's plan locked (v2.0, then v2.1); round-two pages, whose reader identities and plan checksum were then found wrong and fixed |
| 19 | #130 | Tests for those page defects; dataset ledger v13 (six sources obtained unread); decisions 0003 and 0004; acceptance rule v2 for the Gupta and Luo checks: plan, amendment 1 (Luo model v1.1) and result |
| 20 | open | Body map v1.2 (node names and terms, arrowheads); the regroup and the owner's decisions (0005, 0006; roadmap "Now" rewritten); the evidence-first plan; O7 settled; this checkpoint |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** CI passed on PR #130. In a cloud session without the database packages, 1,526 collected and 300 database-backed errors by design, the same set as on `main`. |
| Compile all modules | **Pass.** |
| Migration chain | **Unchanged.** 9 revisions. |
| Pinned data | **Pass.** 232 JSON data files; 86 are earlier versions kept unchanged because locked plans and reports cite them by checksum (counted by stripping version suffixes; the 16 November count of families used a slightly different grouping). |
| Locked checks | **34**, in findings v11; **5 blind**. Of 63 ledger uses, 4 are blind and 2 blind with a recorded deviation. |
| Validation flags | **Pass.** No `clinical_prediction_validated` is true anywhere. |
| Repository hygiene | **Pass.** The one tracked PDF is the EMA 2008 public assessment report, kept on purpose with its checksum. No journal articles, correspondence or `instance/` files are tracked. |

## Findings

1. **A locked plan's first run failed, and the plan was amended before any result was seen.** The acceptance-rule run for daratumumab stopped on a numerical fault: the Luo model's fixed-step solver is unstable for patients with a high Vmax and a small V1. In those patients model v1.0 had also returned silently wrong values, for example an AUC 14 times too high. It was fixed as Luo model v1.1 under amendment 1 (plan v2.1), approved by the owner. Output is bit-identical wherever the old step was stable, and both committed Luo check reports reproduce exactly under v1.1.
2. **Round two's pages were generated wrong, and caught before anyone read.** Both pages carried annotator B's identity, and both declared plan v2.1 while carrying plan v1's checksum. The sample and the reading orders were right throughout. The fix, and tests that fail if either defect returns, are in batches 18 and 19.
3. **A dry run at reduced counts misses rare failures.** The plan-v2 dry run passed and the full run still failed (finding 1). Dry runs stay required, but they do not show that a plan can run at full size.
4. **None of the six unread sources can give a blind check yet.** Each needs a platform model of its drug first. Carfilzomib is next, so that Badros and Quach can test it.
5. **Decisions 0002 to 0006 were recorded in four days.** Three of them (0003, 0005, 0006) fix how results will be read before the results exist.

## Scientific state

- **34 locked checks:** 2 passed, 2 consistent, 11 mixed, 6 disagree, 8 failed, 3 inconclusive, 2 not adopted. No model is validated for clinical prediction.
- **Acceptance rule v2 now covers lenalidomide, ixazomib and daratumumab.**
  - Ixazomib: 19 of 20 verdicts hold.
  - Daratumumab: the three Cmax verdicts hold; two exposure verdicts become undecided across the uncertainty scenarios.
- **Datasets:** 33 in the ledger, 9 unseen. Six are the sources obtained on 17 November. The other three are the Hughes, Gupta and Luo fitting datasets, which cannot be obtained.
- **Reviewer's checklist for lenalidomide** (self-assessed): O7 is settled as a gap in the published evidence. M8, independent review, has never been done; the owner will include an independent reviewer.

## Remaining gates

- **Owner work:**
  - eligibility round two with annotator B, read against decision 0006 if it misses;
  - Track B, 109 entries of review round 3.
- **Next model work:** carfilzomib, after Track B — label-consistency plan, curve, then the blind check against Badros and Quach.
- **Evidence first:** the small fixes of the evidence-first plan, then ixazomib's drug page.
- **Deferred review findings:** F04 (a)–(d), F17, F19, F20, F24, and F16's second half.
- **Authors:** Kim's address bounced; Hughes approached on LinkedIn; Mager reprint requested. None blocks anything.
