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

## Next

- **Move the existing per-model versions to this format.** These are the Hughes coverage contract and the Kim applicability findings.
- **Write daratumumab's scope** from 3.2b–3.2c. Candidates: peaks at 8 and 16 mg/kg; AUC at 8 mg/kg as model data only, given the opposite-direction misses.
- **Show each model's scope** on its scorecard and credibility record (PR #69).
