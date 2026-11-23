# Evidence first: what the evidence pages need

Written 18 November 2026, after the owner's decision to lead the first release with sourced evidence (`docs/REGROUP_2026-11-18.md`, thread 3). It is a plan to discuss, not a locked check: none of it computes a scientific result.

## How the pages were looked at

The pages were rendered with Flask's test client against a copy of the owner's database (`instance/intelligence.db`, 18 November), using the code at PR #129. Batch 19 changed the findings data but none of the pages read here. Page text and links were read; layout and appearance were not, so a rendered review is still needed.

Not rendered in that environment:
- the special-population pages, because the environment lacked scipy (a tooling gap, not a page fault);
- the trial explorer's results, which come live from ClinicalTrials.gov and the environment had no network;
- the eligibility benchmarking pages, deliberately, because they touch the blind data.

The reader in mind is a trial designer, clinical pharmacologist or regulatory professional opening the platform for the first time.

## What is already strong

- **The findings page** (`/models/findings`) lists every check in one line, grouped by drug and question, failures included, with the blind ones counted. No comparable public resource does this.
- **Drug pages link what exists.** Lenalidomide, bortezomib and daratumumab link their models, scorecards and special-population pages. Pomalidomide and dexamethasone link their label curves.
- **The frozen cohorts** give citable, reproducible counts, and the caveats about what a name match does and does not establish are stated.

## What needs work, in priority order

| # | Gap, as found | Proposed fix | Size |
|---|---|---|---|
| 1 | **The home page leads with a model.** Its first exhibit after the headline is a Patient Lab result card (lenalidomide elimination for a synthetic patient). The evidence comes second. | Lead with the trial landscape, the drug evidence and the findings page; move the Patient Lab card below them as "experimental research tools". | Small |
| 2 | **Two different totals for "multiple myeloma".** The home page shows 4,037 trials (cohort #4, all studies); the drug pages default to cohort #1 (drug or biologic, 3,085 studies). A reader sees two numbers for the same disease. | Name the cohort beside every count, use one default, and explain the four cohorts once, on the landscape page. | Small |
| 3 | **The trial explorer is live, not frozen.** `/trials` queries ClinicalTrials.gov at request time, so its counts change, while the landscape pages are frozen and citable. The difference is not stated where it matters. | One line on the explorer ("live registry search; for citable counts use the frozen landscape"), with a link. | Small |
| 4 | **No route from a drug to its checks.** Drug pages link scorecards, whose note gives a count of recorded disagreements, but not the checks themselves: a reader on the bortezomib page sees "4 recorded disagreements" but not which studies, nor that three candidate fixes failed under locked plans. (Corrected 18 November: the first version of this row said the disagreements were not visible at all.) | On each drug page, list that drug's findings lines (outcome and headline), linking to the findings page. | Small |
| 5 | **Ixazomib has a checked model, a special-population page and acceptance-rule results, but no drug page.** `/landscape/drugs/ixazomib` returns 404, because the drug catalogue (`drug_aliases_v1.json`) holds nine drugs and ixazomib is not one of them. | A new catalogue version adding ixazomib, with aliases, mechanism and label safety topics from the held NINLARO labels. Everything else it needs already exists. | Medium |
| 6 | **Drug pages do not say what the platform holds.** The carfilzomib page shows "Knowledge only" and its name matches. It does not say that the label's pharmacokinetics were extracted (21 values, awaiting review round 3) or that two kidney-impairment studies are held unread for a blind check. | One "What the platform holds" section per drug: label sections extracted and their review status; special-population evidence; models with their latest finding; regulatory documents used as sources; sources held for a planned check (counts only, never values). | Medium |
| 7 | **"Regulatory" means registry fields only.** `/landscape/regulatory` shows oversight and results-posting fields from ClinicalTrials.gov. The regulatory documents the platform reads and pins (EPAR assessment reports, FDA clinical pharmacology reviews, TGA AusPARs, label versions) are not browsable as evidence; they appear only as sources inside other pages. | A per-drug list of the regulatory documents the platform holds, with date, procedure, what was extracted and where it is used, linking to the official copy. The PDFs stay off the platform. The evidence index (`/models/evidence`, decision 0001) may already hold most of this. | Medium |
| 8 | **Over half the cohort is outside the drug catalogue.** In cohort #1, 1,701 of 3,085 studies have no curated alias match. Five drugs whose labels were extracted on 4 November (selinexor, isatuximab, thalidomide, elotuzumab, plus carfilzomib's PK) have no drug page or no label content. Newer myeloma agents are absent. | First the four label-extracted drugs, with identity, mechanism and label safety pages; their label PK waits for review round 3, as the roadmap already pauses those pages until then. Then further agents in order of study count in the cohort. | Large |
| 9 | **Long caveat blocks open several pages.** On the drug pages, the same paragraph on what alias matches do and do not establish sits above the content. | A one-line summary with the full text one click away. Wording changes go through the overclaiming audit that set these texts, so nothing is weakened. | Small |

## Done

- **18 November 2026, batch 21:** items 1, 2, 3, 4 and 9. The home page's first exhibit is now the check record (the counts from the findings file, left out if that file fails its checksum), and the Patient Lab example's recorded limitation moved into the lab section. Every count page names its cohort, and a note lists the four cohorts. The explorer says it is live. Drug pages list their checks, each linked to its row on the findings page. The drug pages' caveat is folded, with its wording unchanged. Checked on renderings of the home, trial explorer, landscape and bortezomib pages.
- **18 November 2026, batch 21:** item 5. Ixazomib is in the drug catalogue (v2, from the NINLARO DailyMed SPL version 18), so `/landscape/drugs/ixazomib` exists, with names, mechanism, six label warnings and two studied interactions. The reviewed names Ixazomib Citrate and MLN9708 now count on its row. The safety, interaction and mechanism catalogues moved to v2 with it; every v1 entry is carried over unchanged. The summaries are AI-written from the label and await the owner's review.
- **19 November 2026, batch 23:** items 6 and 7. Each drug page's hub gains *Sources the platform holds* and *Regulatory documents*, computed by `intelligence_store/drug_holdings.py` from the dataset ledger and the special-population summaries: each source with its files' review state and the locked checks that used it; sources held unread for a planned blind check by title only; regulatory documents (product labels, EMA assessment reports, FDA reviews, TGA AusPARs, and the catalogue's DailyMed label version) with their state. `/landscape/regulatory` says the documents are on the drug pages.

## Suggested order

1. **Small fixes first, as one batch:** items 1, 2, 3, 4 and 9. They change what a first-time reader sees and need no new data.
2. **Ixazomib's drug page** (item 5). It closes the most visible inconsistency, and its inputs exist.
3. **"What the platform holds" and regulatory documents** (items 6 and 7). Check the evidence index first; it may already have the data.
4. ~~**Catalogue growth** (item 8), after review round 3, which Track B closes.~~ **Dropped on 23 November** (decision 0007, amendment): these drugs come in through the label pipeline; the alias-coverage gap is to be closed from its ingredient names.

Each batch ends with a rendered review of the changed pages, not only the text.

## Not in this plan

Model pages, the body map and Patient Lab are unchanged. Evidence-first changes which pages lead and how complete they are; it does not hide the models or change any result.
