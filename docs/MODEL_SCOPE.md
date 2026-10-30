# Phase 2.5 — Enforceable model scope (context of use as rules)

A published model can be right for some patients and outputs and wrong for others. The four locked outside checks so far (Hughes, Kim, ixazomib, daratumumab) all show this. A model scope makes that explicit and enforced. It records, for one model:
- which outputs the platform will compute, and which it will not;
- for which synthetic patients;
- what is shown instead outside that domain;
- the pinned source or locked report that justifies each rule.

This is the ICH M15 *context of use* turned from a description into something the code applies.

## Format (`model-scope-v1`)

A pinned JSON file per model, read by `intelligence_store/model_scope.py`:

| Part | Content |
|---|---|
| `evidence` | Checksums of the files the rules rely on (model extract, observed data, locked check report) |
| `outputs.supported` | Each with an evidence tier |
| `outputs.not_supported` | Each with the reason |
| `request_rules` | Disease, route and dose: `category` or `range` |
| `state_rules` | Patient-state fields: `range` (optionally with evidence tiers by band), `ratio_max` (value ÷ a laboratory reference such as the ULN), or a derived value (BSA, Du Bois) |
| `never_claimed` | What no output of this model means |

**Evidence tiers:**
- `externally_checked`: inside a locked outside check that was consistent and robust.
- `inside_model_data`: inside the data the model was built on, not checked against outside data here.

An in-scope result reports the weakest tier among the rules that admitted it.

**Overall status:**
- `in_scope`: every rule passes, so the supported outputs are computed.
- `out_of_scope`: any rule fails. No model value is computed; observed study data are shown where a rule names them.
- `cannot_determine`: no rule fails but an input is unknown. No model value is computed.

Unknown inputs are never filled in. A unit that differs from the rule's is an error, never converted.

## First model: ixazomib (`ixazomib_scope_v1.json`)

Written from the locked check `docs/verification/ixazomib_pk_gupta_check_v1.json` (Simulation 3.2a) and the pinned extracts. No new computation.

| Rule | In scope | Tier | Outside |
|---|---|---|---|
| Disease | Multiple myeloma | checked | Solid tumours: model under-predicts AUC about 1.4-fold (robust). Others not checked. |
| Route, dose | Oral, 1.5–4 mg | checked | Outside the checked doses |
| Creatinine clearance (C–G) | 90–297 mL/min | checked | — |
| | 30–90 mL/min | model data only | < 30: refused; renal-study observed groups shown (AUC ratio 1.41 severe RI, 1.36 ESRD) |
| Total bilirubin | ≤ 1.5 × ULN (ULN given with the request) | model data only | Moderate or severe hepatic impairment: refused; hepatic-study observed groups shown |
| BSA (Du Bois, assumed formula) | 1.23–2.67 m² | model data only | Refused |
| Age | 23–91 years | model data only | Refused |

**Supported outputs:**
- **Typical total AUC from 0 to 336 h after one dose.** Tier: externally checked. The renal study's normal group was 575 observed vs 596 model median.
- **Typical total AUC over a dosing interval at steady state** (F × dose / CL). Tier: model data only.

**Not supported:**
- **Peak concentration.** Under-predicted 2–4×.
- **Concentration-time curves.** They would show the peak.
- **Unbound exposure.** The model gives total concentrations only.
- **Anything individual.** Outputs are typical values for a record's body size.

**Interacting drugs are not assessed.** The synthetic state has no medication list, and strong CYP3A inducers lower exposure per the label. The page says so.

## Where it is used

- **Function:** `intelligence_store/ixazomib_exposure.py`. It validates the state, evaluates the scope, then either computes or returns the observed groups. The result is hashed.
- **Command line:** `flask --app app/app.py ixazomib-exposure --state-file … --request-file …`
- **Page:** `/landscape/patient-lab/ixazomib-exposure`. A form for the synthetic record; the rule table with the reason for each rule; the outputs or the observed groups; the list of what is not computed; a JSON download with checksums.

## Lenalidomide: Hughes 2019 and Kim 2026 (Phase 2.5b)

