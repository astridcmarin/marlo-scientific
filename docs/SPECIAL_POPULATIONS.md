# Phase 4.2 — Special-population evidence summaries (design plan)

Written 30 October 2026, before any summary is built.

## Purpose

For each drug, show in one place what is known about exposure in special populations. This is the question a clinical pharmacology reviewer, a trial designer writing eligibility criteria, or a regulatory professional asks first: what happens to exposure with kidney or liver impairment, with age, and with body size, and what does the label do about it?

The layout follows the "intrinsic factors" part of an FDA clinical pharmacology review. It is a research reference, not dosing guidance.

## Structure of a summary

One summary per drug. Rows are **domains**:

| Domain | Typical content |
|---|---|
| Kidney function | Dedicated renal study or label statement; exposure change by group; dialysis; label action |
| Liver function | Dedicated hepatic study or label statement; categories used (NCI-ODWG, Child-Pugh); label action |
| Age | Covariate tested or retained in a population model; label geriatric statement |
| Body size | Weight or BSA effects; fixed versus body-size dosing |
| Sex, race and other covariates | Tested and not retained, or retained with effect size |

Each row holds **statements**. Each statement is one of:

| Kind | Meaning |
|---|---|
| `study_exposure_change` | An observed exposure ratio or group values from a named study (n, statistic, interval when given) |
| `label_statement` | What the label says about the population, quoted, with its section |
| `label_action` | The label's dose modification or avoidance for the population |
| `covariate_effect` | An effect retained in a published population model (form and size) |
| `covariate_not_retained` | Tested in a population model and not retained (with the tested range) |
| `not_studied` | The source states the population was not studied |
| `platform_model_scope` | How the platform's own model handles the population (scope tier), linking to the scope page |
| `gap` | Nothing in the platform's pinned sources; shown as such |

## Rules

1. **Every value resolves to a pinned file.** A statement stores its value and a pointer (file and JSON path) into a pinned extract. The builder resolves the pointer, and a test fails if the stored value differs from the source. No value is typed in by hand without its source.
2. **Study, label and model findings are kept apart.** Observed study results, label wording and model covariates are different kinds of evidence and are labelled as such. Study populations are named (myeloma, solid tumours, healthy subjects, not stated).
3. **Unknown stays unknown.** A domain with no pinned source shows `gap`, not a guess or remembered value. Filling a gap means a new pinned extract, page-checked, with its own review status.
4. **No recommendations.** The platform quotes label actions; it does not propose doses.
5. **Extraction status shown.** Each source shows whether its extraction is AI-assisted or independently reviewed.

## Data model

- `intelligence_store/data/special_populations_<drug>_v1.json` (pinned): the drug's rows and statements, each with `value` and `source` (`file`, `pointer`, `location` in the original document).
- `intelligence_store/special_populations.py`: loads a summary, resolves every pointer against the pinned file (checking that file's checksum against the platform's own pin), and refuses to render a summary whose values do not match.
- Page: `/landscape/drugs/<drug>/special-populations`, with a JSON download. It is linked from the drug library and from the drug's model pages.

## Order of work

1. **Ixazomib** (dedicated renal and hepatic studies, population model covariates, scope).
2. **Pomalidomide** (label renal and hepatic folds and actions; Li 2017 covariates).
3. **Lenalidomide** (CC-5013-PK-001 groups, dialysis evidence, Hughes and Kim covariates and scopes). The hepatic domain is a gap until a source is pinned.
4. **Daratumumab** (Luo covariates; renal and hepatic tested and not retained).
5. **Dexamethasone** (label: renal and hepatic not studied; NEOFORDEX patient exposure).
6. **Bortezomib**: new extractions needed (label hepatic action; the FDA and EMA review documents already held).

Gaps found along the way are listed in each summary and in this document.

## Not in scope

Drug interactions and food (extrinsic factors) are a later, separate summary. Pregnancy, lactation and paediatrics are not covered: the myeloma drugs here have no paediatric indication, and their reproductive risks belong to the safety catalog.

## Status

| Drug | Summary | Gaps |
|---|---|---|
| Ixazomib | Built 30 October 2026 (`special_populations_ixazomib_v1.json`) | The product information itself is not extracted; the label actions are quoted as reported by the study articles |
| Pomalidomide | Built 30 October 2026 (`special_populations_pomalidomide_v1.json`) | Age, body size, sex and race (label sections 8.5 and 12.3 not extracted for these) |
| Lenalidomide | Built 30 October 2026 (`special_populations_lenalidomide_v1.json`) | Liver function; label renal dose adjustments; age as a tested covariate; sex and race |
| Daratumumab | Built 30 October 2026 (`special_populations_daratumumab_v1.json`) | Age; label statements (renal and hepatic are from the population model only) |
| Dexamethasone | Built 30 October 2026 (`special_populations_dexamethasone_v1.json`) | Age, body size; the label states renal and hepatic impairment were not studied |
| Bortezomib | Built 30 October 2026 (`special_populations_bortezomib_v1.json`), from a new extract of the 2012 VELCADE label (`bortezomib_label_special_populations_2012_v1.json`), transcribed from the scanned label pages | Body size; later label revisions not reviewed |

Pages: `/landscape/drugs/<drug>/special-populations` for all six drugs: ixazomib, pomalidomide, lenalidomide, daratumumab, dexamethasone and bortezomib. Statements may carry a display hint (`mean_sd`, `gm_cv`, `range`, `ratio_ci`, `bands`) that changes only how a value is shown. The drug and model library links each drug that has a summary; ixazomib is not in the curated catalog, so its exposure page links its summary instead.
