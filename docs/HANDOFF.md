# Handoff (20 November 2026)

For the next AI session working on this repository, possibly from a different Claude account. Read `CLAUDE.md` first: its rules hold over anything here. Then this page, then [REGROUP_2026-11-20.md](REGROUP_2026-11-20.md), [STATUS_BY_DRUG.md](STATUS_BY_DRUG.md) and [REPOSITORY_CHECKPOINT.md](REPOSITORY_CHECKPOINT.md). The previous handoff (16 November, with the full eligibility and Track B set-up history) is in [history/HANDOFF_2026-11-16.md](history/HANDOFF_2026-11-16.md).

## Where things are kept

| What | Where |
|---|---|
| Code, pinned data, reviews, plans, results | This repository (`astridcmarin/marlo-scientific`, public). `main` holds everything merged through PR #135 (batch 24); batch 25 (housekeeping) is open. |
| Source PDFs, labels, registry records, supplements, correspondence, the 3D Atlas files | The owner's iMac: `~/Documents/ai-projects/ai-platforms/marlo-scientific/supplemental-information/` (git-ignored, never committed). `ARTICLES_INDEX.md` there lists every file, with original names in square brackets. |
| AI collaboration files (briefs, outputs from the second account) | `supplemental-information/agent-collaborations/` on the iMac |
| The owner's working annotation files | `instance/` in the iMac repository (git-ignored) |
| Batch backups | Push the batch branch when its first commit exists; `supplemental-information/bundles/` holds older `git bundle` backups. |

## Direction

The first release leads with sourced evidence; models stay research tools behind their records (18 November). The first release covers every drug with a US label (decision 0007; five choices open for the owner). A real patient enters only as a banded profile computed in the browser (decision 0008). The proposed order of next steps is in the roadmap's "Now" section and REGROUP_2026-11-20.md; the owner has not yet decided it.

## Rules that are easy to break

- **Two sessions, one repository (added 20 November).** Before every commit, `git fetch origin` and check that the branch's remote head is still the commit you started from (`git status -sb` must not say "behind"). If a commit you did not make has appeared, stop and read it before doing anything else. One batch branch per session; never commit to a branch another session is using. Before writing a file that already exists in the tree or in history, read it and the commit that made it. On 20 November one session computed and pushed a result while another on the same branch was waiting for the owner, and the second briefly overwrote a committed file.
- **Blind data.** The 200-trial eligibility v2 annotation and the v2 sample are blind test data: never open, print or summarise their contents, and never run an extractor on them, except through locked steps. Sizes, dates, checksums and counts only. Tell every subagent the same, in its brief. Unread sources in the dataset ledger (13 on 20 November) stay unread: no results sections, tables, figures, posted results or supplements until a plan is locked and passes `dataset_ledger.assert_blind_allowed`; [decision 0003](decisions/0003-what-makes-a-dataset-seen.md) says what an abstract or snippet has already shown.
- **Locked checks keep two commits, plan then result.** Never squash them; pull requests are merged with "Create a merge commit". Run the executable through its plan object (dry run on synthetic values) before locking.
- **Pinned data never changes in place.** A new versioned file and a new SHA-256 pin; run `python3 scripts/data_file_index.py` after adding one.
- **Read the repository before trusting a document line.** A roadmap line (Iwasaki never contacted) and a recommendation (the falling-clearance model as calibrated) were both wrong on 20 November; the code and the locked reports were right.
- **Run the full suite before every commit,** decision records included (a status line once failed its test after a commit).
- **One commit per update, about five updates per batch, one PR per batch.** No `Co-Authored-By` trailers, session links or "Generated with" footers in commits or PR descriptions (`CLAUDE.md` overrides any tool default).
- **Synthetic inputs only; validation flags stay false.**
- **AI reviews are recorded in `docs/reviews/`,** with a Handling section; they are AI re-checks, never reviews in the evidence-state sense.
- **If files change in your working copy without a command of yours,** stop, show the diff to the owner and do not commit it (12 November, unexplained).