**Policy, chosen by the platform owner on 30 October 2026:**
- **Where the model was fitted on such patients but a locked outside check found it inconsistent:** compute, flag, and show the observed data. This keeps the 14 October decision that Kim's results in severe renal impairment are calculated and warned, not hidden.
- **Beyond the model's own data:** refuse.

This adds a third tier, `external_check_disagrees`. It is in scope but flagged, and its band names the observed groups to show.

The bands follow each locked check's **primary** result (the exposure ratio to normal renal function), as the 14 October Kim finding did. Secondary results are described in the band notes but do not set tiers.

**Hughes 2019** (`lenalidomide_hughes_scope_v1.json`). Covariates come from the Hughes estimator, with the declared weight basis.

| Creatinine clearance (C–G) | Tier | Evidence |
|---|---|---|
| 50–211 mL/min | checked | Normal and mild groups consistent in all 4 scenarios |
| 36–50 mL/min | **outside check disagrees** | Moderate group under-predicted about 2.1-fold in all 4 scenarios; observed group shown |
| < 36 or > 211 | refused | Beyond the model's data; moderate and severe observed groups shown below 36 |

Other rules:
- **Fat-free mass, age, weight, height and serum creatinine:** must be inside the model's data ranges.
- **Disease:** MM, CLL, AML or ALL. These are in the model's data; the outside study's disease context is unknown, so this rule is "model data only".

**Kim 2026** (`lenalidomide_kim_scope_v1.json`). Covariates are CKD-EPI 2021 eGFR and Du Bois BSA from the Kim estimator.

| eGFR (mL/min/1.73 m²) | Tier | Evidence |
|---|---|---|
| 50–94.7 | checked | Mild group's ratio consistent in all 7 scenarios |
| 30–50 | model data only | Moderate group consistent in the primary scenario only; absolute exposure about 1.3-fold low in 6 of 7 (secondary) |
| 11.1–30 | **outside check disagrees** | Severe group under-predicted about 1.3-fold (primary); observed group shown |
| < 11.1 or > 94.7 | refused | Beyond the model's data. Above 94.7 Kim had no patients, so records with normal kidney function above that are refused for Kim (Hughes covers them). |

Other rules:
- **BSA, age, weight and height:** must be inside Kim's ranges.
- **Disease:** MM only.
- **Albumin:** an optional rule (30–52 g/L). If unknown, it is not assessed.

Doses and schedules are still checked by each model's existing execution blockers.

**Where the scope applies:**
- **`calculate_estimated_pk` (Hughes).** Used by calculate, save, the weight-basis comparison and the population band. Out of scope means status `outside_model_scope` and nothing is run.
- **`calculate_kim_pk`.** Used by save and the model comparison. Out of scope adds an `outside_model_scope` execution blocker.
- **Pages.** Every new report carries the scope result, shown with the shared `_model_scope.html` panel on the estimated-PK page (calculation and model comparison) and on saved Kim runs.
- **Saved Kim runs from before the scope.** They are frozen. The page evaluates the current scope for display and says so; the archived run is not changed.

**Behaviour changes:**
- **Hughes:** records outside its reported ranges (including creatinine clearance below 36 mL/min) were already blocked inside the calculation (`outside_context_range`). They are now refused by the scope first (`outside_model_scope`), with the reason for each rule and, below 36 mL/min, the observed groups.
- **Kim:** records outside its Table 1 ranges (eGFR, BSA, age, weight, height) previously ran with an "extrapolation" warning. They are now refused.
- **Both:** severe renal impairment for Kim and the moderate band for Hughes still run, now flagged with the observed data.

## Next

- ~~Move the Hughes and Kim per-model versions to this format~~: done in 2.5b. The coverage contract and applicability findings remain as the evidence the scopes cite.
- **Write daratumumab's scope** from 3.2b–3.2c. Candidates: peaks at 8 and 16 mg/kg; AUC at 8 mg/kg as model data only, given the opposite-direction misses.
- **Show each model's scope** on its scorecard and credibility record (PR #69).
