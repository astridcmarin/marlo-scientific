# Phase 4.2 — Special-population evidence summaries (design plan)

Written 30 October 2026, before any summary is built.

## Purpose

For each drug, show in one place what is known about exposure in special populations. This is the question a clinical pharmacology reviewer, a trial designer writing eligibility criteria, or a regulatory professional asks first: what happens to exposure with kidney or liver impairment, with age, and with body size, and what does the label do about it?

The layout follows the "intrinsic factors" part of an FDA clinical pharmacology review. It is a research reference, not dosing guidance.

## Structure of a summary

One summary per drug. Rows are **domains**:

| Domain | Typical content |
|---|---|
| Kidney function | Dedicated renal study or label statement; exposure change by group; dialysis; label action |
| Liver function | Dedicated hepatic study or label statement; categories used (NCI-ODWG, Child-Pugh); label action |
| Age | Covariate tested or retained in a population model; label geriatric statement |
| Body size | Weight or BSA effects; fixed versus body-size dosing |
| Sex, race and other covariates | Tested and not retained, or retained with effect size |

Each row holds **statements**. Each statement is one of:

| Kind | Meaning |
|---|---|
| `study_exposure_change` | An observed exposure ratio or group values from a named study (n, statistic, interval when given) |
| `label_statement` | What the label says about the population, quoted, with its section |
| `label_action` | The label's dose modification or avoidance for the population |
| `covariate_effect` | An effect retained in a published population model (form and size) |
| `covariate_not_retained` | Tested in a population model and not retained (with the tested range) |
| `not_studied` | The source states the population was not studied |
| `platform_model_scope` | How the platform's own model handles the population (scope tier), linking to the scope page |
| `gap` | Nothing in the platform's pinned sources; shown as such |

## Rules

1. **Every value resolves to a pinned file.** A statement stores its value and a pointer (file and JSON path) into a pinned extract. The builder resolves the pointer, and a test fails if the stored value differs from the source. No value is typed in by hand without its source.
2. **Study, label and model findings are kept apart.** Observed study results, label wording and model covariates are different kinds of evidence and are labelled as such. Study populations are named (myeloma, solid tumours, healthy subjects, not stated).
3. **Unknown stays unknown.** A domain with no pinned source shows `gap`, not a guess or remembered value. Filling a gap means a new pinned extract, page-checked, with its own review status.
4. **No recommendations.** The platform quotes label actions; it does not propose doses.
5. **Extraction status shown.** Each source shows whether its extraction is AI-assisted or independently reviewed.

## Data model

- `intelligence_store/data/special_populations_<drug>_v1.json` (pinned): the drug's rows and statements, each with `value` and `source` (`file`, `pointer`, `location` in the original document).
- `intelligence_store/special_populations.py`: loads a summary, resolves every pointer against the pinned file (checking that file's checksum against the platform's own pin), and refuses to render a summary whose values do not match.
- Page: `/landscape/drugs/<drug>/special-populations`, with a JSON download. It is linked from the drug library and from the drug's model pages.

## Order of work

1. **Ixazomib** (dedicated renal and hepatic studies, population model covariates, scope).
2. **Pomalidomide** (label renal and hepatic folds and actions; Li 2017 covariates).
3. **Lenalidomide** (CC-5013-PK-001 groups, dialysis evidence, Hughes and Kim covariates and scopes). The hepatic domain is a gap until a source is pinned.
4. **Daratumumab** (Luo covariates; renal and hepatic tested and not retained).
5. **Dexamethasone** (label: renal and hepatic not studied; NEOFORDEX patient exposure).
6. **Bortezomib**: new extractions needed (label hepatic action; the FDA and EMA review documents already held).

Gaps found along the way are listed in each summary and in this document.

## Not in scope

Drug interactions and food (extrinsic factors) are not part of the summary schema. For lenalidomide only, since 5 November 2026, the page also quotes the label's section 12.3 (absorption and food, distribution, elimination, haemodialysis, interaction studies, transporters) and section 7 (interactions) in a separate section below the five domains (`lenalidomide_label_2023_pk_v1.json`, `lenalidomide_label.label_pk_view`; not yet reviewed by the owner). Pregnancy, lactation and paediatrics are not covered: the myeloma drugs here have no paediatric indication, and their reproductive risks belong to the safety catalog.

## Status

| Drug | Summary | Gaps |
|---|---|---|
| Ixazomib | Built 30 October 2026 (`special_populations_ixazomib_v1.json`); **v2 on 31 October 2026** (`special_populations_ixazomib_v2.json`) adds the NINLARO label, revision 7/2024 (`ixazomib_label_2024_v1.json`; every quoted statement is identical in the 11/2015 label at first approval). The label's own 3 mg starting-dose actions and AUC increases (39% severe renal or ESRD, 20% moderate or severe hepatic) replace the actions previously quoted from the study articles, and the label's age, sex, race and BSA statements are added. v1 is kept unchanged. **v3 on 31 October 2026** (`special_populations_lenalidomide_v3.json`) records that the renal study enrolled people with non-malignant renal impairment and healthy controls, and moves to renal evidence v2, Hughes scope v2 and Kim scope v3 (moderate eGFR band flagged). v2 is kept unchanged. | Revisions after 7/2024 are not reviewed. |
| Pomalidomide | Built 30 October 2026 (`special_populations_pomalidomide_v1.json`) | Age, body size, sex and race (label sections 8.5 and 12.3 not extracted for these) |
| Lenalidomide | Built 30 October 2026 (`special_populations_lenalidomide_v1.json`); **v2 on 31 October 2026** (`special_populations_lenalidomide_v2.json`) adds the REVLIMID label, revision 3/2023 (`lenalidomide_label_2023_v1.json`): Table 3 renal dose adjustments, mild hepatic impairment, moderate and severe hepatic impairment not studied, and age, weight, sex and race not clinically relevant to clearance. v1 is kept unchanged. **v3 on 31 October 2026** (`special_populations_lenalidomide_v3.json`) records that the renal study enrolled people with non-malignant renal impairment and healthy controls, and moves to renal evidence v2, Hughes scope v2 and Kim scope v3 (moderate eGFR band flagged). v2 is kept unchanged. | None in the five domains. Two source differences are recorded, not resolved: the label's first renal dose step is 30–60 mL/min, against 50 mL/min in the earlier secondary source; and the label lists 3 healthy subjects in the renal study, against n = 7 in the EMA table used as the reference. |
| Daratumumab | Built 30 October 2026 (`special_populations_daratumumab_v1.json`) | Age; label statements (renal and hepatic are from the population model only) |
| Dexamethasone | Built 30 October 2026 (`special_populations_dexamethasone_v1.json`) | Age, body size; the label states renal and hepatic impairment were not studied |
| Bortezomib | Built 30 October 2026 (`special_populations_bortezomib_v1.json`), from a new extract of the 2012 VELCADE label (`bortezomib_label_special_populations_2012_v1.json`), transcribed from the scanned label pages | Body size; later label revisions not reviewed |

