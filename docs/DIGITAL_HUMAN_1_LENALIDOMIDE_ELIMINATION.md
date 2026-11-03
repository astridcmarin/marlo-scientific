# Digital human 1.0 — lenalidomide elimination body map (design plan)

Written 31 October 2026. Status: **approved by the platform owner on 31 October 2026**, with the three recommended decisions (see the end of this plan).

## The question it answers

*Where does lenalidomide leave the body, and how does that change as kidney function falls?*

This is the first piece of the computational-human interface: a whole-body view with an organ zoom, driven by a model the platform has already checked. It is deliberately small. It shows elimination routes, not concentrations in organs.

## Why lenalidomide, and why elimination first

- **The physiology is simple and well documented.** About 85% of a dose leaves unchanged in urine. Lenalidomide is not metabolised by cytochrome P450, and renal clearance exceeds filtration, so the tubules also secrete it (`SIMULATION_2_RENAL_PATHWAYS.md`).
- **The model already exists and has been checked.** The Simulation 2.0a pathway model splits clearance into filtration, tubular secretion and non-renal routes. A locked check against CC-5013-PK-001 is on record, including where it fails.
- **The evidence is richer than for any other drug on the platform.** It includes:
  - two extracts of the renal study (EMA 2008 arithmetic means; EMA 2013 geometric means, ratios with 90% CIs, renal clearance and regressions on measured creatinine clearance);
  - two population models with enforced scopes;
  - the label's dose steps.
- **It needs no tissue concentrations.** Elimination routes can be shown honestly from clearance data. Concentrations in organs cannot (see "What it does not do").

## What it shows (v1)

**1. Whole-body view.** An original schematic body, not an anatomical model:
- dose in (gut) → plasma → three exits: **kidney filtration**, **kidney tubular secretion**, **non-renal**;
- arrow widths proportional to each route's clearance (mL/min), on a fixed scale, so two patients can be compared;
- labels with each route's share of elimination and the percentage of the dose leaving unchanged in urine.

**2. Kidney zoom.** Glomerulus (filtration = unbound fraction × creatinine clearance) and tubule (secretion), with numbers and a one-line explanation of each process.

**3. Two modes:**
- **Explorer:** a creatinine-clearance control from 10 to 140 mL/min, with no patient record. For educators and trial designers.
- **Patient record:** creatinine clearance estimated from a saved synthetic record (Cockcroft–Gault, with the documented weight-basis assumption), as on the existing renal-pathways page.

**4. Exposure context beside the map.** Typical exposure relative to normal kidney function from the pathway model, next to:
- the observed group values from CC-5013-PK-001, as arithmetic means and as the EMA 2013 geometric-mean ratios with 90% CIs;
- the label's dose steps, quoted, not recommended.

**5. Evidence on every number.** Each route and band carries its evidence status:

| Creatinine clearance | Status shown | Basis |
|---|---|---|
| Normal (calibration) | calibrated | 2.0a: fitted to the normal group |
| Mild | checked, consistent | 2.0a primary scenario |
| Moderate | **outside check disagrees**: renal elimination probably lower than shown | 2.0a: reading A under-predicts exposure (0.79 of observed) and over-predicts the urine fraction (67% vs 42%) |
| Severe (no dialysis) | consistent in the primary scenario only | 2.0a scenarios |
| Below 10 or above 140 | not drawn | outside the calibrated range |
| Dialysis | not drawn in v1 | 2.0c covers it separately |

**6. Provenance.** The shared simulation banner and a run record listing the model version, the evidence files and checksums, the assumptions and the inputs.

## What it does not do, and why

- **No drug concentrations in organs or tissues.** No source gives lenalidomide tissue partitioning or organ volumes; drawing organ concentrations would mean inventing them. The arrows are clearance flows, not amounts sitting in an organ.
- **No PBPK model.** Same reason (see `SIMULATION_2_RENAL_PATHWAYS.md`).
- **No animated time course in v1.** A plasma curve from Hughes or Kim could be added later, under their own scopes. Mixing models into one animation now would blur which model each number comes from.
- **No mechanism or target zoom in v1.** The cell and molecular level (cereblon and the degradation of IKZF1/3) belongs to the knowledge layer. A static, sourced "where it acts" card could come later; it is not a simulation.
- **No liver impairment, drug interactions, dialysis, dosing advice or individual prediction.** The label has no PK data for moderate or severe liver impairment. No interaction model is established. Outputs are typical values for a synthetic record.
- **No 3D anatomy.** A clear 2D schematic is more honest for what the model knows, and it can be swapped for a richer graphic later without changing the data.

## Scientific issues to settle before building

