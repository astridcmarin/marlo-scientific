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

**Hughes 2019** (`lenalidomide_hughes_scope_v2.json`; v1 superseded on 31 October 2026). Covariates come from the Hughes estimator, with the declared weight basis.

| Creatinine clearance (C–G) | Tier | Evidence |
|---|---|---|
| 50–211 mL/min | checked | Normal and mild groups consistent in all 4 scenarios |
| 36–50 mL/min | **outside check disagrees** | Moderate group under-predicted about 2.1-fold in all 4 scenarios; observed group shown |
| < 36 or > 211 | refused | Beyond the model's data; moderate and severe observed groups shown below 36 |

Other rules:
- **Fat-free mass, age, weight, height and serum creatinine:** must be inside the model's data ranges.
- **Disease:** MM, CLL, AML or ALL. These are in the model's data. The outside study enrolled people with renal impairment due to non-malignant conditions and healthy controls, not cancer patients, so the outside check does not cover any disease and this rule stays "model data only".

**Kim 2026** (`lenalidomide_kim_scope_v3.json`; v1 and v2 superseded on 31 October 2026). Covariates are CKD-EPI 2021 eGFR and Du Bois BSA from the Kim estimator.

| eGFR (mL/min/1.73 m²) | Tier | Evidence |
|---|---|---|
| 50–94.7 | checked | Mild group's ratio consistent in all 7 scenarios |
| 30–50 | **outside check disagrees** | Moderate group under-predicted about 1.3-fold in the 2.1e recheck, all four scenarios (the first check had it consistent in the primary scenario only); observed group shown. Most of the group's constructed eGFR values were below 30, so this edge is approximate. |
| 11.1–30 | **outside check disagrees** | Severe group under-predicted about 1.3-fold (primary; confirmed in all four recheck scenarios); observed group shown |
| < 11.1 or > 94.7 | refused | Beyond the model's data. Above 94.7 Kim had no patients, so records with normal kidney function above that are refused for Kim (Hughes covers them). |

Other rules:
- **BSA, age, weight and height:** must be inside Kim's ranges.
- **Disease:** MM only. The outside study did not enrol myeloma patients (non-malignant renal impairment; healthy controls).
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

## Daratumumab and the public scope pages (Phase 2.5c)

**Daratumumab scope** (`daratumumab_scope_v1.json`). Written from both locked checks (3.2b, 3.2c). The platform does not compute daratumumab yet (`runtime: none`); the scope fixes what a future implementation may compute and how it must be labelled.

| Output | Tier | Why |
|---|---|---|
| Peak after the first IV infusion, 8 or 16 mg/kg | checked | Consistent in all 8 scenarios of both checks |
| AUC to infinity after 8 mg/kg | model data only | Consistent in v1, but not in every v2 scenario |
| First-week AUC after 16 mg/kg | **outside check disagrees** | Over-predicted in every scenario of both checks (0.87, 0.83) |
| Troughs and peaks over the labelled schedule | model data only | Not classified; descriptively about 1.26× the model in SIRIUS |

**Rules:**
- **Disease:** MM.
- **Route:** IV is checked against outside data; subcutaneous dosing is model data only. Category rules can now carry a tier per value (`tier_by_value`).
- **Weight and albumin:** must be inside the model's data.

**Pages:**
- **`/models/<model_id>/scope`**, with a JSON download, for every registered scope. The registry is `intelligence_store/scope_registry.py`; each entry uses its scope file's pinned loader.
- **Links.** The models index lists all four scopes. Scorecards and credibility records link to the scope when one exists. Ixazomib and daratumumab have scopes but no scorecard or credibility record yet, because they are not in the evidence status file or the credibility context.

## Bortezomib platelet model (Phase 2.5d, 31 October 2026)

**Why.** The bortezomib platelet curve was the only computed model with no scope. It ran for any baseline, with a warning below the source study's entry thresholds, although the 30 October policy is to refuse beyond the model's data. Its driving PK component disagrees with outside concentration data, and that was stated only in a limitation line.

**Scope** (`bortezomib_platelets_scope_v1.json`, pinned in `bortezomib_patient_platelets.py`):

| Baseline platelets (×10⁹/L) | Tier | Note |
|---|---|---|
| 50 or more | model data only | At or above the source's usual entry threshold |
| 30–50 | model data only | Admitted in the source only with extensive marrow involvement (transfusion allowed) |
| below 30 | **refused** | Below every entry threshold; the model has no data from such patients |

- **No upper limit.** The source states none, and none is invented. The scope engine now accepts an open range end (`null`; evaluation v1.1). Existing scopes evaluate exactly as before.
- **Tier of the curve: model data only.** It is reproduced against its fitting data (Lonial 2005), and no outside platelet data exist. It is not tier "outside check disagrees": the outside checks tested the PK component's concentrations, not platelet counts.
- **Inherited caveat, shown on the scope page.** The PK component disagrees with outside data: first-dose exposure is 2–3-fold too high in Ogawa 2008 and Reece 2011 and consistent in CAN-1004, and the rise over repeated doses is too small in every study that sampled both days. The platelet parameters were fitted with this same PK, so the curve can still match its fitting data; transfer to other regimens is what the disagreement undermines. Only the studied regimen is run.
- **Not supported:** individual counts, grade or risk; other doses, schedules, holds or subcutaneous dosing; patient bortezomib concentrations.
- **Population stated, not enforced.** The model was fitted on relapsed or refractory myeloma (SUMMIT, CREST). The page has no disease input, so the scope states the population rather than enforcing it.

**Behaviour change.** A baseline below 30 ×10⁹/L now gives "Outside the model's scope" with the scope panel, and no curve. Before, a curve was drawn with a warning. Baselines of 30–50 still draw a curve, with the existing warning and the band note.

**Corrected text.** The platelet tool's limitation and the drug-capability assumption said the PK model "overstates first-dose exposure about 7-fold". That figure is the ratio of the label's first-dose clearance to the model's clearance, not measured exposure. Against measured exposure, first-dose AUC is 2–3-fold too high in two studies and consistent in a third. Both texts now say so. The locked platelet check plan keeps its original wording, as a record.

## Next

- ~~Move the Hughes and Kim per-model versions to this format~~: done in 2.5b. The coverage contract and applicability findings remain as the evidence the scopes cite.
- ~~Write daratumumab's scope~~: done in 2.5c.
- ~~Show each model's scope on its scorecard and credibility record~~: done in 2.5c (linked pages).
- ~~Add ixazomib and daratumumab to the evidence status file and the credibility context~~: done in 6.1b (evidence status v7, credibility context v2).
- **Add ixazomib to the curated drug catalog** (a new versioned catalog file), so the drug library lists it with its capability level.
