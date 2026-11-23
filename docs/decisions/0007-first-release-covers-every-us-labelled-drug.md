# 0007 — The first release covers every drug with a US label, built automatically from the label, with its review state shown

**Date:** 19 November 2026 · **Status:** accepted by the owner for the scope, 19 November 2026 ("All drugs with a US label"); the owner made four of the five open choices on 20 November (below); the fifth, storage, is decision 0009

## Problem

Until today the platform's drug pages were built by hand, one drug at a time: the owner downloads a DailyMed label, the assistant writes catalogue entries (names, mechanism, warnings, interactions) from it, and the owner reviews each entry. Ixazomib took about a day this way (catalogue v2 and review round 4). Ten drugs have pages, all in multiple myeloma, and the frozen trial cohorts are myeloma only.

The owner has set the first release's scope as evidence for every drug with a US label, not only myeloma. Hand-built pages cannot reach that: DailyMed's full human prescription release alone runs to tens of thousands of label files, and review of every entry by one person cannot keep up with them.

## Options

1. **Keep building by hand, drug by drug.** Every entry reviewed. Does not reach the scope in any useful time.
2. **Build every page automatically from the label, and show plainly what was and was not reviewed.** Text taken verbatim from the label by script, with its section and label version; review by sampling, as the double-extraction rule did for round 3; hand review kept for anything that feeds a calculation or a model check.
3. **Link out only.** Each drug page lists its DailyMed label and trials, with no content taken from the label. Reaches the scope, but adds little beyond DailyMed itself.

## Decision

Option 2, with these rules:

- **Source.** The DailyMed structured product labels (SPL), which the National Library of Medicine publishes for bulk download as full releases and daily, weekly and monthly updates. Each label file used is pinned by set ID, version and checksum, as the NINLARO label was.
- **Verbatim, not summarised.** At this scale the platform shows the label's own text and section headings, with the section and label version, not AI-written summaries. A summary needs review, and unreviewed summaries for thousands of drugs would be exactly the unsupported claims the platform exists to avoid. Hand-reviewed summaries, like the ten catalogue drugs', stay where they exist.
- **Review state on every value.** Content built by script carries a plain label ("taken from the label by script, not reviewed"). Quality is measured by a sampled check under a locked plan: a random sample of extracted sections is compared with the label by the owner, with a rule fixed beforehand for what a failure means. The evidence-state ladder (`intelligence_store/evidence_states.py`) gains a state for script-extracted text.
- **Unit.** One page per active ingredient (or fixed combination), not per product: many products and generics share an ingredient. Which product's label is shown first is choice 2 (below).
- **What does not change.** Models, locked checks and blinding stay drug by drug, behind the evidence (decisions 0003 and 0005; regroup of 18 November). No model or label-based curve is added for a drug because it now has a page.

## Open choices for the owner, and the owner's answers (20 November 2026)

Asked on 20 November with a recommended option for each; the owner chose the recommended option every time.

1. **Prescription only, or over-the-counter too.** "A US label" includes OTC monographs; DailyMed publishes them as separate releases. **Prescription only.** OTC can come later as its own release.
2. **Reference label per ingredient.** **Every label listed, the original NDA or BLA holder's shown first.** The holder's label is identified from the label's own marketing category (NDA or BLA, against ANDA for generics), so no other source is needed. When an ingredient has more than one NDA or BLA label, the page says so and shows them all first.
3. **Where ingestion runs.** The working sessions have no network for bulk downloads. **The owner's computer, pilot first:** the pilot of about 50 labels runs on the owner's iMac through the linked workspace; a server is decided only if the full set needs one. For scale: on 20 November DailyMed's page listed the full human prescription release as six parts with 54,916 label files and about 16.7 GB zipped, last modified 21 September 2026.
4. **Storage.** The extracted content is too large for versioned JSON files in the repository. **Decision 0009** (proposed on 20 November).
5. **Trials beyond myeloma.** The frozen cohorts are myeloma only. **Live registry search, limits shown:** a drug outside myeloma links to a live ClinicalTrials.gov search, labelled as unfrozen, unclassified and liable to change. The frozen myeloma cohorts are unchanged.

## Amendment, 23 November 2026: AI-written summaries give way to the label's own text

Asked by the owner: once every label is on the platform verbatim, why review the myeloma drugs' catalogue entries? The owner agreed (23 November):

- **Values that feed a calculation** (doses, clearances, kidney-function cut-offs used by models and checks) are still reviewed by the owner against their source before use. Rounds 1–4 have done this for every such value so far.
- **AI-written catalogue summaries** (the safety and interaction summaries of the ten catalogue drugs) are replaced by the label's own sections, shown verbatim with their review state, once the label pilot passes. Until then they stay as they are, marked as AI-written.
- **The pending owner review of the ixazomib catalogue summaries is dropped,** since those summaries are to be replaced.

## Revisit when

The first sampled check of script-extracted text fails its rule, or the owner narrows or widens the scope.
