# Eligibility annotation guide (Phase 4.1c, version 1)

For the reference annotation of the 120-trial validation sample. Fixed by `eligibility_validation_plan_v1.json`; a change to these rules is a new version and a new plan. Read the trial's registered eligibility text only: not the title, other registry fields, publications or your own knowledge of the trial.

## For each trial and each of the eight criterion types, record one status

| Status | Use when |
|---|---|
| **stated** | The text gives a numerical threshold for this measure that applies to all participants. |
| **multiple** | Different thresholds apply to different parts, cohorts or arms (for example, a dose-escalation and an expansion cohort). Record each value. |
| **not_stated** | The measure is not given a numerical threshold anywhere in the text. "Adequate organ function" without numbers is not_stated. |
| **unclear** | A threshold seems intended but cannot be read with confidence (garbled text, a threshold in a table that did not survive, contradictory statements). Add a note. |

## For each value (stated or multiple), record

1. **The eligible side.** Write the threshold as the condition a patient must meet to be *eligible*, whatever section it is in.
   - Inclusion "creatinine clearance ≥ 30 mL/min" → ≥ 30.
   - Exclusion "creatinine clearance < 30 mL/min" → ≥ 30 (patients below 30 are excluded, so 30 and above are eligible).
   - Exclusion "creatinine clearance ≤ 30 mL/min" → > 30.
2. **Comparator** after that conversion: ≥, >, ≤ or <.
3. **Value** exactly as written (30, 1.5, 75000, 1.0). Do not convert.
4. **Unit** from the list for the type, exactly as written (choose "other" and note it if none fits).
5. **Section**: inclusion or exclusion, where you found it.
6. **Sentence**: copy the exact text of the bullet or sentence.
7. **Qualifier** (optional): conditions that change the threshold, such as "unless due to myeloma", "without transfusion in the previous 7 days", "≤ 3 × ULN if liver involvement". Record the general threshold as the value and the exception as the qualifier.

## The eight criterion types

| Type | What counts | Units to choose from | Notes |
|---|---|---|---|
| **kidney_function_min** | Creatinine clearance or eGFR minimum | mL/min; mL/min/1.73 m² | Record the estimating method if stated: Cockcroft–Gault, MDRD, CKD-EPI, measured (24-hour urine) or not stated. If either a CrCl *or* a creatinine limit qualifies ("creatinine ≤ 2 mg/dL or CrCl ≥ 40"), record both, in their own types, and note "either". |
| **creatinine_max** | Serum creatinine maximum | mg/dL; µmol/L; × ULN | |
| **anc_min** | Absolute neutrophil count minimum | × 10⁹/L; /mm³ (= /µL); cells/µL | "1,000/mm³" and "1.0 × 10⁹/L" are both recorded as written. |
| **platelets_min** | Platelet count minimum | × 10⁹/L; /mm³ (= /µL) | Many myeloma trials allow lower counts with heavy marrow involvement: record the general value and the exception as a qualifier. |
| **hemoglobin_min** | Haemoglobin minimum | g/dL; g/L; mmol/L | |
| **bilirubin_max** | Total bilirubin maximum | × ULN; mg/dL; µmol/L | Gilbert's syndrome exceptions are qualifiers. Direct bilirubin is not total bilirubin: note it, status not_stated unless total is also given. |
| **ast_alt_max** | AST and/or ALT maximum | × ULN; U/L | If AST and ALT have different limits, record each under multiple and say which is which in the qualifier. |
| **ecog_max** | ECOG (or WHO, which uses the same scale) performance status maximum | score | "ECOG 0–2" → ≤ 2. Karnofsky only → not_stated for ECOG, with a note "Karnofsky ≥ X". |

## Common situations

- **Ranges written as lists:** "ECOG 0, 1 or 2" → ≤ 2.
- **"Within normal limits" or "≤ ULN" without a multiplier:** record 1 × ULN, comparator ≤.
- **Lab values given only for a subgroup** (for example, "patients with renal impairment must have CrCl ≥ 15") are qualifiers if a general threshold exists; otherwise status multiple.
- **The same threshold repeated** in inclusion and exclusion: record it once (inclusion).
- **Thresholds that apply only to screening for a later part** (for example, before cycle 2): not eligibility criteria; ignore and note.
- **Text truncated by the registry:** status unclear for anything that may have been cut.

## Pace and breaks

About 3–5 minutes per trial. The page saves after every trial, so the work can be spread over several sessions. Annotate in the order given (it is randomised); do not skip trials, and do not go back to change a saved trial except to correct a clear slip, which the page records with the time.
