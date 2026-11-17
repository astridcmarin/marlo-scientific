# Eligibility annotation guide (Phase 4.2, version 3)

This guide is for the reference annotation of the 200-trial validation sample (`eligibility_validation_sample_v2.json`) and for the independent second annotator.

Version 2 ([`ELIGIBILITY_ANNOTATION_GUIDE_V2.md`](ELIGIBILITY_ANNOTATION_GUIDE_V2.md)) is unchanged and still fixes the plans locked against it: `eligibility_validation_plan_v2.json`, `eligibility_reference_review_plan_v1.json` and `eligibility_second_annotation_plan_v1.json`. Any plan that uses *this* version must pin this file, which means a new plan version.

Read only the trial's registered eligibility text. Do not use the title, other registry fields, publications, or anything you know about the trial.

## Why version 3

The re-reading of 14 November corrected 108 of 215 items. The causes are classified in [`development/ELIGIBILITY_REFERENCE_CAUSES.md`](development/ELIGIBILITY_REFERENCE_CAUSES.md). Four of them are addressed here, in the order of how much they cost:

1. **35 values were missed entirely** — recorded as not_stated where the trial states a limit. Section 1 is new and is the main change.
2. **19 comparators dropped "or equal to"** — a strict `<` or `>` recorded where the trial wrote `≤` or `≥`. Section 4 is rewritten.
3. **17 items used "multiple" for a single value with an exception.** Version 2 had this rule and gave the right example; it did not take, so section 5 promotes it to a two-question test.
4. **Bilirubin, AST/ALT and ANC were the weakest types**, and they are the ones measured in × ULN or in several interchangeable units. Section 6 gives each a worked rule.

5. **Four items recorded a bound in each section**, which version 2 covered only for a repeated threshold. Three of the four were bands, and the re-reading dropped one bound in each. Section 5, question 3 and section 8 now treat them as bands.

Nothing else changes. Where version 3 is silent, version 2's rule still stands.

## 1. Where to look, before you record not_stated

**not_stated means: "I looked in all six places below, searched the measure's other names, and there is no numerical threshold."** It does not mean "I did not see one".

1. The inclusion list, **including every sub-bullet**. Limits are often nested under a parent bullet that names no number: "adequate organ function", "adequate bone marrow function", "adequate hepatic function", "adequate renal function", "adequate haematologic function".
2. Any block headed **PATIENT CHARACTERISTICS**, **DISEASE CHARACTERISTICS** or **PRIOR CONCURRENT THERAPY**. Older registry entries use this layout instead of Inclusion/Exclusion headings, and the laboratory limits usually sit under PATIENT CHARACTERISTICS.
3. A block headed **Laboratory**, **Laboratory values** or **Required laboratory values**.
4. The **exclusion list**. The limit frequently appears only there, as its own bound: "Exclusion: platelet count < 75,000". That is a stated threshold, recorded as the eligible side.
5. **Text on the same line as a heading, after a colon.** Registry text often runs a limit onto the heading line.
6. **The measure's other names.** Search for each one before concluding not_stated:

| Type | Also written as |
|---|---|
| kidney_function | creatinine clearance, CrCl, CrCL, CCr, eGFR, GFR, glomerular filtration rate, Cockcroft–Gault, MDRD, CKD-EPI |
| creatinine | serum creatinine, SCr, Cr |
| anc | absolute neutrophil count, ANC, neutrophils, neutrophil count, granulocytes, absolute granulocyte count, AGC, PMN |
| platelets | platelet count, PLT, thrombocytes, thrombocyte count |
| hemoglobin | haemoglobin, Hgb, Hb, HGB |
| bilirubin | total bilirubin, T. bili, TBIL, bili |
| ast_alt | AST, ALT, **SGOT, SGPT, ASAT, ALAT, GOT, GPT**, aspartate aminotransferase, alanine aminotransferase, transaminases, aminotransferases |
| ecog | ECOG, WHO, Zubrod, SWOG, performance status, PS |

The bold forms in the AST/ALT row are the ones that caused missed values in round 1.

## 2. One status per trial and per criterion type

| Status | Use when |
|---|---|
| **stated** | One threshold applies to all participants. An exception for some patients goes in the qualifier, and the status stays stated. |
| **multiple** | Either different thresholds apply to different **parts of the study** (cohorts, arms, parts, phases, dose levels), or the measure carries a **band** — a floor and a ceiling in different sections (section 5, question 3). Record each value. |
| **not_stated** | No numerical threshold appears in any of the six places in section 1, under any of the names, apart from disease definitions (section 7). |
| **unclear** | A threshold seems intended but cannot be read with confidence: garbled or truncated text, or contradictory statements. Add a note. |

## 3. For each value, record

