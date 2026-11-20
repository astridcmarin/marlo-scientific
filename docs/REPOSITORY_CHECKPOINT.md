# Repository checkpoint — 20 November 2026, batches 21 to 24

**Verified tree:** `main` at the merge of PR #135 (batch 24). This checkpoint covers batches 21 to 24.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-20.json`](verification/repository_checkpoint_2026-11-20.json).
**Previous checkpoint:** 18 November, batches 17 to 20, in [`history/`](history/REPOSITORY_CHECKPOINT_2026-11-18.md).

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered

| Batch | PR | What |
|---|---|---|
| 21 | #132 | Evidence-first small fixes (items 1–4, 9); drug catalogue v2 with ixazomib's drug page; review round 4 opened (14 ixazomib catalogue entries); eligibility round two's records pinned, then its analysis: the two-reader reference meets the 0.90 bar |
| 22 | #133 | Round two's practice record; round 4 pinned (14 of 14 match); Track B pinned (102 match, 7 wrong) and the double-extraction rule passes; FDA guidance extracts corrected (liver v2, kidney v3) |
| 23 | #134 | Carfilzomib label-consistency plan, then its result (not eligible); sources held and regulatory documents on drug pages (items 6–7); carfilzomib model scan; decisions 0007 and 0008; ledger v19 (NCT01801436 partly seen); decision 0007's status line fixed. Eight commits, more than the batch size of about five. |
| 24 | #135 | Iwasaki 2020 independence recorded and the roadmap corrected; ledgers v20 and v21; the NCT01801436 bortezomib blind check, plan then result (3.0n; ledger v22, findings v14) |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** CI passed on PRs #132 to #135. In a cloud session without the database packages, 1,610 run on `main` and 301 database-backed errors by design (one more than on 18 November: the round-4 page test needs the app). |
| Compile all modules | **Pass.** |
| Migration chain | **Unchanged.** 9 revisions. |
| Pinned data | **Pass.** 257 JSON data files in 154 families; 103 are earlier versions kept unchanged because locked plans and reports cite them by checksum. Counted by stripping `_vN` suffixes, which groups more files into families than the 18 November count (86). |
| Locked checks | **37**, in findings v14. Ledger v22 has 68 uses: 6 blind and 2 blind with a recorded deviation. |
| Validation flags | **Pass.** No `clinical_prediction_validated` is true anywhere. |
| Repository hygiene | **Pass.** The one tracked PDF is the EMA 2008 public assessment report, kept on purpose with its checksum. No journal articles, correspondence or `instance/` files are tracked. |

## The NCT01801436 review, as the owner gave it

The observed file pins the owner's reply when the eight values were put to them on 20 November: "go", at 11:03 (America/New_York). The result was then computed and committed (79b1294, 11:21). Separately, at 12:07, the owner wrote:

> I have reviewed the results on the ClinicalTrials.gov page and it stands.

and at 12:10 confirmed that the 11:03 "go" was theirs and the record correct. The pinned file is unchanged; this quotation is its fuller wording, recorded here at the owner's request.

## Findings

1. **Two sessions wrote to one branch.** The NCT01801436 result was computed and pushed by one session while another, on the same branch, waited for the owner's review. The record turned out correct, but the second session briefly overwrote the committed observed file in its working tree before noticing, and restored it. The handoff update in this batch adds a rule to `CLAUDE.md`: fetch and check the branch head before each commit, and one branch per session.
2. **A documentation line was trusted over the repository.** The roadmap said Iwasaki had never been contacted; acting on it, a session overwrote the existing Iwasaki extract and module in its working tree. Both were restored from git before any commit (checksums unchanged) and the roadmap corrected (batch 24).
3. **A decision record was committed without the full suite** and failed the status-line test; fixed in batch 23 before merge.
4. **A model was proposed for a blind check on an unverified premise.** The falling-clearance candidate was recommended as already calibrated; its locked report shows neither form could be. Caught before the plan changed; the plan records why it is left out.
5. **The owner's reviews keep finding errors in AI extraction.** Track B: 102 entries match and 7 are wrong (FDA guidance page locations), corrected in the liver v2 and kidney v3 extracts. Round 4: 14 of 14 match.

## Scientific state

- **37 locked checks:** 3 passed, 2 consistent, 11 mixed, 7 disagree, 9 failed, 3 inconclusive, 2 not adopted. No model is validated for clinical prediction.
- **Eligibility:** a two-reader reference under guide v3 meets the bar (lower bound 0.9125 against 0.90); decision 0006's miss rule does not apply.
- **Carfilzomib:** the label curve is not eligible (the label's exposure and stated clearance disagree about two-fold); Badros and Quach stay unread.
- **Bortezomib, first blind check:** both the constant-clearance and the Iwasaki model under-predict day 11 AUC0-t (observed 190.4 ng·h/mL, 95% CI 150.9–229.9; models 126.6 and 145.4; Iwasaki not robust to body size). The observed day 11/day 1 ratio is 3.7 against about 1.5 (not blind).
- **Datasets:** 40 in the ledger, 13 unseen, of which the Hughes, Gupta and Luo fitting datasets cannot be obtained.

## Remaining gates

- **Owner:** decision 0007's five choices; review of the AI-written ixazomib catalogue summaries; an independent reviewer (decided 18 November, not yet started).
- **Eligibility:** a plan for the adjudicated two-reader reference, then an extractor revision tested only on trials posted after the cohort freeze.
- **Evidence first:** item 8, catalogue growth.
- **Models:** selinexor and thalidomide label-consistency plans; a reading plan for the FDA and PMDA carfilzomib reviews; the owner's choice of a carfilzomib model to test against Badros and Quach.
- **Deferred review findings,** carried from 18 November and not re-checked here: F04 (a)–(d), F17, F19, F20, F24, and F16's second half.