1. **The unbound fraction changes the drawn split, not the exposure.**
   - **The issue.** The pathway model uses fu = 0.77, from in vitro binding of 23%. But ex vivo binding measured in the renal study's own subjects was about 40% (fu ≈ 0.60; EMA 2013, page 20), and Kim estimated 0.614.
   - **What it changes.** Under reading A, total renal clearance at any creatinine clearance does not depend on fu, so exposure is unaffected; only the filtration/secretion split moves. At normal function the split is filtration 85 / secretion 78 mL/min with fu 0.77, and about 66 / 96 with fu 0.60.
   - **Proposal.** Draw the split with both values: a band, or the primary value with the alternative in the label. Record the reason. No locked check needs re-running, because exposure is unchanged. **Decision for the owner.**

2. **Moderate impairment.** The map must not look more certain than the check. In the moderate band, the renal arrows carry the flag "probably lower than shown", and the observed group value is shown next to the model's.

3. **A consistency observation, not a test, so no claim.** The EMA 2013 regression (renal clearance = −17.4 + 1.89 × measured creatinine clearance) is steeper than reading A's proportional scaling (about 1.47 × creatinine clearance, from 162 mL/min at an assumed 110). That fits the 2.0a finding that renal elimination falls faster than in proportion. The regression uses the same subjects as the calibration, so it is not independent. The page can show it as context, labelled as such.

4. **Creatinine clearance stands in for GFR and overestimates it.** This is stated on the page, as it already is on the 2.0b page.

## Architecture (reuses what exists)

- **No new model.** The view calls the existing `patient_renal_pathways` and `lenalidomide_renal_pathways` functions, so the numbers on the map are exactly those of the 2.0b page (tested).
- **A new view module, `body_map.py`**, producing `body-map-view-v1` JSON:
  - `nodes`: compartments and organs, each with an id, a label and an optional UBERON anatomy ID (for example kidney UBERON:0002113), so later drugs and organs reuse the same vocabulary;
  - `flows`: from, to, clearance in mL/min, share, evidence status, and a pointer to the source or report behind it;
  - `context`: observed values, label steps and the run record.
- **Drawing:** server-rendered SVG, like the existing pages: original artwork, no external graphics, no JavaScript framework. The explorer uses a plain form control.
- **Routes:**
  - `/landscape/patient-lab/body-map?crcl=…` (explorer);
  - `…/patient-state/revisions/<id>/body-map` (record);
  - `?format=json` on both.
- **Generic by design.** The view takes a drug's flows and nodes as data, so a second drug only needs its own flow model, not a new page.

## Validation strategy

- **Software:**
  - flows sum to total clearance, and shares sum to 100%;
  - routes fall monotonically as creatinine clearance falls;
  - numbers match the 2.0b page exactly;
  - each band's evidence status matches the 2.0a report;
  - nothing is drawn outside 10–140 mL/min;
  - the JSON is reproducible (a checksum per view).
- **Science:** v1 makes no new claim, so no new outside check is required. It displays results already on record, with their status.
- **Review:** the owner reviews the drawings against this plan before merging.

## Steps

| Step | What | Output |
|---|---|---|
| 1.0 | This plan, approved | this document |
| 1.1 | Unbound-fraction decision recorded (issue 1) | short assessment file |
| 1.2 | `body_map.py` view and tests | JSON view, no page |
| 1.3 | Whole-body SVG and kidney zoom, record mode | page and run record |
| 1.4 | Explorer mode and the observed-data context panel | page |
| 1.5 | Docs, links from the drug page and the Patient Lab, checkpoint | — |

Each step is its own PR.

## Decisions (taken 31 October 2026)

