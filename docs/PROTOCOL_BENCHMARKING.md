# Protocol benchmarking — design plan (Phase 4.1a)

Status: **design and data export, 21 October 2026.** Roadmap Phase 4.1: let a trial designer compare a draft protocol's eligibility criteria with those of similar registered trials, with counts and a link to every trial behind each number. First disease: multiple myeloma.

## The question it answers

*"In phase 2–3 trials of relapsed multiple myeloma, what minimum creatinine clearance did other protocols require, and how many accepted patients below 30 mL/min?"*

Today a trial designer answers this by opening dozens of registry records by hand. The platform already holds the records (the saved myeloma cohort); what is missing is a reliable reading of the criteria text.

Why it matters scientifically: eligibility thresholds decide who a trial can enrol. Kidney, liver and blood-count cutoffs that are stricter than the drug's pharmacology requires exclude older and sicker patients, which is the population the drug will later be used in. FDA guidance (*Enhancing the Diversity of Clinical Trial Populations — Eligibility Criteria*, 2020; *Cancer Clinical Trial Eligibility Criteria* series, including organ dysfunction) asks sponsors to justify such cutoffs. This tool shows the range other protocols used; it does not judge any of them.

## What the data look like

Eligibility criteria on ClinicalTrials.gov are one free-text field per trial, usually bulleted under "Inclusion Criteria" and "Exclusion Criteria". The same idea is written many ways:

| Concept | Ways it is written |
|---|---|
| Kidney function | "creatinine clearance ≥ 30 mL/min", "CrCl > 40 ml/min (Cockcroft-Gault)", "eGFR ≥ 45 mL/min/1.73 m²", "serum creatinine ≤ 2.0 mg/dL", "creatinine < 1.5 × ULN" |
| Neutrophils | "ANC ≥ 1.0 × 10^9/L", "absolute neutrophil count ≥ 1,000/mm³", "ANC ≥ 1000 cells/µL" |
| Platelets | "platelets ≥ 75,000/mm³", "platelet count ≥ 50 × 10^9/L" (often lower if marrow is heavily infiltrated) |
| Liver | "total bilirubin ≤ 1.5 × ULN", "AST and ALT ≤ 3 × ULN" |
| Performance status | "ECOG 0–2", "Karnofsky ≥ 60%" |

Some criteria sit under Exclusion and are written as the opposite ("Exclusion: creatinine clearance < 30 mL/min"). A reliable reading has to handle direction, units and the inclusion/exclusion section.

## Scope of version 1

**Criterion types** (each reported separately, with its own accuracy):

1. Minimum creatinine clearance or eGFR (mL/min, or mL/min/1.73 m², kept separate; the estimating equation recorded when stated).
2. Maximum serum creatinine (mg/dL or × ULN, kept separate).
3. Minimum absolute neutrophil count (normalised to 10⁹/L only when the unit is explicit).
4. Minimum platelet count (same rule).
5. Minimum haemoglobin (g/dL or g/L, kept separate).
6. Maximum total bilirubin (× ULN or mg/dL, kept separate).
7. Maximum AST/ALT (× ULN).
8. Maximum ECOG performance status.

**Every extracted value keeps:** the trial and snapshot, the exact sentence it came from, the section (inclusion or exclusion), the direction after reading the section, the unit as written, and any qualifier ("unless due to myeloma", "without transfusion").

**Units are never converted silently.** 30 mL/min (Cockcroft–Gault) and 30 mL/min/1.73 m² (eGFR) are different measures and are counted separately. Converting creatinine between mg/dL and µmol/L is exact and allowed; × ULN cannot be converted to an absolute value and stays separate.

**Unknown stays unknown.** A trial that does not mention a criterion is "not stated", never "no limit".

## How extraction works, and how it is checked

**Method: rules first.** Version 1 uses explicit patterns (regular expressions plus a small section parser), not a language model. Rules are transparent and repeatable, and every miss can be traced. A language-model extractor can be added later (Phase 5) and judged against the same checks.

**Validation before anything is shown.** This is the equivalent of the locked model checks:

1. **Locked plan.** Before running the extractor on the full corpus, a plan is committed that fixes the criterion types, the annotation rules, the sample, and the pass thresholds.
2. **Reference annotation.** A random sample of trials (proposed: 120 interventional trials, stratified by phase and start-date decade, drawn with a fixed seed) is annotated by hand: for each criterion type, the value, unit, direction and sentence, or "not stated". The person annotating should not see the extractor's output first. **This is the step that needs a domain expert** (clinical research coordination and GCP training are exactly the background for it).
3. **Accuracy per criterion type.** Precision (of the values extracted, how many are right) and recall (of the values present, how many were found), with 95% intervals.
4. **Pass rule (proposed, fixed in the locked plan):** a criterion type is shown only if its precision is at least 0.95 with a 95% lower bound of at least 0.90, and its recall is at least 0.85 with a 95% lower bound of at least 0.75. Types that fail stay hidden, with the reason shown, until the rules improve and a new locked check passes.
5. **Every number on the page links to the trials and sentences behind it**, so a user can verify any count by reading the source text.

## What the user will see (version 1)

A benchmarking page for one saved cohort, filtered by phase, recruitment status, start-date range and line of therapy where stated:

- For each criterion type that passed: the distribution of thresholds (for example, "minimum CrCl: ≥ 30 in 112 trials, ≥ 40 in 41, ≥ 50 in 19; not stated in 210"), each bar linking to its trials and sentences.
- A "draft protocol" box: enter a threshold and see how many similar trials were stricter, equal or more permissive.
- The accuracy of each criterion type, and the checks behind it.

## What it does not do

