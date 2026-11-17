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

**In the plan's own order:**

1. **Adjudicate the 43 disagreements — done (16 November).** The owner and annotator B, together, under guide v2: B's reading stands in 24, the owner's in 9, and 10 are unclear, 7 of which say both readings were wrong. So the reference is wrong in at least 31 of the 400 pairs and B's reading in at least 16; errors both readers share cannot be found this way, so these are lower bounds. Record `intelligence_store/data/eligibility_adjudication_record_v1.json`, report `docs/verification/eligibility_adjudication_v1.json`, finding `eligibility_adjudication_v1`, outcome mixed. No adjudicated reference was produced; that would be a new annotation version under its own plan.
   - Adjudication was deliberately not blind: the two readers sat together, the guide's author was in the room and B may have deferred to her. `resolution` records that.
   - The tooling stays for round two, whose plan adjudicates again if the bar is missed: `PYTHONPATH=. python3 scripts/eligibility_adjudication_page.py --output …` writes the standalone page and prints its view checksum; `intelligence_store/eligibility_adjudication.py` validates the record and gives the split. It was built for round one's guide and readers, so check it against plan v2.1 before using it.
2. **A second round under annotation guide v3** (`docs/ELIGIBILITY_ANNOTATION_GUIDE_V3.md`, new in batch 16), with **B reading a fresh 50 drawn from the other 150 trials** — B is no longer naive on the first 50 — and the owner reading the same fresh 50. Planned and locked: `intelligence_store/data/eligibility_second_annotation_plan_v2_1.json`, which pins guide v3, comparison v2, a presentation order per reader, and the bootstrap seed and bar its own executable reads.
   - Both pages are written: `supplemental-information/eligibility/round2_owner_page.html` (page checksum `132a8015cb596141`) and `round2_annotator_b_page.html` (`97a31d6531440ea9`). Each reader works alone from their own page and returns the locked download.
   - Validate each record against its own reader: `validate_record(record, reader='owner'|'annotator_b', plan=<v2.1>)`, then `agreement(record_b, p=..., record_a=..., p_a=..., comparison='v2', plan=<v2.1>)`. Passing neither reader nor plan builds round one's payload, which is not this round's.
   - Both pages first came out carrying annotator B's identity, and both declared plan v2.1 while carrying plan v1's checksum (17 November 2026, fixed in the same commit as this line). The sample and the two orders were correct throughout and are unchanged by the fix.

**Why v3 exists, and why a second round is justified rather than merely hoped for:** 32 of the 43 disagreements fall in classes v3 was written to resolve, and 11 are genuine differences in reading. That is a count of classes, not a prediction. The evidence is in `docs/development/ELIGIBILITY_REFERENCE_CAUSES.md`, which also records that anchoring was tested and not supported, that there is no learning curve across the annotation order, and three extractor v1.1 defects with no effect on this sample.

**Do not revise either extractor yet.** The plan made adjudication a precondition, and it is met, but it was a precondition, not a licence. Fixing the known v1.1 defects would also spend these 200 trials as an evaluation set; a revised extractor needs trials posted after the cohort freeze, and a reference shown adequate to judge it, which round two is the next attempt at.

### 2. Track B: the owner's review of 109 entries

Page: `/models/extraction-review/round-3/track-b` (35 disagreements, 33 without numbers, 20 sampled agreements, 21 FDA guidance entries; the second reading is shown beside each). The owner downloads the record; validate with `flask --app app/app.py extraction-review-check FILE`, then pin it as a round 3 record. The plan's decision rule (`extraction_double_extraction_plan_v1.json`) then decides; if any sampled agreement is wrong, the plan says what follows. The 21 FDA entries were read a second time on 13 November by the second Claude account from the blinded list (`docs/development/trackb_fda_second_reading_comparison_v1.json`, outside the locked plan, shown beside each entry): 10 agree, 2 disagree, 9 have no numbers. Two platform quotes drop words (indexed eGFR: "and"; Cockcroft–Gault weight: "of renal function"), and the Child–Pugh groups sentence is on printed page 5 (PDF page 8) of the September 2026 draft, not page 6. Corrections, if the owner confirms them, go into new versioned files.

### 3. Acceptance rule v2 for more drugs (F03 follow-up)

Done for the four lenalidomide checks (`docs/verification/acceptance_rule_v2_lenalidomide_v1.json`; reviews in `docs/reviews/2026-11_chatgpt_f03_review.md`). **An extension to ixazomib and daratumumab was built and run in another account on 13 November and lost with batch 14** — not in the owner's working copy, the bundles or GitHub, so it is not done and cannot be reconstructed from the description of its own results. Extending it needs a new locked plan, and an owner decision first: Gupta 2017 (ixazomib) and Luo 2021 (daratumumab) publish %RSE only, Li 2017 (pomalidomide) publishes 90% bootstrap intervals (`docs/reviews/2026-11_precision_extraction_gupta_luo_li.md`). Also from ChatGPT's review, for that plan: joint bootstrap vectors or correlation scenarios, more outer draws, other marginal shapes.