1. **Comparator, as written** — section 4.
2. **Value, as written:** 30, 1.5, 75000. Write "1,500" as 1500.
3. **Unit**, from the list for the type — section 6. Choose "other" only when none fits, and say what it is in the note.
4. **Section:** inclusion or exclusion, whichever heading the sentence is under.
5. **Describes:** eligible or excluded. Leave it empty when the section already says it. Change it only for sentences like "No …" or "Patients with … are not eligible" **under the inclusion heading** — that is the one case where the heading and the meaning disagree, and it is where a reversed comparator comes from.
6. **Sentence:** copy the exact text of the bullet or sentence.
7. **Qualifier** (optional): any exception that changes the threshold for some patients.

Record the comparator **as written**. Do not turn exclusion criteria round yourself; the page works out the eligible side.

## 4. Comparators

**The rule that matters most: if "or equal to" is there, in any form, record it.** Nineteen of the corrections were a missing equals sign. "At least 45" includes 45. "Greater than 45" does not.

### Symbols

| Written | Record as |
|---|---|
| `≥`, `>=`, `=>`, `= >`, `≧`, `=/>`, `>/=`, `> or =`, `/>` | `≥` |
| `≤`, `<=`, `=<`, `= <`, `≦`, `=/<`, `</=`, `< or =`, `/<` | `≤` |
| `>` | `>` |
| `<` | `<` |
| `\>`, `\<` | `>`, `<` — the backslash is an escape character, not part of the comparator |

A slash or a stray space beside the sign is a mangled `≥` or `≤`, not a strict comparator. `⩾` and `⩽` are `≥` and `≤`. An undecoded `&ge;` or `&le;` is `≥` or `≤`.

### Words

| Words | Record as |
|---|---|
| at least, no less than, not less than, minimum of, or greater, or above, or higher, equal to or greater than, greater than or equal to | `≥` |
| greater than, more than, higher than, above, exceeding, in excess of | `>` |
| no more than, not more than, not greater than, not exceeding, not to exceed, up to, maximum of, or less, equal to or less than, less than or equal to | `≤` |
| less than, below, under | `<` |

### A value with no comparator at all

"Patients must have a creatinine clearance of 45 mL/min" states a bound with no sign. There is no `=` comparator in this schema, and `=` would be wrong in any case: a trial asking for 45 mL/min does not exclude a patient at 46.

Record the direction the measure implies, and put the bare wording in the note:

- a floor for **kidney function, ANC, platelets, haemoglobin** → `≥`;
- a ceiling for **creatinine, bilirubin, AST/ALT, ECOG** → `≤`.

If the sentence makes the opposite direction clear — a trial enrolling patients *with* kidney impairment, say — follow the sentence and note it.

## 5. One value, or several

Two questions, in this order:

1. **Do the different numbers belong to different parts of the study** — a cohort, arm, part, phase or dose level? If yes, **multiple**, and record each.
2. **Does a second number apply to a kind of patient inside the same part?** If yes, **stated** with one value, and the second number goes in the **qualifier**.
3. **Does the same measure carry one bound in the inclusion list and a *different* bound in the exclusion list?** That is a **band**, not a repetition: a trial enrolling patients who already have impairment sets the floor in one section and the ceiling in the other, and both bounds are real. Record **multiple** with both values and write "band" in the note. If the two sections state the *same* threshold, it is a repetition — record it once, from inclusion (section 8).

Worked examples:

- "Platelets ≥ 75,000 (≥ 50,000 if marrow plasma cells ≥ 50%)" → **stated**, `≥ 75000`, qualifier "≥ 50,000 if marrow plasma cells ≥ 50%". Not multiple.
- "Platelets ≥ 100,000 for cohort A and ≥ 75,000 for cohort B" → **multiple**, both values.
- Bilirubin with a Gilbert's syndrome carve-out → **stated** plus qualifier.
- "≥ 500 for patients with liver involvement" → **stated** plus qualifier.
- Inclusion "haemoglobin < 10 g/dL", exclusion "haemoglobin < 8 g/dL" → **multiple**, `< 10` and `≥ 8`, note "band". Eligibility is 8 g/dL up to 10 g/dL, and recording either bound alone loses the other.
- Inclusion "creatinine > 2 mg/dL", exclusion "creatinine > 2.5 mg/dL" → **multiple**, `> 2` and `≤ 2.5`, note "band".

**The one exception**, which version 2 stated in its unit table and which contradicted its own rule: when **AST and ALT carry different limits** ("AST ≤ 2.5 × ULN and ALT ≤ 3 × ULN"), record them as **multiple**, both values, and say in the qualifier which is which. Two analytes are not two parts of the study, but the type holds both measures, so this is the only way to record both.

## 6. Units, by type

