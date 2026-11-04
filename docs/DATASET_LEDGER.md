# Dataset ledger: what each model has seen

Written 4 November 2026.

## Why

The platform's main safeguard is that checks follow plans locked before computation. A locked plan protects against tuning the analysis. It does not make a check blind if the data had already been read. Each plan records that on its own; nothing gave the overview. As a result, the platform was running out of unseen data without anyone being able to see it.

## What it is

`intelligence_store/data/dataset_ledger_v2.json`, pinned in `intelligence_store/dataset_ledger.py`. v1 is kept unchanged; v2 adds the five labels extracted on 4 November 2026 (Phase 3.2d) as seen datasets, with no uses yet.

- **Datasets** (26 in v2; 21 in v1): each with its sources, pinned files and `values_first_seen`, the date anyone working on the platform first read its values (null if never).
- **Uses** (42): for each model or tool, every dataset it was built from, tuned on, reproduced, or checked against, with the step, plan and report.
- **Roles:**

| Role | Meaning |
|---|---|
| `built_from` | The model's parameters come from this dataset |
| `tuned_on` | The platform set or fitted parameters on it |
| `reproduction` | Compared with the model's own fitting data, or the study its source compared it with |
| `checked_blind` | Plan locked before anyone on the platform saw the values |
| `checked_blind_with_deviation` | As above, with a recorded deviation |
| `checked_not_blind` | Plan locked, but the values had been seen before it was written |
| `compared_model_to_model` | Compared with another model, not observed data |
| `reserved_for_blind_check` | Set aside for a locked check not yet run |

## What it shows (4 November 2026)

- **Three datasets have given blind checks:** Bridoux 2016, for Hughes and Kim, with a deviation; the NEOFORDEX EPAR studies (dexamethasone label curve); and eligibility sample v1 (extractor v1). Every other outside check on the platform was planned after its data had been read, and its plan says so.
- **One dataset is unseen and reserved:** eligibility sample v2, for extractor v1.1. Its criteria text is read only by the annotator, the platform owner.
- **Every lenalidomide renal-impairment dataset available is seen:** CC-5013-PK-001, Bridoux 2016 and Kim 2026. Any further kidney-model check is not blind until new data is found (see Simulation 2.0d).
- The three datasets with no values (Hughes, Gupta and Luo fitting data) are the published models' own data, which the platform does not hold.

## The gate

- `assert_blind_allowed(model, dataset)` refuses a blind check when the dataset has been seen, or when the model was built from, tuned on or reproduced against it. It also refuses a dataset that is not yet in the ledger, so new data must be registered first.
- `validate_plan_datasets(plan)` applies the gate to a plan that declares `{"model", "datasets": [{"id", "role"}]}`. **Plans written from now on declare their datasets this way** and are validated before they are pinned.
- A test (`tests/test_dataset_ledger.py`) requires every check report in `docs/verification/` to appear in the ledger, so a new check cannot be added without recording its role. Another test confirms that every blind check's plan predates the dataset's first-seen date.

## Updating it

The ledger is pinned like any reference file. When a dataset is read, a check is run or a model is tuned, a new version records it (`dataset_ledger_v2.json`), with a new pin, never an edit in place.