**Owner decision, 17 November: convert, with correlation scenarios** (`docs/decisions/0004-acceptance-rule-precision-conversion.md`). %RSE and 90% intervals are turned into draws, and the verdict is shown under the independent case and under each correlation scenario. The scales, correlations, draw count and alternative shapes are fixed in the plan before it runs. Next: write and lock that plan. The lost extension is not reconstructed.

### 4. Body map (Track H, `docs/reviews/2026-11_organ_level_design_draft.md`)

Done: ICRP 89 women and men (`reference_physiology_icrp89_v2.json`, not yet used by pages), label fixes, absorption through the portal vein (paths v3), kidney clearance inside the kidneys and separate ureter ends (paths v4), R/L markers, navigation (drag moves, scroll zooms at the pointer, double-click focuses). Open: arrowheads (item 16), node names and UBERON terms in `body_map.py` (a versioned step). The design draft's eight questions were answered by the owner on 17 November (its Handling section): lumped compartments first, renal clearance 162 mL/min, a reference woman's physiology but no female picture before a female mesh, no mouse check until the model goes beyond lumped compartments, fu as decided on 31 October, both parent shares quoted with their methods, the women's liver flow as the sum of its parts, the semen finding as text only.

### 5. Smaller items

- Corrections for the Li 2017 extract when it is next versioned: Table 3 is on journal page 137, not 139; "ω (V/F):ω (CL/F)" is not stated to be a covariance.
- Track G is closed: Dimopoulos 2011, Kado 2015 and 2020 and the Akita grant report were checked against their full texts on 13 November and the O7 verdict is unchanged (`docs/reviews/2026-11_exposure_efficacy_search.md`, "Checked against the full texts").
- Draft emails to the Hughes and Kim authors (Hughes: the weight basis of Cockcroft–Gault) were offered and not written.

### 6. Six sources obtained unread (17 November)

Dataset ledger v13 registers Badros 2013 and Quach 2017 (carfilzomib, renal impairment), Dimopoulos 2021 and the SARCLISA EPAR (isatuximab), NCT04256707 (selinexor, hepatic impairment) and the Zhang and Mager 2020 supplement (bortezomib), each with the SHA-256 of the file obtained (kept in `supplemental-information/articles`, outside the repository) and a note of exactly what was read before registration. With the Hughes, Gupta and Luo fitting data, which the platform cannot obtain, they are its only unseen datasets, and the only ones it holds.

- Reading their results sections, tables, figures, posted results or supplement makes them seen, and they can then no longer give a blind check. So far only file names, title pages and checksums have been handled. A check that wants to use one locks its plan first and passes `dataset_ledger.assert_blind_allowed`.
- Even then, a blind check may not use anything an abstract reports, since each source was found by web search and search results show abstract sentences. For Badros, Dimopoulos and the SARCLISA EPAR, the direction of a renal or covariate effect is also known (the ledger notes say how). What remains blind is the tabulated values.
- **Badros stays unseen** (owner, 17 November). What "seen" means for these six is `docs/decisions/0003-what-makes-a-dataset-seen.md`; the gate does not enforce its exclusions, so a plan claiming a blind check on one of them must quote the dataset's note and show its prediction avoids them.
- The Zhang and Mager main article is not held; a reprint was requested from Donald Mager on 17 November. The Nguyen PAGE abstract (isatuximab population PK) returned access forbidden and was not obtained.

## Two events worth knowing about

**Explained (13 November).** `docs/HANDOFF.md` item 3 was edited through the GitHub web editor to say the extended acceptance rule was locked and committed with the ledger and findings updated. None of it was on `main`, and the commit message described work its one-line diff did not contain. The owner confirmed on 16 November that the edit was hers and a mistake; the paragraph was restored in PR #126. A web edit also moves a file's checksum out from under anything pinned to it, so changes belong in a commit from a working copy.

## One unexplained event

On 12 November at 16:45 (New York time), three files in the main session's working copy (`app/app.py`, `app/templates/extraction_review.html`, `intelligence_store/extraction_review.py`) were changed by something the session could not identify; no command of the session and no running subagent accounts for it. The change was a Track B review page. It was set aside, not committed, and the page was rebuilt in the session (commit "Track B review page"). If files change in your working copy without a command of yours, stop, show the diff to the owner and do not commit it.
