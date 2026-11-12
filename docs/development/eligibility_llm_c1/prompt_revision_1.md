# Eligibility threshold extraction: instructions for the model (extractor llm-c1, prompt version 1)

You read the registered eligibility criteria text of one clinical trial and report numerical thresholds for eight laboratory and performance measures. You use only the text you are given: not the trial title, other registry fields, publications, or anything you know about the trial.

## The eight types

| Key | Measure | Allowed units |
|---|---|---|
| `kidney_function_min` | Creatinine clearance or estimated GFR | `mL/min`, `mL/min/1.73 m2` |
| `creatinine_max` | Serum creatinine | `mg/dL`, `umol/L`, `x ULN` |
| `anc_min` | Absolute neutrophil count | `x 10^9/L`, `/mm3 (= /uL)`, `cells/uL`, `x 10^3/uL (K/uL)` |
| `platelets_min` | Platelet count | `x 10^9/L`, `/mm3 (= /uL)`, `x 10^3/uL (K/uL)` |
| `hemoglobin_min` | Haemoglobin | `g/dL`, `g/L`, `mmol/L` |
| `bilirubin_max` | Total bilirubin | `x ULN`, `mg/dL`, `umol/L` |
| `ast_alt_max` | AST and/or ALT (transaminases) | `x ULN`, `U/L` |
| `ecog_max` | ECOG performance status (WHO, Zubrod and SWOG scales count as ECOG; Karnofsky or Lansky alone does not) | `score` |

The key names are historical: each type is a threshold for that measure **in either direction**. A trial for patients with kidney impairment may require "eGFR < 40"; report it.

## Report every threshold on the eligible side

For each value give the comparator that an **eligible** patient must satisfy:
- A sentence that describes eligible patients (usually under the inclusion heading) keeps its comparator: "platelets ≥ 75,000/mm3" is `>=` 75000.
- A sentence that describes excluded patients (usually under the exclusion heading, or "No …" / "not eligible" under inclusion) is turned round: "exclude if CrCl < 30 mL/min" is `>=` 30. The pairs are `<` ↔ `>=`, `<=` ↔ `>`.
- Spelled-out forms: "at least" is `>=`, "no more than" is `<=`, "greater than" / "more than" / "above" is `>`, "less than" / "below" is `<`.
- ECOG ranges "0–2" or "0, 1 or 2" are `<=` 2.
- "Within normal limits" or "≤ ULN" with no number, for bilirubin, creatinine or AST/ALT, is `<=` 1 `x ULN`.
- Write numbers as plain decimals: "1,500" is `1500`, "1.5" is `1.5`. Keep the number and unit as written; do not convert units.

## Status for each type

- `stated`: one threshold applies to all participants. An exception for some patients (marrow involvement, Gilbert's syndrome, liver involvement, "≥ 30,000 if plasma cells ≥ 50%") does not make a second value; report only the main threshold.
- `multiple`: different thresholds apply to different parts of the study (cohorts, arms, parts, phases, dose levels). Report each one, at most three. If AST and ALT have different limits, report both values.
- `not_stated`: no numerical threshold for this measure.

## Leave out

- Thresholds that only define the disease (CRAB or SLiM criteria, "renal insufficiency: CrCl < 40", "anaemia: haemoglobin > 2 g/dL below normal").
- Thresholds that only apply later in the study (before cycle 2, for re-treatment, for dose modification).
- The same threshold repeated in inclusion and exclusion: report it once, from inclusion.
- With "or" between two measures ("creatinine ≤ 2 mg/dL or CrCl ≥ 40"), report each under its own type.

## Output

Return one JSON object and nothing else, with all eight keys:

```json
{"kidney_function_min": {"status": "stated", "values": [{"comparator": ">=", "value": "30", "unit": "mL/min", "section": "inclusion", "segment": "Creatinine clearance ≥ 30 mL/min (Cockcroft-Gault)", "equation": "cockcroft_gault"}]},
 "creatinine_max": {"status": "not_stated", "values": []},
 "...": "the other six types in the same form"}
```

- `comparator`: one of `>=`, `>`, `<=`, `<` (eligible side).
- `value`: the number as a string.
- `unit`: exactly one of the allowed units for the type.
- `section`: `inclusion` or `exclusion`, the heading the sentence is under.
- `segment`: the exact sentence or bullet the value comes from, copied from the text.
- `equation` (only for `kidney_function_min`): `cockcroft_gault`, `mdrd`, `ckd_epi`, `measured` (24-hour urine) or `not_stated`.
- For `not_stated`, `values` is an empty list.
