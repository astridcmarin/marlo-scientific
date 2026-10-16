# Product and scientific development direction

Product direction recorded 10 October 2026. Owner: Astrid. Repository checkpoint updated 13 October 2026: Step 109 plus the separate observation-intake workflow.

## Product goal

A subscription research platform for individual researchers and pharmaceutical scientists. Users return to investigate diseases and drugs, compare evidence, build synthetic or hypothetical biological profiles, explore supported medication responses, and retain their investigations.

Broad disease coverage, a substantial medication library, and exposure/efficacy/toxicity simulation are essential to the intended release. The owner is not rushing to launch. A restricted disease pilot can support development but does not replace the broad product goal. No launch deadline or deployment authorization is implied.

## Existing foundation

The platform has frozen trial cohorts, drug reference catalogs, saved research work, immutable synthetic patient revisions, educational lenalidomide PK archives, comparison reports, generic exposure/binding/turnover experiments, and a published renal PK group reference. Cohort 4 includes 4037 retained Multiple Myeloma studies according to the user's local reports. The current identity catalog has nine curated entities. This is a seed, not broad coverage.

The existing lenalidomide model is a deterministic educational implementation. Generic Simulation Lab models do not establish drug-specific pharmacodynamics. Efficacy and toxicity prediction models are not yet registered. Software checks do not establish independent scientific review, source reproduction, predictive validity or individual applicability.

## Development phases

| Phase | Concrete work | Completion evidence |
|---|---|---|
| 1. Explicit capability library | Connect each curated drug with reference coverage, model endpoints, source populations, inputs, versions and gaps. | Searchable inventory accurately reflects installed assets and withholds unavailable entries. Step 101 supplies the first view; Step 109 adds source-checked research-tool discovery. |
| 2. Broader disease and drug evidence | Extend curated identities and disease associations; preserve formulations, components and regimens distinctly; expand source review and trial cohorts. | Reviewed source-linked entries, documented coverage and reproducible counts. No disease indication inferred from an alias or trial condition alone. |
| 3. Drug-specific exposure models | Add suitable published PK models and formulation/route boundaries. Establish mathematical verification, independent transcription review and observed-data evaluation. | Reproducible equations, parameters and comparison results, with population and uncertainty limits. |
| 4. Efficacy and toxicity endpoints | Select quantitative exposure-response or mechanistic models with suitable measurements. Implement each endpoint under its evidence-supported scope. | Observed endpoint reproduction/evaluation and documented assumptions; no efficacy or risk inferred solely from binding, a warning or a trial count. |
| 5. Biological profile integration | Link compatible patient state, treatment requests, PK and endpoint models. Track uncertainties and applicability across the complete chain. | End-to-end verification and empirical evaluation against relevant profiles; unsupported inputs remain explicit. |
| 6. Broad research workflows | Scale the library across diseases and medications; improve comparison, visualization, saved investigations and repeat use. | Representative scientists can complete the intended workflow and understand each model's limitations. |
| 7. Subscription and operational preparation | Accounts, private workspaces, entitlements, billing, backup, monitoring, source maintenance and support. Review privacy, security and intended use. | Operational testing and user-authorized controlled release. Deployment remains deferred. |

These phases overlap where useful. Scientific model coverage expands drug by drug and endpoint by endpoint. The number of catalog entries alone does not measure readiness.

## Capability representation

Every drug may have identity, mechanism, safety and interaction references while lacking one or more simulation models. The library records those independently. Each new model requires:

- Drug/component identity, formulation, route, treatment schedule and represented disease context.
- Endpoint definition: plasma exposure, a named biomarker, a specified efficacy endpoint or a specified toxicity endpoint.
- Equations, inputs, parameter units, source locations and version bindings.
- Population, dose and sampling coverage; exclusions and extrapolation limits.
- Mathematical verification, source review, empirical evaluation and uncertainty treatment.
- A precise description of what the output supports for a synthetic or hypothetical profile.

A group mean is not an individual observation. Marginal covariate ranges do not establish joint coverage. A generic biological demonstration cannot be relabeled as a researched drug model. Evidence currency and validation state must stay visible.

## Current checkpoint and next work

See the [repository checkpoint of 16 October 2026](REPOSITORY_CHECKPOINT.md). Since the 13 October checkpoint:
- **Lenalidomide:** a second exposure model (Kim 2026, renal impairment).
- **Bortezomib:** an exposure engine and the first drug-effect module (Lignet 2022 platelet model, checked against its fitting data).
- **Patient Lab:** the platelet curve in a patient's own counts, and a run record that states the evidence behind every result.

No efficacy or toxicity model is registered, and no model is validated for clinical prediction.

The library inventory now counts two lenalidomide exposure models, the bortezomib PK component and the platelet tool (inventory v1.2). Earlier step-number history, including the reused numbers 106–108 for **observation intake v1**, is in the [13 October checkpoint](history/REPOSITORY_CHECKPOINT_2026-10-13.md).

**Next work:**
1. Simulation 2.0 (2.0a–2.0c) and 4.0a–4.0b are done. Next candidates: a body → organ navigation layer linking the existing organ views, or (for bortezomib) a PK model with time-dependent clearance.
2. Strengthen 4.0a (reconcile the 2.97 and 3.34 odds ratios; carry exposure uncertainty).
3. For bortezomib, a published PK model with time-dependent clearance.

Preserve the distinction between software verification and empirical or independent scientific validation.