- It does not recommend criteria or judge any protocol.
- It does not say who actually enrolled; criteria are not participant characteristics.
- It does not infer anything from criteria that are not stated.
- It does not read protocol documents beyond the registry text.
- It is not a regulatory submission tool.

## Data

The trial records live in the local database (about 440 MB), which this workspace cannot read and is too large to copy. A one-time export writes only what benchmarking needs:

```
PYTHONPATH=. flask --app app/app.py eligibility-corpus-export --list
PYTHONPATH=. flask --app app/app.py eligibility-corpus-export --cohort-id <id> --output Articles/eligibility_corpus_cohort<id>.json
```

The file (`eligibility-corpus-v1`) holds, for each trial in the cohort, the identifier, snapshot, phase, status, dates, conditions, interventions, sponsor, enrolment and the eligibility fields exactly as registered, plus the cohort's query and a checksum of the whole file. It also verifies the cohort's reported size (the 4,037-trial figure has not been checked in the repository so far). ClinicalTrials.gov data are public; whether the corpus itself is committed or kept with the other source files will be decided when its size is known.

## Steps

1. **4.1a — this plan and the export command** (`intelligence_store/eligibility_corpus.py`).
2. **4.1b — corpus pinned** (done 21 October 2026): `intelligence_store/data/eligibility_corpus_mm_cohort3_v1.json.gz`, loaded by `eligibility_corpus.load_corpus()`, which checks the SHA-256 of the decompressed export (`bf01ddcf…`) and the file's own content checksum (`5d1ed413…`). Cohort 3: multiple myeloma, all interventional studies, retrieved 5 October 2026; **3,450 trials, 3,449 with criteria text** (the locally reported figure of 3,450 interventional studies is confirmed; the 4,037 total includes observational and expanded-access records not in this cohort). Phases: phase 2 1,209; phase 1 806; phase 1/2 478; not applicable 378; phase 3 375; early phase 1 103; phase 4 63; phase 2/3 37. Start decades: 1990s 140, 2000s 860, 2010s 1,292, 2020s 1,140. Median criteria text 2,708 characters.
3. **4.1c — annotation guide and locked validation plan** (locked 22 October 2026): [annotation guide](ELIGIBILITY_ANNOTATION_GUIDE.md), plan `eligibility_validation_plan_v1.json`, sample `eligibility_validation_sample_v1.json` (120 trials, proportional across five phase groups: phase 1 32, phase 1/2 17, phase 2 42, phase 2/3 or 3 14, other 15; seed 20261022; fixed shuffled annotation order) and a disjoint 200-trial development set for building the extractor. Scoring per (trial, criterion type) pair with Wilson 95% intervals; types with fewer than 20 annotated values cannot pass.
   - **Annotation page** (`landscape_ui/eligibility_annotation_pages.py`): `/landscape/benchmarking/annotate`, one trial at a time in the fixed order, showing only the registered criteria text. Every value must quote a sentence found in that text; each trial is saved on submit to `instance/eligibility_annotations_v1.json` (local, not committed); a re-save needs a reason and is logged. Export with `eligibility-annotations-export` when all 120 are done.
   - **Self-review before export** (`intelligence_store/eligibility_annotation_review.py`): `/landscape/benchmarking/review`. It lists what was recorded for every saved trial and the status counts per criterion. Each trial can be re-read with its recorded sentences highlighted. It also prompts on:
     - a bound on the wrong side for the type;
     - a section that does not match the heading the sentence sits under;
     - an exclusion value that keeps the sentence's own comparator;
     - a value not found in its sentence;
     - a measure named in the text but marked not stated.

     The prompts come only from the annotation and the text, never from the extractor. A trial is marked reviewed for the version saved; a later correction is logged as usual and needs reviewing again. This pass happens before the extractor runs on the sample, so corrections made in it cannot favour the extractor.
4. **4.1d — extractor** (`intelligence_store/eligibility_extractor.py`, version `eligibility-extractor-v1.0`): rules written and tuned only on the 200-trial development set; the validation sample's text has not been read. In order, it:
   - cleans the registry text (markdown escapes such as `\>=`, Unicode ≥/≤, spelled-out comparators such as "at least", "no greater than", "< or =");
   - splits it into clauses and tracks the inclusion and exclusion sections;
   - takes the first comparator, number and unit after each measure's keyword;
   - turns exclusion criteria (and inclusion criteria starting "No …") into the eligible side;
   - records the kidney-function equation when one is named.

   Exceptions written as conditions ("≥ 30,000 if marrow plasma cells ≥ 50%", "except Gilbert's syndrome", "unless …") are treated as qualifiers. A second value for the same measure in one clause is usually the same value in another unit, and is counted once. A minimum type keeps only lower bounds and a maximum type only upper bounds, so disease definitions ("Renal insufficiency: CrCl < 40") are not read as thresholds. The extractor never answers "unclear".

   **Development set (200 trials), not a measure of accuracy:**

   | Type | Trials with a value found (of 200) |
   |---|---|
   | ECOG | 134 |
   | Bilirubin | 95 |
   | AST/ALT | 95 |
   | Platelets | 90 |
   | ANC | 82 |
   | Kidney function | 70 |
   | Haemoglobin | 62 |
   | Creatinine | 52 |

   **Known misses seen there:**
   - thresholds written before the measure ("> 1.5 × ULN total bilirubin");
   - second-cohort values ("≥ 100 for run-in and 75 for phase II");
   - adequate values listed under the exclusion heading;
   - trials of impaired kidney function whose eligible range is an upper bound ("eGFR < 40").

   Accuracy is only measured by the locked check (4.1e). The rules are frozen once the sample is scored; changes after that need a new version and a new locked check.
5. **4.1e — reference annotation** of the sample (by hand), then the locked accuracy check.
6. **4.1f — benchmarking page** showing only the criterion types that passed.
