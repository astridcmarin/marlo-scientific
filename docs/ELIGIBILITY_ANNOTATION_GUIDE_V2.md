# Eligibility annotation guide (Phase 4.2, version 2)

This guide is for the reference annotation of the 200-trial validation sample (`eligibility_validation_sample_v2.json`). It is fixed by `eligibility_validation_plan_v2.json`; any change to these rules is a new version with a new plan.

Read only the trial's registered eligibility text. Do not use the title, other registry fields, publications, or anything you know about the trial.

## What changed from version 1

1. **Record the comparator exactly as written.** You no longer turn exclusion criteria round yourself.
   - For each value, say whether the sentence describes patients who are **eligible** or patients who are **excluded**.
   - The page works out the eligible side. For example, "CrCl < 30" that describes **excluded** patients is stored as ≥ 30.
   - If you leave "describes" empty, the section decides: inclusion → eligible, exclusion → excluded. Change it only for sentences like "No …" or "Patients with … are not eligible" under the inclusion heading.
2. **"Multiple" is only for values that differ by part of the study:** cohorts, arms, parts, phases or dose levels. An exception for some patients is a **qualifier**, not a second value. Examples are "≥ 30,000 if marrow plasma cells ≥ 50%", Gilbert's syndrome, liver involvement, or "≥ 500 for patients with …".
3. **The thresholds are now any direction.** The types are thresholds for these measures, not only minimums or maximums. A trial for patients with kidney impairment may require "eGFR < 40": record it.
4. **Thresholds that only define the disease are left out**, with a note. These are diagnostic or progression definitions such as CRAB or SLiM criteria ("renal insufficiency: CrCl < 40 mL/min", "anaemia: haemoglobin > 2 g/dL below the lower limit").
5. **ECOG equivalents.** WHO, Zubrod and SWOG performance status use the same 0–4 scale: record them as ECOG. Karnofsky or Lansky alone is not stated for ECOG; add a note.

## For each trial and each of the eight criterion types, record one status

| Status | Use when |
|---|---|
| **stated** | One threshold applies to all participants (exceptions go in the qualifier). |
| **multiple** | Different thresholds apply to different parts of the study: cohorts, arms, parts, phases or dose levels. Record each one. |
| **not_stated** | No numerical threshold for this measure appears anywhere in the text, apart from disease definitions. |
| **unclear** | A threshold seems intended but cannot be read with confidence, for example garbled or truncated text, or contradictory statements. Add a note. |

## For each value, record

1. **Comparator, as written:** ≥, >, ≤ or <. Read spelled-out forms as their symbol:
   - "at least" is ≥;
   - "no more than" is ≤;
   - "greater than" is >;
   - "less than" is <.
2. **Value, as written:** 30, 1.5, 75000. Write "1,500" as 1500.
3. **Unit**, chosen from the list for the type. Choose "other" only when none fits, and say what it is in the note.
4. **Section:** inclusion or exclusion, whichever heading the sentence is under.
5. **Describes:** eligible or excluded. Leave it empty when the section already says it.
6. **Sentence:** copy the exact text of the bullet or sentence.
7. **Qualifier** (optional): any exception that changes the threshold for some patients.

## Units

| Type | Units | How to read common wordings |
|---|---|---|
| kidney_function | mL/min; mL/min/1.73 m² | "cc/min" and "mL per minute" are mL/min. Also record the method if stated: Cockcroft–Gault, MDRD, CKD-EPI, measured (24-hour urine) or not stated. |
| creatinine | mg/dL; µmol/L; × ULN | "1.5 upper limit of normal" and "1.5 times ULN" are × ULN. |
| anc | × 10⁹/L; /mm³ (= /µL); cells/µL; × 10³/µL (K/µL) | /µL, /mcL, /µl, /mm³ and cells/mm³ are all /mm³ (= /µL) or cells/µL, and the scoring treats them as the same. "1.0 K/µL" is × 10³/µL. |
| platelets | × 10⁹/L; /mm³ (= /µL); × 10³/µL (K/µL) | As for ANC. |
| hemoglobin | g/dL; g/L; mmol/L | Read the unit carefully: 8 g/dL is the same as 80 g/L. |
| bilirubin | × ULN; mg/dL; µmol/L | "Within normal limits" or "≤ ULN" with no number is 1 × ULN, comparator ≤. |
| ast_alt | × ULN; U/L | If AST and ALT have different limits, record both values as multiple, and say which is which in the qualifier. |
| ecog | score | "0–2" and "0, 1 or 2" are ≤ 2, as written. "< 2" is recorded as < 2; the scoring treats it as ≤ 1. |

## Common situations

- **The same threshold in inclusion and exclusion:** record it once, from inclusion.
- **Criteria with "or":** if either a creatinine limit or a CrCl limit qualifies ("creatinine ≤ 2 mg/dL or CrCl ≥ 40"), record each under its own type and note "either".
- **Thresholds that only apply later in the study**, such as before cycle 2 or for re-treatment: not eligibility. Leave them out and note it.
- **Text cut off by the registry:** unclear for anything that may be missing.

## Pace

About 3–4 minutes per trial; the page saves after every trial. Annotate in the order given, which is randomised. When all 200 are done, use the review page before exporting.
