# Evidence connections: plan with acceptance criteria (11 November 2026)

**Status:** updates 1-4 done in batch 6 (11 November). The evidence index is at `/models/evidence`, the sex-evidence map at `/models/sex-evidence`. Two acceptance points narrowed in the doing: evidence states are shown on the evidence page (the extract panels already show the owner-review text that sets them), and enrolment by sex is shown as not available, since it needs ClinicalTrials.gov posted results the platform has not retrieved.

Draws on an outside review (ChatGPT, 11 November 2026) of the repository, keeping only what Marlo does not already do. Already in place, and not repeated here: per-value provenance in pinned files (quote, location, SHA-256), owner-review status, the dataset ledger and locked checks, supplied/derived/estimated/assumed labels in Patient Lab, scope files and credibility records, and the standing rules in `CLAUDE.md`.

**Not in this plan, on purpose:** a new database or graph database, a common class rewritten across models, a full canonical data model with external identifiers, an in-product AI assistant, and SBML/PharmML/FHIR export. Each is reconsidered when a page or a user needs it.

## Update 1: two standing rules and a decision record

**What.** Two rules added to `CLAUDE.md`, and a folder `docs/decisions/` for short architecture decision records. The first record is for the evidence index (update 2).

- Before changing an existing scientific calculation, add or confirm a regression test that pins its current output.
- Before a new dependency, database change or scientific framework, write a decision record: the problem, the options, the choice, and what would make us revisit it.

**Accepted when** the two rules are in `CLAUDE.md`, `docs/decisions/0001-evidence-index.md` exists, and a test checks every decision record has the four headings.

## Update 2: the evidence index (read-only, derived)

**What.** `intelligence_store/evidence_index.py` builds, on demand, a list of connections from what the pinned files already state; nothing new is recorded by hand. The connections are:

| Connection | Taken from |
|---|---|
| file → file it cites | every `{file or path, sha256}` reference inside a pinned file (303 today) |
| file → file it supersedes | `supersedes` blocks (49 today) |
| file → source document | each file's `source` block (title, location, `file_sha256` of the PDF where pinned) |
| model → file it uses | the credibility context's source extracts and scope files |
| check → model, check → dataset | the dataset ledger's uses |
| check → files it pinned | each check report's recorded inputs |

Each connection carries: from, to, type, the field it was read from, the version (SHA-256) and the date recorded.

**Accepted when:**
- every reference resolves to a file that exists, and its SHA-256 matches. A mismatch or a missing file is listed as a finding, never silently skipped; a test fails on any new one;
- for lenalidomide the index answers, by test: which models use `hughes_parameter_precision_v2.json` (Hughes 2019); which models and checks depend on the Hughes weight-basis assessment; which files supersede which;
- a page `/models/evidence/<file>` shows, for any pinned file, what it comes from, what uses it, and what superseded it;
- no database table, migration or new dependency is added.

## Update 3: the evidence-state ladder

**What.** Each pinned extract gets a computed state, shown on the index page and on the extract's panels. The states never substitute for one another:

| State | Means | Comes from |
|---|---|---|
| Extracted | Taken from a source; quotes matched by script where checked | the file itself |
| Reviewed by the owner | Checked against the source by the platform owner | review records (rounds 1-3) |
| Agreed by two extractions, sampled | A second, independent extraction agreed and the sample found no error | Track B, when run |
| Used by a model checked against outside data | A model using it has a locked check against data it was not built from | dataset ledger and check findings |

The fourth state describes the model, not the value: a correct extract does not make a model valid, and the page says so.

**Accepted when** every pinned extract has exactly one of the first three states, and the fourth is shown separately; a test checks that no extract is shown as reviewed without a review record; AI reviews (the 10 November review) are listed as AI re-checks, not as reviews.

## Update 4: the sex-representation evidence map (Track I)

**What.** For each myeloma drug on the platform:
- enrolment by sex in the trial dataset, where the registry records it;
- what the label and the regulatory reviews state about sex effects, quoted;
- whether each source PK model tested sex as a covariate;
- where sex enters the platform's own calculations (Cockcroft–Gault, fat-free mass, CKD-EPI), with the published equation.

**Accepted when** every number is computed from pinned data or quoted with a location; "not reported" is shown as such; no sex adjustment is added to any model; the page says this describes the evidence and predicts nothing.

## Order

1 → 2 → 3 → 4, each one commit in batch 6 after the two locked plans. Update 4 does not depend on 2 or 3.
