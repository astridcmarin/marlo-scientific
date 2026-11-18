# 0003 — A dataset is its unread values: what an abstract or a search result has shown is excluded from a blind check, not disqualifying

**Date:** 17 November 2026 · **Status:** accepted by the owner, 17 November 2026

## Problem

The ledger's rule is that a dataset becomes seen on the date anyone on the platform first reads its values, and a seen dataset can never give a blind check.

Six sources were obtained on 17 November 2026 and registered in dataset ledger v13. All six were found by web search, and search results show sentences from an abstract. Before registration:

- Badros 2013's abstract was read in full while its file was being renamed. It gives adverse-event rates, proteasome inhibition of up to 85%, the response rate, and the pharmacokinetic conclusion that carfilzomib clearance and exposure do not differ by renal function.
- Dimopoulos 2021's renal conclusion was read in a search snippet before the file was obtained.
- A covariate conclusion for isatuximab was read in a snippet about a conference abstract, not the SARCLISA EPAR.

Read strictly, the rule makes every source seen as soon as it is found. A source cannot be obtained without first being found, so no published source could ever give a blind check.

## Options

1. **The whole source is seen once any of its values has been read.** Simple, and the gate enforces it. It ends blind checks on any source found by search, which is all of them.
2. **The dataset is the values in the tables, figures, supplement or posted results.** Its ledger note records exactly what was read before registration. A blind check may not use anything the abstract reports, and, where a conclusion has been read, not the direction or absence of that effect. What stays blind is the tabulated values.
3. **Lock the check plan before searching for its data.** The cleanest order. It cannot work as stated, because a source has to be found before anyone knows it exists.

## Decision

Option 2. The owner confirmed it for Badros 2013 on 17 November 2026 (keep it unseen), and it applies to all six sources registered in ledger v13.

## What this does not do

`dataset_ledger.assert_blind_allowed` reads only `values_first_seen`. It does not read the exclusions in a dataset's note. A plan that claims a blind check on one of these datasets must therefore quote the dataset's `seen_note` and show that its prediction uses neither what the abstract reports nor a direction the note says is known. That is enforced when the plan is reviewed, not by code.

## Revisit when

A plan's prediction cannot be separated from what an abstract says; the gate is extended to read the exclusions; or a source's tables turn out to have been read, in which case the dataset is marked seen in a new ledger version.