**A limit given as "ULN" with no number is `≤ 1 × ULN`.** This covers "≤ ULN", "within normal limits", "within institutional normal limits", "≤ upper limit of normal" and "WNL", and it applies to all three types measured in × ULN — **bilirubin, AST/ALT and creatinine**. It is a stated threshold, not not_stated: the trial is requiring a result at or below the top of the local normal range, which is 1 × ULN by definition. Extractor v1.1 reads every one of these forms the same way **except the bare abbreviation "WNL", which it misses**; record it as `≤ 1 × ULN` regardless, since the trial states a limit.


| Type | Units | How to read common wordings |
|---|---|---|
| kidney_function | mL/min; mL/min/1.73 m² | "cc/min" and "mL per minute" are mL/min. Record the method if stated: Cockcroft–Gault, MDRD, CKD-EPI, measured (24-hour urine) or not stated. |
| creatinine | mg/dL; µmol/L; × ULN | "1.5 upper limit of normal" and "1.5 times ULN" are × ULN. |
| anc | × 10⁹/L; /mm³ (= /µL); cells/µL; × 10³/µL (K/µL) | /µL, /mcL, /µl, /mm³ and cells/mm³ are the same unit to the scoring. "1.0 K/µL" is × 10³/µL. **1.0 × 10⁹/L, 1,000/mm³ and 1.0 K/µL are the same number in three units — record the one written, do not convert.** |
| platelets | × 10⁹/L; /mm³ (= /µL); × 10³/µL (K/µL) | As for ANC. **"75,000" with no unit at all is /mm³ (= /µL); "75" with no unit is × 10⁹/L.** |
| hemoglobin | g/dL; g/L; mmol/L | 8 g/dL and 80 g/L are the same number. Record the one written. |
| bilirubin | × ULN; mg/dL; µmol/L | A number with "× ULN", "times ULN" or "x the upper limit of normal" is × ULN, never mg/dL. **"Total bilirubin" is this type; "direct bilirubin" alone is not — record not_stated and note it.** |
| ast_alt | × ULN; U/L | A number with "× ULN" is × ULN; a number with "U/L", "IU/L" or "units/L" is U/L. Different limits for AST and ALT → multiple (section 5). A limit given for "transaminases" or "aminotransferases" without naming which covers both: **stated**, one value. |
| ecog | score | "0–2", "0, 1 or 2" and "0 to 2" are `≤ 2`, as written. "< 2" is recorded as `< 2`; the scoring treats it as `≤ 1`. Karnofsky or Lansky alone is **not_stated** for ECOG, with a note. WHO, Zubrod and SWOG are the same 0–4 scale: record them as ECOG. |

## 7. Thresholds that only define the disease

A threshold that exists **only** to define or stage the disease is left out, with a note: CRAB and SLiM criteria, "renal insufficiency: CrCl < 40 mL/min", "anaemia: haemoglobin > 2 g/dL below the lower limit", "measurable disease: M-protein ≥ 0.5 g/dL".

**When the same measure appears both as a disease definition and as a requirement for entry, record the entry requirement and ignore the definition.** Do not record both. This is the case the word "only" left open in version 2: if a trial defines anaemia by a haemoglobin cut-off *and* separately requires a haemoglobin minimum to enrol, the second is the one to record. Note the definition in the note field.

If the measure appears **only** in the disease definition, the status is **not_stated** with a note saying where it was and why it was left out.

## 8. Common situations

- **The same measure in inclusion and exclusion.** If both sections state the **same** threshold, record it once, from inclusion. If they state **different** bounds, it is a band: record **multiple** with both values and note "band" (section 5, question 3).
  - *Known limitation.* Each of the eight types holds one threshold in one direction, so a band has to borrow the `multiple` status, which otherwise means different parts of the study. The note is what distinguishes them. A later annotation version should carry bands in their own right; recorded here rather than worked around silently.
  - Extractor v1.1 behaves the same way: `stated` from inclusion where the two thresholds match, `multiple` with both where they differ. So this convention and the extractor remain comparable.
- **Criteria with "or":** if either a creatinine limit or a CrCl limit qualifies ("creatinine ≤ 2 mg/dL or CrCl ≥ 40"), record each under its own type and note "either".
- **Thresholds that apply later in the study** — before cycle 2, for re-treatment, for dose modification: not eligibility. Leave them out and note it.
- **Thresholds conditional on a transfusion or growth factor** ("platelets ≥ 50,000 without transfusion support in the past 7 days"): record the value, and put the condition in the qualifier.
- **Text cut off by the registry:** unclear for anything that may be missing.
- **The thresholds run in any direction.** The types are thresholds for a measure, not only minimums or maximums. A trial for patients with kidney impairment may require "eGFR < 40": record it.

## 9. Pace

About 3–4 minutes per trial; the page saves after every trial. Annotate in the order given, which is randomised. When all are done, use the review page before exporting.
