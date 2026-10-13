# Computational human direction — historical Step 26 proposal

> Historical design document. Versioned patient state, saved revisions and comparison workflows have since been implemented. This is not the current implementation checklist. See [the current roadmap](docs/PRODUCT_AND_SCIENCE_ROADMAP.md) and [repository checkpoint](docs/REPOSITORY_CHECKPOINT.md).

The central question remains: **What happens when this drug meets this biological system?**
Keep the existing Flask application, retained trial evidence, curated drug knowledge,
Patient Lab, saved reports and Workspace. Extend their contracts incrementally.
Deployment remains deferred until Astrid explicitly requests it.

## Next realistic version: Patient Lab 2.0, a versioned patient state

Its job is to describe a synthetic biological starting state that a future model
can consume. Describing a kidney state and modeling its effect on drug clearance
are separate scientific tasks. Recording additional inputs does not justify
changing the existing reference PK curve.

Build these small steps in order:

1. Audit the existing scenario profile, saved-payload schema and reference PK
   contract. Preserve old saved scenarios and exports without reinterpretation.
2. Add a pure patient-state validator and versioned schema. Begin with existing
   demographics plus body weight, height, a clearly identified renal-function
   measure, a small set of liver-related laboratory fields and their units.
   Record missing fields explicitly. Do not treat a missing result as normal.
3. Give each field an origin: synthetic input, assumption or derived value,
   along with units, synthetic observation time and optional source reference.
   Validate finite values and unit compatibility; broad plausibility checks are
   input checks, not declarations of health. Do not automatically substitute
   eGFR for creatinine clearance or infer normal hepatic function from one lab.
4. Add versioned patient-state snapshots linked to existing scenarios. Editing
   creates a new revision; old reports retain the state they actually used.
   Existing legacy records remain readable with their original schema version.
5. Extend the existing Patient Lab form with a compact physiological-state panel,
   explicit unknowns and a field-provenance view. Add an export showing which
   fields a model uses and which are merely recorded. Compare input states
   before comparing any modeled response.

Disease descriptors, biomarkers and pharmacogenomics can follow when a selected
model needs a precisely defined input. Medication history needs product, route,
dose, timing and uncertainty before it can support exposure simulation. Free-text
medication lists remain evidence context until those requirements are satisfied.

### Minimum architecture

| Component | Responsibility |
|---|---|
| Existing evidence and knowledge modules | Retain trial snapshots and versioned, source-backed curated drug context |
| Patient-state module | Normalize units, validate fields, preserve unknowns and derivation provenance |
| Versioned state storage | Link immutable state revisions to scenarios without rewriting previous payloads |
| Model registry | Declare supported drug/product/route, model version, inputs, units and validity domain |
| Parameter binding | Connect a specific state to supported model parameters; reject unsupported cases |
| Simulation runner | Produce deterministic results from captured inputs and parameters |
| Existing Workspace | Store result, state, model, parameter sources, assumptions and uncertainty together |
| Patient Lab UI | Show state, model availability, results and provenance with accessible tables/charts |

Initially implement only the state module, storage and UI. The model registry and
runner contracts can be documented before a new personalized model is added.
Suggested future endpoints under the existing Flask blueprint are a state
validation endpoint, revision creation/read endpoints and an explicit simulation
endpoint. These are proposals, not routes implemented by Step 26.

A future field representation might contain `value`, `unit`, `origin`,
`observed_at`, `source_ref` and `derivation_ref`. A null value means unknown;
its unit/origin can still be recorded. A future result must retain the complete
model input subset, ignored fields, model/version, parameter-set hash, solver
configuration, source references, assumptions and model applicability decision.
A hash supports reproducibility; it does not certify scientific correctness.

## What Patient Lab 2.0 explicitly does not attempt

No patient-specific efficacy, adverse-effect probability, survival prediction,
organ injury trajectory, treatment recommendation, genetic-response prediction,
or automatic renal/hepatic dose adjustment. No claim that trial inclusion or a
label warning establishes a simulated outcome. No whole-body physiology,
combination-therapy kinetics, PBPK organs or molecular animation driven by
unsupported equations. Preserve the current PK teaching demonstration as a
reference illustration until a separately validated covariate model is available.

## Scientific modules after the state foundation

| Phase | Smallest defensible deliverable | Evidence and validation needed |
|---|---|---|
| Current knowledge phase | Expand selected drug references and expose remaining gaps | Pinned label versions, curated section rationales, retained trial IDs; no numerical parameter inference |
| Patient Lab 2.0 | Versioned physiological starting state | Units, missingness, provenance, legacy compatibility and immutable revision tests |
| Personalized PK 1.0 | One drug, one formulation/route, one justified patient covariate relationship | Published model equations, parameter units, applicable population, independent reference curves and sensitivity checks |
| Compartment PK 2.0 | Add an extra compartment only when data require it; later simplified PBPK | Mass balance, tissue parameters, organ flows, identifiability and independent validation data |
| Mechanism and PD | One experimentally supported concentration-effect relationship | Target binding/effect data, an explicit endpoint, parameter uncertainty; a pathway diagram alone is insufficient |
| Integrated response | One validated biomarker or toxicity process linked to exposure | Longitudinal data, delayed effects where supported, external validation and calibrated uncertainty |
| Multi-organ/disease/combination models | Add one independently justified feedback or interaction at a time | Systems biology, interaction data and tests for feedback stability; do not extrapolate label interaction ratios as universal multipliers |
| Anatomical UI | Map existing validated outputs to body/organ views | Clearly distinguish measured inputs, calculated compartments and explanatory illustrations |
| Mechanistic + ML | Learn a specific unresolved component from suitable data | Separate training/validation populations, leakage controls, calibration and comparison with mechanistic baselines |

Published pharmacology supplies equations and parameter estimates. FDA labeling
and DailyMed product labels supply specific product/route/population context and
constraints, sometimes quantitative measurements; population averages alone do
not define an individual PK or PD model. Clinical trials supply study evidence;
registry counts do not train an individual-response model by themselves.
PBPK supplies anatomically motivated compartments when sufficient physiological
and drug-specific parameters exist. Systems biology belongs in later supported
pathway/feedback modules. ML and anatomical rendering do not repair missing
scientific support.

Validate software correctness and scientific performance separately. First check
units, conservation, solver convergence, reproducibility and rejected inputs.
Then check reference datasets, population applicability, external validation,
parameter uncertainty and sensitivity. Distinguish parameter uncertainty,
between-patient variability and model inadequacy; do not replace these with an
unsupported confidence score.

## Phase completion checkpoint

Before switching from this knowledge phase to patient-state implementation,
review curated coverage and remaining gaps, document source-selection rules,
confirm saved-report compatibility and run the platform checks against the real
local cohort. Agree on the one-drug scientific use case that future models will
serve. This checkpoint is independent of deployment.

Step 26 adds dexamethasone references only. It does not implement Patient Lab 2.0,
a new PK model or any of the future endpoints above.