**Kidney-function classifications compared (lenalidomide, 5 November 2026; reviewer's checklist R1 and R2).** Below the kidney row, the lenalidomide page sets three classifications side by side: the FDA 2024 renal-impairment guidance's Table 1 (`fda_renal_impairment_guidance_2024_v1.json`, new), CC-5013-PK-001's groups (the body map's bands) and the label's Table 3 dose rows. It shows which ranges share values, marking ranges that share only a boundary value (FDA mild and the label's 30–60 row share only 60 mL/min). It then states each source's measure of kidney function: measured 24-hour creatinine clearance (the study), Cockcroft–Gault (the label, Bridoux 2016, and Hughes 2019 with its weight basis unresolved) and CKD-EPI 2021 eGFR indexed to 1.73 m² (Kim 2026, unlike the guidance's preferred mL/min). Every bound and statement is read by pointer from a pinned file (`kidney_function_classifications.py`); the platform-written notes are labelled as such. The body map's observed-data panel shows where the chosen value falls in each classification. The guidance values were extracted with AI assistance from the FDA's PDF and are not yet reviewed by the owner (round 3). Overlapping ranges are not the same people, because the measures differ; nothing classifies a patient or proposes a dose.

**Label kidney doses and exposure (lenalidomide, 5 November 2026; reviewer's checklist R9).** Below the classifications, the page asks whether each label kidney row's reduced dose brings exposure back to the reference, from three pinned sources (`renal_dose_exposure.py`): Bridoux 2016, myeloma patients observed on those doses (day 5 AUC24 ratio to normal: moderate 1.03, severe 1.33, dialysis 1.16; the mild group on 25 mg, 1.49); CC-5013-PK-001's single 25 mg dose ratios (EMA 2013 Table 4) scaled to the label's average daily dose by dose proportionality, which the label states (1.04, 1.06, 0.95, with scaled 90% intervals); and the sponsor's steady-state simulation (EMA 2013 Table 7: 1.05 for both severe regimens). The scaling is the platform's arithmetic and is labelled as derived; the sponsor's table is labelled as a model prediction. The sources differ in population, reference group and kidney-function measure, and Bridoux's first reduction was at 50 mL/min rather than the US label's 60. No threshold for "restores" is set and no dose is proposed.

**Liver-function classifications (lenalidomide, 5 November 2026; reviewer's checklist H2).** Below the liver row, the page sets the FDA September 2026 draft hepatic guidance (`fda_hepatic_impairment_guidance_2026_draft_v1.json`, docket FDA-2026-D-8693) beside the label: NCI ODWG groups A–D by bilirubin and AST, which the guidance allows in cancer, and Child–Pugh A–C, which it recommends in cirrhosis. The label's mild definition is NCI group B (B1 or B2); its "moderate to severe", with no data, is read as C and D. Both readings are labelled platform notes. The guidance tables came back from the text layer flattened, so their reading is marked as the assistant's (Child–Pugh points per column assumed). Not yet reviewed by the owner (round 3).

**Dialysis (lenalidomide, 6 November 2026; reviewer's checklist R7).** Below the dose-and-exposure table, the page gathers what is known in dialysis (`dialysis_evidence.py`): the label's dialysis dose; CC-5013-PK-001's same six end-stage subjects dosed on a non-dialysis day and 3 hours before a 4-hour haemodialysis (paired means, with on/off ratios marked as derived); the dialysis clearance and fraction removed per session (EMA 2013, label); and Bridoux's myeloma patients on the label's dialysis dose. Dialysis is not modelled, and the page says so.

**Assays behind the kidney data (lenalidomide, 6 November 2026; reviewer's checklist O8).** The page quotes how each kidney-function dataset's concentrations were measured (`lenalidomide_bioanalytical_methods_v1.json`, loaded by `lenalidomide_label.load_bioanalytical_methods`): CC-5013-PK-001 and Kim 2026 report their validation figures; Bridoux 2016 and Hughes 2019 cite earlier methods and give none. Twelve quotes, each matched by script against the source PDF on the owner's computer; added to review round 3 (queue v3, 117 entries).

Pages: `/landscape/drugs/<drug>/special-populations` for all six drugs: ixazomib, pomalidomide, lenalidomide, daratumumab, dexamethasone and bortezomib. Statements may carry a display hint (`mean_sd`, `gm_cv`, `range`, `ratio_ci`, `bands`) that changes only how a value is shown. The drug and model library links each drug that has a summary; ixazomib is not in the curated catalog, so its exposure page links its summary instead.