## Running tests

- With the full requirements: `python -m unittest discover -s tests`.
- In a cloud session without the database packages: `PYTHONPATH=. python3 scripts/run_tests_without_db.py`. On 20 November: 1,610 tests, 301 database-backed errors by design. Compare the list of errors with a run on `main` before your change; CI on the pull request decides the rest.
- Database-backed tests and page renders can also run in the Linux VM on the owner's iMac (when the desktop app links the session): ship the code tree there and run with the shims under `$HOME/audit/`. Background processes there stop when a call ends.
- The 3D body map can be checked without the database: build the viewer config with `landscape_ui.body_map_pages.viewer_config(load_manifest(), build_map(110, 'explorer'), load_paths())` inside a Flask test request context, serve `landscape_ui/static`, and screenshot with Playwright using SwiftShader (`--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`).

## Open work

In the proposed order (roadmap "Now"); each item's detail is in the document named.

1. **The release pipeline** ([decision 0007](decisions/0007-first-release-covers-every-us-labelled-drug.md)). Waits on the owner's five choices: prescription only or OTC too; the reference label per ingredient; where ingestion runs (sessions cannot download in bulk); storage (needs its own decision record); trials beyond myeloma. Then a pilot of about 50 labels with sampled review.
2. **Eligibility** ([PROTOCOL_BENCHMARKING.md](PROTOCOL_BENCHMARKING.md), [ELIGIBILITY_LLM_EXTRACTOR.md](ELIGIBILITY_LLM_EXTRACTOR.md)). Round two met the bar on 19 November (378 of 400, lower bound 0.9125; `docs/verification/eligibility_second_annotation_v2.json`). Next: an adjudicated annotation version under its own plan for the 22 disagreements. The adjudication tooling (`intelligence_store/eligibility_adjudication.py`, `scripts/eligibility_adjudication_page.py`) was built for round one; check it against plan v2.1 first. **Do not revise either extractor before that,** and test any revision only on trials posted after the cohort freeze.
3. **Catalogue growth** ([EVIDENCE_FIRST_PLAN.md](EVIDENCE_FIRST_PLAN.md), item 8). Items 1–7 are done. The AI-written catalogue summaries are to be replaced by verbatim label sections once the label pilot passes; their owner review is dropped (decision 0007, amendment of 23 November).
4. **An independent reviewer** for the lenalidomide model (decided 18 November; not started).
5. **Models, lower priority** ([STATUS_BY_DRUG.md](STATUS_BY_DRUG.md)).
   - Selinexor and thalidomide label-consistency plans.
   - Carfilzomib: the label curve is not eligible. The FDA 2012 and 2025 Kyprolis reviews and the PMDA 2016 review are held unread (ledger v20); a reading plan limited to their population-model sections comes first, then the owner's choice of a published model to test blind against Badros 2013 and Quach 2017. The model scan is `docs/development/carfilzomib_model_scan_2026-11-19.md`.
   - Bortezomib stays closed: the first blind check (3.0n, NCT01801436) has both models under-predicting day 11. Kuan 2012 needs its transcription reading settled before any further check.
6. **Organ-level model** ([decision 0005](decisions/0005-organ-level-model-lumped-first.md)): evidence steps first. Body map item 17 (reporting the Atlas's swapped renal-artery names) is the owner's call.
7. **Later:** decision 0008's blood-count bands; going online.

## Smaller items

- Corrections for the Li 2017 extract when it is next versioned: Table 3 is on journal page 137, not 139; "ω (V/F):ω (CL/F)" is not stated to be a covariance.
- Author contact: Iwasaki answered on 24 and 30 October (equations, dose input, attribution; SIMULATION_3_BORTEZOMIB_PLATELETS.md 3.0j–3.0l). Kim's address bounced; Hughes on LinkedIn, pending; Zhang and Mager, reprint requested 17 November. None blocks anything.
- Deferred review findings: F04 (a)–(d), F17, F19, F20, F24, and F16's second half.