1. **Unbound fraction (issue 1): show both values.** The split is drawn with fu 0.77 (in vitro, the value the 2.0a check used) and fu ≈ 0.60 (ex vivo, in the renal study's own subjects). Exposure is the same under both.
2. **Explorer mode in v1: yes.**
3. **"Where it acts" card: later.** Not part of v1.
4. **Rendering: 3D, using the Human Reference Atlas (decided 31 October 2026, replacing the 2D schematic).** See the next section.
5. **Context organs: yes (decided 3 November 2026).** Organs off the elimination route are drawn faintly for orientation. See "Context organs" below.

## Rendering decision: 3D reference organs (amends "What it shows" and step 1.3)

The platform owner chose a 3D view built on the **Human Reference Atlas (HRA) 3D Reference Object Library**. It is a set of expert-reviewed reference organs, published as GLB files on NIH 3D under CC BY 4.0 and fitted to the Visible Human bodies. It suits the long-term vision: its anatomy is tagged with UBERON IDs (the vocabulary the step 1.2 data already uses), and it goes from organs down to tissue structures.

**What stays the same.** The numbers, bands, evidence statuses and limitations come from the step 1.2 `body-map-view-v1` data, unchanged. 3D only changes how they are drawn.

**How the flows are drawn in 3D:**
- Kidneys, ureters and bladder from the HRA models. The heart and blood vessels as the plasma compartment, if the vascular model is usable; otherwise a simple drawn vessel, labelled as schematic.
- Flow as tubes along the renal vessels and ureters, with thickness proportional to clearance on one fixed scale. Particles move along them at a speed proportional to clearance (off for viewers who prefer reduced motion).
- Non-renal clearance as an arrow leaving the circulation, labelled "routes not identified". **The arrow does not point to the liver**, because no source puts lenalidomide metabolism there. (Since decision 5, the liver appears only as a faint context organ.)
- Evidence status on the organs: the moderate band outlines the kidneys in the warning style, with the text "probably lower than shown". Tapping an organ opens its evidence card.
- A fixed, labelled camera view by default, so screenshots are comparable. Rotation and zoom are optional.

**What it does not imply.** A realistic organ is not a concentration. Organs are not shaded by drug amount, because no source gives tissue levels.

**Engineering:**
- **three.js** is installed from npm and served from the platform's own static files (no external CDN at runtime). Models load with its GLTF loader.
- **The GLB files** are recorded in an asset manifest with file name, HRA version, sex, source URL, licence and SHA-256. The page refuses to load a changed file, as with the reference data.
- **Attribution** on the page and in the manifest: "Human Reference Atlas 3D Reference Object Library (HuBMAP), CC BY 4.0".
- **One body for all organs:** female or male, chosen once, because organ positions and sizes differ between the two reference bodies.
- **2D fallback:** the schematic SVG is drawn when WebGL is unavailable, or on request, so the page works everywhere and in tests.
- **Phones:** model detail is checked against file size and frame rate. If a model is too heavy, a simplified copy is made and recorded in the manifest as derived from the original.

**Revised steps** (1.3 becomes three steps; 1.4 and 1.5 unchanged):

| Step | What |
|---|---|
| 1.3a | Assets: the owner downloads the HRA GLB files; asset manifest with checksums and licence; check that the organs line up in one coordinate space |
| 1.3b | 3D viewer: three.js scene with the organs, a fixed default camera, the 2D fallback and the record mode |
| 1.3c | Flows and evidence drawn from the step 1.2 data: tubes, particles, organ outlines, evidence cards |

## Context organs (decision 5, 3 November 2026)

The platform owner chose to show the rest of the body's anatomy around the elimination route, so the view reads as a whole body (a dark background, a translucent skin, solid organs inside) rather than a kidney floating alone.

**Two classes of organ, kept visibly apart:**

| Class | Organs (v1) | How drawn | Carries data |
|---|---|---|---|
| **Simulation organs** | Gut (dose in), blood (plasma), kidneys, ureters, bladder | Coloured, lit, animated flows, evidence outlines | Yes: flows, shares, evidence status, from `body-map-view-v1` |
| **Context organs** | Brain, lungs, heart, liver, stomach, small and large intestine, spleen, skeleton if available | Faint, uniform, desaturated "glass"; never coloured, never animated | No. Label: "anatomy for orientation, not simulated" |

**Rules that keep the view honest:**
- A context organ never changes with the simulation: not with creatinine clearance, not with time, not with the patient record. Its look is fixed in the asset manifest, not computed.
- Selecting a context organ shows only its name, its UBERON ID and the label above; no drug numbers and no evidence card.
- The two classes come from data: `body-map-view-v1` lists the simulation nodes; any HRA object not in that list is drawn as context. A test checks that no context organ receives a flow, share or status.
- The heart appears in both roles only through the blood: the vascular model and heart stand for the plasma compartment; the heart itself carries no number.
- The page legend states the difference in one line: "Coloured organs carry model results; grey organs are anatomy for orientation."

**Why the line matters.** In a realistic body, a glowing organ reads as "the drug is there" or "the drug acts there". The model has no tissue concentrations and no site-of-action layer, so only organs on the elimination route may look active.

**Assets.** All context organs come from the same HRA male reference body and version as the simulation organs, and are recorded in the same manifest. Each is simplified for the web (step 1.3a), and the simplified copy is recorded as derived from its original. Loading order: simulation organs first, context organs after, so the page is usable before the anatomy finishes loading.

**Effect on the steps.** None added. Step 1.3a covers the extra files; step 1.3b draws both classes; the test above belongs to step 1.3c.
