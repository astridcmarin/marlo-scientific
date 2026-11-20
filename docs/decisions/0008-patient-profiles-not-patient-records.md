# 0008 — A real patient enters the platform only as a banded profile that many people share, computed in the browser and never sent or stored

**Date:** 20 November 2026 · **Status:** accepted by the owner, 20 November 2026 ("lets lock this one and keep fine tuning it"). Refinements are added below as dated amendments; the four rules in *Decision* change only by a new decision record.

## Problem

The owner's aim for the platform is to compare what trials found with a real person's situation, and to show how a drug behaves in a body like theirs, for women and men. Calling such a record "synthetic patient 2" does not make it synthetic: if its values are copied from a real person, it is that person's health information under a new name, and a combination of age, diagnosis, laboratory values and medicines can identify someone. Holding it would bring privacy law, consent and security duties that the platform is not built for, and which apply differently depending on who enters the data and why.

Two related problems are recorded here but not decided by this record: trial results describe groups, not individuals (so no output may claim what *this* patient will gain), and patient-specific treatment support can be a regulated device (FDA, *Clinical Decision Support Software*, guidance reissued 29 January 2026). The current wording, "not for treatment selection", stays.

## Options

1. **Accept real patient records with consent and security controls.** The heaviest path: legal agreements, storage security, breach duties. Not for a pre-release research platform run by one person.
2. **Pseudonymise:** store the real values under a code name. Still personal health information; the name hides nothing.
3. **A banded profile, computed in the browser, never sent or stored.** The platform holds nothing about the person; the profile describes a group.
4. **Run inside a hospital**, under its governance. A later step that needs an institution as partner.

## Decision

Option 3, with four rules.

1. **The platform never receives it.** Profile calculations run in the user's browser. The profile is not sent to the server, not stored there, not logged, and not put in a URL (URLs are logged). A user who wants to keep a profile downloads it as a file to their own computer.
2. **A profile, not a record.** The form asks only for what trial eligibility and the models need, each in bands (below). It has no field for a name, a date, a place, a record or device number, or free text, and it rejects input that looks like one. This follows the identifiers the HIPAA Safe Harbor method removes (including dates other than the year and ages over 89), whether or not HIPAA applies to a given user.
3. **Results are about the profile.** Outputs read "for patients matching profile 2". Where a model needs an exact value (kidney function, weight), the result is shown across the whole band, lowest to highest, not as one number.
4. **A guard for rare combinations.** When a profile could point to few people, the form widens the bands and says so, instead of proceeding.

## First form (fine-tuning expected)

| Field | Bands |
|---|---|
| Age | 18–29, 30–39, … 80–89, 90 and over (adults only; no model on the platform is for children) |
| Sex | female, male (as used by the models' covariates) |
| Weight | 10 kg bands from 40 kg; 120 kg and over |
| Height | 10 cm bands (needed for body surface area) |
| Kidney function | the FDA renal guidance's Table 1 categories (March 2024): 90 and over, 60 to under 90, 30 to under 60, under 30 mL/min; dialysis as its own band |
| Liver function | Child–Pugh A, B, C, or NCI ODWG normal, mild, moderate, severe, as in the FDA hepatic draft guidance |
| Diagnosis | chosen from the platform's disease list, not typed |
| Line of therapy | 1, 2, 3, 4 or more |
| Current medicines | active ingredients from the drug catalogue; no doses or dates |
| Eligibility values | ECOG 0–4; neutrophils, platelets, haemoglobin, bilirubin and AST/ALT in bands set at the thresholds trials commonly use (to be fixed from the eligibility annotations before the form is built) |

**Rare-combination rule, first version:** the 90-and-over band is never combined with a diagnosis outside the platform's disease list or with a line of therapy above 3; if a profile would do so, age is shown as 80 and over. Further rules are added as amendments.

## What stays as it is

- The Patient Lab's existing saved scenarios are synthetic records the user invents; they stay server-side. Profile mode never saves to them.
- No output claims what a patient will gain from a treatment, and no model is shown beyond its checked limits (decision 0005; the locked checks).
- A privacy lawyer reviews this design before profiles built from real patients are invited. This record reduces risk; it does not decide which laws apply.

## Revisit when

The legal review asks for changes; a partner institution offers to run the platform under its own governance; or a feature needs a value finer than a band.

## Amendments

*(none yet)*
