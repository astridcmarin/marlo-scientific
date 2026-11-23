# 0010 — Trial-to-drug matching splits combination names; investigational drugs wait

**Date:** 23 November 2026 · **Status:** accepted by the owner, 23 November 2026

## Problem

The evidence-first plan's item 8 found that over half of myeloma cohort 1 (1,701 of 3,085 studies) matched no drug in the 10-drug catalogue. When catalogue growth was dropped in favour of the label pipeline (decision 0007, amendment of 23 November), the owner asked how that gap closes. A read-only breakdown of cohort 1 on 23 November (matching rebuilt outside the platform, so it found 1,686 studies, not 1,701) showed:

- **848 studies** already match a drug through the owner-reviewed formatting-group mappings of October (966 mappings to 589 drugs: isatuximab, selinexor, elotuzumab, teclistamab and others). Their drugs only lack a page. The label pipeline gives approved drugs their page.
- **838 studies** have no matched drug name. Their 1,450 distinct unmatched names are about 460 combinations written as one name ("lenalidomide and dexamethasone"), about 330 investigational code names ("SNS01-T", "BI-505"), and about 660 others, mostly cell therapies and unlabelled products ("anti-BCMA CAR-T").

Matching today is exact by design (`drug_aliases.py`, method drug-aliases-v1.2): a name matches only if, after whitespace and case are normalised, it equals an approved alias or a reviewed formatting group.

## Options

1. **Keep exact matching only.** Combination names stay unmatched; about 460 names, and the studies that carry only them, stay in the gap.
2. **Split combination names, then match each part exactly.** Split on stated separators (commas, "and", "+", "plus", "/" and similar, fixed in a plan) and require every part, or at least one part, to match exactly. No spelling correction, no fuzzy matching, no pharmacology.
3. **Fuzzy or model-based matching.** Closes more, but introduces guessing the platform has avoided.
4. **Bring in investigational drugs through FDA's substance registry (GSRS),** which assigns identifiers and synonyms to investigational substances.

## Decision

- **Option 2, splitting:** accepted. It is a new method version beside drug-aliases-v1.2, not an edit of it. Before it is used, a locked plan fixes the separators, what counts as a match (every part or any part), how a study with a partly matched combination is shown, and a sampled review of the split matches with a pass rule, as for the label pilot. A regression test pins the current matching's output first (`CLAUDE.md`).
- **Option 4, investigational drugs:** deferred by the owner "until we are done with this phase", the first release (decision 0007). Names that look like investigational codes stay unmatched and are shown as such.
- **Option 3:** not taken.
- **Cell therapies and other unlabelled products** are recorded as their own kind of intervention, not counted as missing drugs, under the same plan.

## Revisit when

- The first release is done (investigational drugs).
- The splitting plan's sampled review fails.
- The label pipeline's ingredient names leave a large part of group A without a page.
