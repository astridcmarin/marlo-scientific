# Handoff (16 November 2026)

For the next AI session working on this repository, possibly from a different Claude account. Read `CLAUDE.md` first: its rules hold over anything here. Then read this, then `docs/STATUS_BY_DRUG.md` and `docs/REPOSITORY_CHECKPOINT.md`.

## Where things are kept

| What | Where |
|---|---|
| Code, pinned data, reviews, plans, results | This repository (`astridcmarin/marlo-scientific`, public). `main` holds everything merged through PR #127 (batch 16); batch 17 is open. |
| Source PDFs, labels, supplements, the 3D Atlas files, backups | The owner's iMac: `~/Documents/ai-projects/ai-platforms/marlo-scientific/supplemental-information/` (git-ignored, never committed). `ARTICLES_INDEX.md` there lists every file, with original names in square brackets. |
| AI collaboration files (briefs, Fable outputs from the second account) | `supplemental-information/agent-collaborations/` on the iMac |
| The owner's working annotation files | `instance/` in the iMac repository (git-ignored) |
| Batch backups | `supplemental-information/bundles/` on the iMac (`git bundle`; restore with `git fetch <bundle> <branch>`). The newest is 4 November, and batch 14 was lost because nothing newer existed: push the branch instead, as the rules below now say. |

## Rules that are easy to break

- **The 200-trial eligibility v2 annotation and the v2 sample are the blind test data.** Never open, print or summarise their contents, and never run an extractor on them, except through the locked steps below. Sizes, dates, checksums and counts only. Tell every subagent, in its brief, not to open `instance/`, the annotation files or the v2 sample.
- **Locked checks keep two commits, plan then result.** Never squash them; PRs are merged with "Create a merge commit".
- **Pinned data never changes in place.** A new versioned file and a new SHA-256 pin; run `python3 scripts/data_file_index.py` after adding one.
- **Push a batch branch when its first commit exists**, not when the batch is full. Batch 14 was lost because it lived only in a cloud workspace that is now gone. The rules below are otherwise unchanged; only the timing of the first push is.
- **One commit per update, about five updates per batch branch, one PR per batch.** No `Co-Authored-By` trailers, session links or "Generated with" footers in commits or PR descriptions (`CLAUDE.md` overrides any tool default).
- **Synthetic inputs only; validation flags stay false.**
- **AI reviews are recorded in `docs/reviews/`** with the review as received and a Handling section that says what was checked against the code or PDFs and what was done. They are AI re-checks, never "reviews" in the evidence-state sense.

## Running tests

