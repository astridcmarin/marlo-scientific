# Why the v2 eligibility reference needed correcting — causes, by class

**Exploratory, post hoc classification. Not a locked check, and it has no acceptance rule.** It was produced after the reference re-reading result (`docs/verification/eligibility_reference_review_v1.json`, findings `eligibility_reference_review_v1`) in order to write annotation guide v3. It makes no claim about either extractor's accuracy.

- Date: 16 November 2026. Record: [`eligibility_reference_review_causes_v1.json`](eligibility_reference_review_causes_v1.json), one row per item, carrying no annotation values.
- Input: the owner's re-reading record of 14 November (SHA-256 `bbbdd127289625892066bc2e904b40f392424239f4bb4e7f3e60ebdfa5d2e212`, held on the owner's iMac), the pinned annotation and the frozen extractor outputs.
- Method: for each of the 215 completed items, the shape of the change between the original annotation and the owner's locked blind reading, then a likely cause from the sentence text. Classification is by script, so it is reproducible but not reviewed item by item.

## Causes of the 108 corrections

| Cause | Count |
|---|---|
| Value missed entirely (original said not_stated; the trial states a limit) | 35 |
| Comparator wrong | 30 |
| "Multiple" recorded where a single value applied | 17 |
| Value or unit wrong | 9 |
| Value withdrawn (recorded where the trial states none) | 8 |
| Sentence attribution only | 3 |

## What the comparator errors were

Of the 27 pure comparator corrections, 19 added "or equal to" — twelve `<` to `≤`, six `>` to `≥`, one the reverse. Eight changed direction. The section and "describes" fields were unchanged in 24 of 27, so these are not exclusion-flip errors: the original annotation recorded a strict comparator where the trial wrote "or equal to".

## Where the reference was weakest

Corrected items per type: bilirubin 24 of 37, AST/ALT 23 of 38, ANC 9 of 15, platelets 13 of 28, ECOG 11 of 24, haemoglobin 10 of 22, kidney function 10 of 26, creatinine 8 of 26. The types measured in × ULN or in several interchangeable count units fared worst; the two with the cleanest units fared best.

The 31 items whose status involved "multiple" are concentrated in platelets (11) and haemoglobin (6), and 28 of the 31 moved from multiple to a single stated value. Guide v2 already made that a qualifier rather than a second value, and gave the platelet marrow-plasma-cell case as its example, so the rule existed and did not take.

## On anchoring

Every one of the 215 readings was locked before that item's answers were revealed, with no exceptions in the record. Because the owner worked item by item, drift toward the extractors' conventions over the session was tested: agreement of the locked blind reading with both extractors runs 77%, 68%, 70% and 59% across the four quarters in the order worked. It declines, where drift would raise it.

The corrected reading agreed with both extractors in 83 of 108 corrections, with one of them in 9, and with neither in 16. Since each reading was locked blind, that agreement was not formed by seeing their answers.

This does not establish either extractor's accuracy. 16 corrections, 18 of the 79 "annotation stands" items and 17 of the 28 unclear items agree with neither extractor, and the corrected reference is still one reader. The independent second annotator remains the deciding step.

## Comparator forms that do not occur

The forms `/>`, `/<`, `⩾` (U+2A7E), `⩽` (U+2A7D), `&ge;`, `&le;` and a spaced `> =` appear nowhere in the criteria text of the 216 items. Extractor v1.1 mishandles all of them — it reads `/>` and `/<` as strict comparators and drops the other five entirely — but none of the corrections is attributable to them. They are recorded here as known defects without effect on this sample.

## Bands: a schema limitation, not an annotation error

Four items carried a value from each section in the original annotation. Three are bands rather than repetitions: inclusion "haemoglobin < 10 g/dL" with exclusion eligible-side "≥ 8", inclusion "creatinine > 2" with exclusion "≤ 2.5", and a platelet pair. These are trials enrolling patients who already have impairment, where the floor sits in one section and the ceiling in the other, so both bounds are operative. The re-reading kept the inclusion bound in all four and so lost the other, which makes these four corrections a loss of information rather than a repair.

The eight types each hold one threshold in one direction, so no band can be recorded as such. Guide v3 records both bounds under the `multiple` status with a "band" note, which is what the original annotation did and what v1.1 emits when the two bounds differ. A later annotation version should carry bands in their own right. These are the trials in the impaired populations the platform is built around, so the limitation is worth retiring rather than living with.

## Extractor defect found while checking the conventions

For a genuine multi-part trial ("≥ 100,000 for cohort A and ≥ 75,000 for cohort B") v1.1 returns status `stated` with the first value only, where the guide calls for `multiple` with both. Annotation and extractor will therefore disagree on every true multi-cohort trial, in the annotation's favour. Not yet recorded as a finding; it needs its own plan.