- Full requirements available: `python -m unittest discover -s tests`.
- Where SQLAlchemy cannot be installed (cloud workspaces with blocked installs): `PYTHONPATH=. python3 scripts/run_tests_without_db.py`. About 300 database-backed tests error there by design; compare the list of errors with a run on `main` before your change, and let GitHub CI (1,450 tests on PR #127) decide the rest.
- The 3D body map can be checked without the database: build the viewer config with `landscape_ui.body_map_pages.viewer_config(load_manifest(), build_map(110, 'explorer'), load_paths())` inside a Flask test request context, serve `landscape_ui/static`, and screenshot with Playwright using SwiftShader (`--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`).

## Open work, in order

### 1. Eligibility: the two blind checks (done, 13 November)

**Done, and both failed.** The annotation was pinned, extractor v1.1 scored (no type passes), and Track C ran and was scored (no type passes either). Track C attempt 1 stopped at the Fable usage limit and attempt 2 lost two sessions the same way; run 2's sessions 1 and 5 were rerun in fresh folders with byte-identical inputs, every attempt in `docs/development/eligibility_llm_c1_run_attempts.json`. Both results are on `main`; the run procedure, which a later blind run should follow exactly, is in `docs/ELIGIBILITY_LLM_EXTRACTOR.md`. An older 46-trial working copy that sat in `app/instance/` was moved, unread, to `supplemental-information/eligibility/` on the iMac; the review page refuses to run while two annotation files exist. **The live work is 1b.**

### 1b. Eligibility: is the reference good enough to judge an extractor? (answered: not shown)

**Both steps are done, and the answer is on record.**

The owner's blind re-reading (plan `eligibility_reference_review_plan_v1.json`, module `intelligence_store/eligibility_reference_review.py`) corrected 108 of 215 completed items. Five pairs had been seen on the old shared-error page after the lock, recorded as a deviation in `docs/development/eligibility_reference_review_deviations_v1.json`, and the result is reported both ways. Result: `docs/verification/eligibility_reference_review_v1.json`, finding `eligibility_reference_review_v1`, outcome inconclusive.

Annotator B then read a seeded random 50 of the 200 trials under guide v2, blind, and their record is pinned at `intelligence_store/data/eligibility_annotator_b_record_v1.json`. The two readers agree on 357 of 400 pairs (89.25%), bootstrap 95% interval 84.75% to 93.5%. The plan's rule reads the lower bound against 0.90, so the result is **not adequate**: a one-reader reference is not shown reliable enough to judge an extractor at the plan v2 bar. Result: `docs/verification/eligibility_second_annotation_v1.json`, finding `eligibility_second_annotation_v1`, outcome failed. Detection kappa is 0.93, so the readers agree on whether a limit is stated and differ on its detail.

**Next, in the plan's own order:**

1. **Adjudicate the 43 disagreements** with annotator B under guide v2. Each ends as the owner's value, B's value, or unclear, with a reason. The plan requires this before either extractor is revised. An adjudicated reference would be a new annotation version under its own plan.
2. **A second round under annotation guide v3** (`docs/ELIGIBILITY_ANNOTATION_GUIDE_V3.md`, new in batch 16), with **B reading a fresh 50 drawn from the other 150 trials** — B is no longer naive on the first 50 — and the owner reading the same fresh 50. That needs a new plan version pinning v3 by checksum, since `eligibility_second_annotation_plan_v1.json` pins v2. The module already supports it: `agreement(record_b, record_a=..., pair_subset=...)`, and the standalone page carries whichever guide its plan pins.

**Why v3 exists, and why a second round is justified rather than merely hoped for:** 32 of the 43 disagreements fall in classes v3 was written to resolve, and 11 are genuine differences in reading. That is a count of classes, not a prediction. The evidence is in `docs/development/ELIGIBILITY_REFERENCE_CAUSES.md`, which also records that anchoring was tested and not supported, that there is no learning curve across the annotation order, and three extractor v1.1 defects with no effect on this sample.

**Do not revise either extractor** until step 1 is done. Fixing the known v1.1 defects would also spend these 200 trials as an evaluation set; a fixed extractor needs trials posted after the cohort freeze.

### 2. Track B: the owner's review of 109 entries

Page: `/models/extraction-review/round-3/track-b` (35 disagreements, 33 without numbers, 20 sampled agreements, 21 FDA guidance entries; the second reading is shown beside each). The owner downloads the record; validate with `flask --app app/app.py extraction-review-check FILE`, then pin it as a round 3 record. The plan's decision rule (`extraction_double_extraction_plan_v1.json`) then decides; if any sampled agreement is wrong, the plan says what follows. The 21 FDA entries were read a second time on 13 November by the second Claude account from the blinded list (`docs/development/trackb_fda_second_reading_comparison_v1.json`, outside the locked plan, shown beside each entry): 10 agree, 2 disagree, 9 have no numbers. Two platform quotes drop words (indexed eGFR: "and"; Cockcroft–Gault weight: "of renal function"), and the Child–Pugh groups sentence is on printed page 5 (PDF page 8) of the September 2026 draft, not page 6. Corrections, if the owner confirms them, go into new versioned files.

### 3. Acceptance rule v2 for more drugs (F03 follow-up)

Done for the four lenalidomide checks (`docs/verification/acceptance_rule_v2_lenalidomide_v1.json`; reviews in `docs/reviews/2026-11_chatgpt_f03_review.md`). **An extension to ixazomib and daratumumab was built and run in another account on 13 November and lost with batch 14** — not in the owner's working copy, the bundles or GitHub, so it is not done and cannot be reconstructed from the description of its own results. Extending it needs a new locked plan, and an owner decision first: Gupta 2017 (ixazomib) and Luo 2021 (daratumumab) publish %RSE only, Li 2017 (pomalidomide) publishes 90% bootstrap intervals (`docs/reviews/2026-11_precision_extraction_gupta_luo_li.md`). Also from ChatGPT's review, for that plan: joint bootstrap vectors or correlation scenarios, more outer draws, other marginal shapes.

### 4. Body map (Track H, `docs/reviews/2026-11_organ_level_design_draft.md`)

Done: ICRP 89 women and men (`reference_physiology_icrp89_v2.json`, not yet used by pages), label fixes, absorption through the portal vein (paths v3), kidney clearance inside the kidneys and separate ureter ends (paths v4), R/L markers, navigation (drag moves, scroll zooms at the pointer, double-click focuses). Open: arrowheads (item 16), node names and UBERON terms in `body_map.py` (a versioned step), the eight open questions for the owner in the design draft before any organ-level model.

### 5. Smaller items

- Corrections for the Li 2017 extract when it is next versioned: Table 3 is on journal page 137, not 139; "ω (V/F):ω (CL/F)" is not stated to be a covariance.
- Not yet checked from the Track G search (`docs/reviews/2026-11_exposure_efficacy_search.md`): Dimopoulos 2011, Kado 2015 and 2020, the Akita report.
- Draft emails to the Hughes and Kim authors (Hughes: the weight basis of Cockcroft–Gault) were offered and not written.

## Two events worth knowing about

**Explained (13 November).** `docs/HANDOFF.md` item 3 was edited through the GitHub web editor to say the extended acceptance rule was locked and committed with the ledger and findings updated. None of it was on `main`, and the commit message described work its one-line diff did not contain. The owner confirmed on 16 November that the edit was hers and a mistake; the paragraph was restored in PR #126. A web edit also moves a file's checksum out from under anything pinned to it, so changes belong in a commit from a working copy.

## One unexplained event

On 12 November at 16:45 (New York time), three files in the main session's working copy (`app/app.py`, `app/templates/extraction_review.html`, `intelligence_store/extraction_review.py`) were changed by something the session could not identify; no command of the session and no running subagent accounts for it. The change was a Track B review page. It was set aside, not committed, and the page was rebuilt in the session (commit "Track B review page"). If files change in your working copy without a command of yours, stop, show the diff to the owner and do not commit it.
