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
- **Renderer (changed in step 1.3b):** a small WebGL viewer written for the platform (`landscape_ui/static/body-map/body-map-viewer.js`), served from the platform's own static files, in place of three.js. The planned three.js could not be installed in the build workspace, and the assets from step 1.3a need only positions, normals and indices, so no library is needed. No external code at runtime, and no third-party licence to track. three.js remains an option if later steps need more than this.
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

## Step 1.3a delivered (3 November 2026): the 3D assets

**Source.** The HRA *3D Reference Organ Set for United, Male* (`3d-vh-m-united.glb`, 241.6 MB, 6.9 million triangles, CC BY 4.0), checked against the owner's SHA-256 (`fae3ac19…`). It holds every organ in one body and one coordinate frame (metres, +y up, body left +x). Its kidneys match the HRA's separate kidney files to within 0.12 mm, which confirms the frame independently. The set has no stomach; one from Innerscene (CC0) is placed by hand and labelled approximate.

**Output** (built by `scripts/build_body_map_assets.py`, pinned in `intelligence_store/data/body_map_assets_v1.json`, loaded by `intelligence_store/body_map_assets.py`):

| File | Class | Size | Triangles | Parts |
|---|---|---|---|---|
| `landscape_ui/static/body-map/models/body-route-male-v1.glb` | simulation | 3.6 MB | 203,259 | 20 |
| `landscape_ui/static/body-map/models/body-context-male-v1.glb` | context | 2.8 MB | 166,294 | 19 |

- **Simulation parts** name their `body-map-view-v1` node: small intestine → gut; arteries, veins, unlabelled vessels and heart → plasma; each kidney's capsule, cortex, pyramids, papillae and hilum → kidney; renal pelvis and calyces, ureters, bladder and urethra → urine.
- **Context parts** name none: skin, brain, spinal cord, lungs, airways, larynx, liver, gallbladder, biliary tree, pancreas, colon, spleen, thymus, spine, pelvis, legs, prostate, genital ducts, stomach.
- **Left out, each with a reason in the manifest:** fat layers (they hide the organs), mouth and teeth, eyes and their muscles and nerves, knee and larynx muscles, tonsils, one lymph node, hyoid. The Atlas skeleton is partial (spine, pelvis, legs; no ribs, skull or arms).
- **Simplification.** Quadric-based vertex clustering in numpy (`intelligence_store/glb_mesh.py`). Vertices on opposite sides of a thin wall are never merged, which keeps vessel and heart walls closed. Organs built from tiled segments (brain, lungs, liver) are reduced to their outer shell (voxel 3–4 mm, smoothed), because their inner walls stack up in a translucent view. Each part records its method and how far its bounding box moved: at most 2.3 mm for simulation parts (limit 3 mm) and 7.5 mm for context parts (limit 8 mm).
- **Checks recorded in the manifest:** all parts inside the skin's bounding box; kidneys on the correct sides; kidneys match the separate HRA files; no context part names a body-map node. The build writes nothing if a check fails.

**Three points for the owner to confirm** (where the build had to choose between parts of decision 5):
1. **Heart.** The table lists it as context, while the rules say the heart and vessels stand for the plasma compartment. The build follows the rules: the heart is in the plasma group and is coloured with the blood. The viewer attaches no number to the heart itself (step 1.3c).
2. **Small intestine.** The table lists the intestines as context, while the simulation row lists the gut as the dose-in site. The build makes the small intestine the gut (simulation) and the colon context.
3. **Stomach.** The decision says context organs come from the same reference body. The Atlas has no stomach, so this one is a different source, placed by eye, and marked `approximate_by_hand` in the manifest.

**Open:** the HRA release version of the United set is not recorded yet (`hra_version: null`); the owner reads it from the download page.

## Step 1.3b delivered (3 November 2026): the record-mode page with the 3D viewer

**Route:** `/landscape/workspace/scenarios/<scenario>/patient-state/revisions/<revision>/body-map` (and `?format=json` for the `body-map-view-v1` data). Linked from the patient-state record as "Lenalidomide body map (3D)".

**What the page shows**
- The shared simulation banner and, in the moderate band, the "outside check disagrees" alert above the view.
- **3D view:** the step 1.3a models on a dark panel. Four fixed camera presets (whole body, abdomen, kidneys, side), with whole body as the default so screenshots are comparable. Drag turns the body; zoom buttons. Selecting an organ shows its name, whether it is a simulation organ (and which body-map node it draws) or "anatomy for orientation, not simulated", and its UBERON IDs. The stomach's card says it is placed by hand.
- **Checksums before drawing:** the browser computes each model's SHA-256 and compares it with the pinned manifest. A changed file is refused and the 3D view is not drawn. Browsers that cannot check (no secure connection) or have no WebGL show a message instead.
- **Numbers beside the view:** filtration and secretion (with fu 0.77 and 0.60), renal total, non-renal, total clearance, the fraction excreted unchanged and the relative exposure. All come from `body-map-view-v1`; the viewer draws no number itself.
- **Flow diagram (2D, server-drawn):** the same flows as line widths on the fixed normal-total scale. It is always on the page, so every number is available without the 3D view.
- **Limits** and the **run record**, which is the 2.0b pathways record plus the body-map view, the asset manifest and both model checksums.
- Outside 10–140 mL/min or with missing inputs, no map is drawn and the reason is shown.

**Not yet (step 1.3c):** flows drawn in 3D (tubes and particles), evidence-status outlines on the kidneys, and per-organ evidence cards with numbers.

## Step 1.3c delivered (3 November 2026): flows and evidence in 3D

**Flow paths** (`intelligence_store/data/body_map_flow_paths_v1.json`, built by `intelligence_store/body_map_paths.py` from the pinned route model; a test rebuilds it exactly):
- **Into each kidney:** from the aorta at the level of that kidney's hilum, through the hilum, to the kidney's centre. Filtration and secretion are two strands, each kidney carrying half of each.
- **Into urine:** from each renal pelvis down its ureter's centre line (20 slices of the ureter mesh) to the bladder.
- **Absorption:** from the small intestine straight into the blood (inferior vena cava at kidney level), drawn dotted and without a value, because the view has none (bioavailability taken as 1). It does not pass through the liver: the model has no first-pass step. (Superseded by flow paths v3, 12 November 2026: see the correction at the end.)
- **Non-renal:** no path, because the routes are not identified. A label at the aorta gives the value and says so. Its leader line points away from the liver.
- Only simulation organs anchor a path.

**Drawing.** Tubes have a diameter proportional to clearance on the view's fixed scale (the whole normal-function clearance through one tube would be 2 cm), so records can be compared by eye. Particles move along each strand at a speed proportional to its clearance. The flow layer is drawn over the anatomy, as a diagram, so vessels never hide it. Buttons turn the flow, the animation and the labels on and off. With "reduce motion" set in the browser, the flow starts paused.

**Evidence status on the organs.** In the moderate band (outside check disagrees) the kidneys are outlined in orange and a banner states the finding. Where the check was consistent in the primary scenario only, the outline is amber. Calibrated and consistent bands have no outline.

**Evidence cards.** Selecting a simulation organ opens its card, with numbers copied from `body-map-view-v1`:
- kidneys: filtration and secretion under both unbound fractions, renal total, band status, basis;
- ureters and bladder: into urine, the fraction excreted unchanged;
- blood: total clearance, non-renal, relative exposure;
- small intestine: the absorption note.

Each card names the source model and the view checksum. Context organs have no card, only "anatomy for orientation, not simulated".

**Step 1.3 is complete.** Next in the plan: 1.4 (explorer mode with a creatinine-clearance control, and the observed-data context panel) and 1.5 (docs, links, checkpoint).

## Step 1.4 delivered (3 November 2026): explorer mode and the observed-data context

**Explorer route:** `/landscape/patient-lab/body-map?crcl=…` (and `&format=json`). No patient record: the creatinine clearance is chosen with a slider or typed, from 10 to 140 mL/min. It starts at 110 mL/min, the pathway model's calibration point. The page is the record-mode page (3D view, numbers, flow diagram, limits) with the form on top; the form works without JavaScript, and a small script (`body-map-explorer.js`) keeps the slider and the number box in step and shows the new value when the slider is released. Outside 10–140 no map is drawn. The value stands for creatinine clearance measured from urine, as in the study.

**Observed-data context panel** (`intelligence_store/body_map_context.py`, schema `body-map-context-v1`), on both the explorer and the record pages, for the band the value falls in:
- **Model beside observation:** exposure relative to normal function, dose leaving unchanged in urine, renal clearance and total apparent clearance. The model column is copied from the map. The observed column is copied from the pinned EMA 2008 extract (arithmetic means) and the pinned EMA 2013 extract (geometric means, with their CV or SD). Exposure ratios to the normal group are worked out from the printed means and say so.
- **Group, not point:** a note says the observed values are group summaries for 5–7 subjects whose measured creatinine clearance fell in the band, not values at the chosen number.
- **EMA geometric-mean ratios with 90% CIs** for the moderate and severe bands, where Table 4 reports them, with the note that their reference group pools normal and mild subjects.
- **The EMA regression of renal clearance** (CLr = −17.35 + 1.89 × CLcr) evaluated at the chosen value, next to the map's renal total, labelled "context, not a check": it was fitted to the same subjects as the calibration (issue 3 of this plan).
- **The label's renal dose steps,** quoted from Table 3 (revision 3/2023), with the row containing the value marked. The panel states that the platform proposes no dose, that the label uses Cockcroft–Gault estimates, and that the label and the regulatory-context note use different thresholds.
- Sources with their checksums, and a checksum of the panel itself.

**Run record (explorer):** `record_for_body_map_explorer`. No patient record; the entered value is the input. Same assumptions as the record mode except the Cockcroft–Gault weight basis, which does not apply. Checksums of the view, the context, the pathway evidence and report, the unbound-fraction record, the asset manifest and both models. The simulation banner shows "No patient record" in place of "Synthetic patient record".

**What the panel shows that matters:** at moderate kidney function the map's renal clearance (about 59 mL/min at 40) is about twice the group's observed geometric mean (27 mL/min), and its urine fraction (67%) is well above the observed 38–42%. That is the 2.0a finding the moderate-band warning already states; the panel puts the observed numbers next to it.

**Tests:** `tests/test_body_map_explorer.py` (values copied from the extracts, model column equals the map, ratios only where reported, regression labelled, label rows matched without a dose, reproducible checksums, explorer page, JSON, out-of-range and bad requests).

**Next:** 1.5 (docs, links from the drug page and the Patient Lab, checkpoint).

## Step 1.5 delivered (3 November 2026): links, docs and the end of Digital human 1.0

**Links to the body map:**
- **Sidebar:** "Body map explorer" under Patient Lab, on every workspace page.
- **Lenalidomide drug page:** "Body map explorer" in the drug hub under *Exposure and effect tools*; the record-mode map stays listed under *On synthetic patients*.
- **Saved Patient Lab:** a "Lenalidomide body map explorer" button beside the other Patient Lab tools.
- **Each patient record:** "Body map (3D)" under *Where does the drug leave the body?* in the record's results (layout step 3), and the record-mode map links to the explorer at the record's creatinine clearance.

**Status of Digital human 1.0.** All planned steps (1.0–1.5) are delivered. The body map answers its question (*where does lenalidomide leave the body, and how does that change as kidney function falls?*) with the 2.0a pathway model, on Human Reference Atlas anatomy, with every number's evidence status and the study's observed values beside it. It makes no new scientific claim: no outside check was added, and the validation flags stay false.

**Open items carried forward:**
- The HRA release version of the United male set (`hra_version: null` in the asset manifest).
- The three points for the owner in step 1.3a (heart drawn with the blood, small intestine as the gut, the hand-placed stomach).
- The moderate-band disagreement remains the main scientific limitation. Lower renal elimination than the intact-nephron reading predicts is the known finding; a revised reading needs its own locked plan and an independent check (for example Bridoux 2016, once obtained).
- Exact-reproduction checks of five locked reports differ in the last floating-point digits on macOS; they pass on the CI platform (Linux). A tolerance-based comparison off CI is a candidate fix.

**Candidates for Digital human 1.1+** (each needs its own plan): a plasma time-course panel from Hughes or Kim under their own scopes; a female reference body; a static, sourced "where it acts" card (cereblon, IKZF1/3) from the knowledge layer; a second drug through the same generic `body-map-view-v1` data.

## Correction (3 November 2026): kidney flows start in the aorta and follow the renal arteries (flow paths v2)

**What was wrong.** In paths v1 each kidney flow started 2–4 cm in front of the aorta and ran straight to the kidney's hilum, below the renal arteries, so on screen the strands looked displaced from the vessels they stand for. The cause: the route model merges all arteries into one part, and v1 took "the aorta" as the middle of every artery near the midline at that height, which the superior mesenteric and other front arteries pulled forward.

**Fix.**
- `scripts/build_body_map_vessel_lines.py` reads the original Atlas file (checked against its SHA-256 `fae3ac19…`; it stays on the owner's computer) and writes centre lines for the abdominal aorta, both renal arteries and the inferior vena cava to `intelligence_store/data/body_map_vessel_lines_v1.json` (pinned).
- Flow paths v2 (`body_map_flow_paths_v2.json`, method `body-map-flow-paths-build-v2.0`): each kidney flow starts on the aorta's centre line at its renal artery's origin, follows that artery's centre line, and ends at the kidney's centre. Absorption ends on the vena cava's centre line at renal-artery level. Urine paths are unchanged. v1 is kept unchanged for traceability.
- Tests check that each kidney flow starts within 2 mm of the aorta's centre line and runs along the renal artery.

**Atlas naming.** The Atlas node called "left renal artery" lies on the body's right and "right renal artery" on the body's left, opposite to the kidneys (whose sides were confirmed in step 1.3a). Sides are assigned by position, and the Atlas name is kept in the file. Worth reporting to the HRA team.

**Labels.** Flow labels are now measured and kept inside the view, and labels on the same side no longer overlap (they did in the side view).

Nothing in the numbers, bands or evidence changes; this is drawing geometry only.

## Rendering pass (3 November 2026)

Display only; no geometry, number or evidence status changes.
- **Transparency:** translucent organs are drawn farthest first with ordinary alpha blending (back faces before front faces), instead of being added together, which washed overlapping layers out to a white haze. Context anatomy is drawn first as a backdrop, so it never veils the organs that carry results. The skin, the small intestine and the kidney capsule stay as glowing layers on top; the capsule's edge colour still shows the evidence band (orange where the outside check disagrees, amber where it agrees in the primary scenario only).
- **Lighting:** a key light, a cool fill light, a back light for edges, a sky/ground ambient, and a specular highlight set per material (glossy vessels, matte organs).
- **Kidney materials:** a lighter, more translucent cortex so the pyramids show; papillae pink instead of the urine yellow, which now marks only the collecting system, ureters and bladder.
- **Flow tubes:** a faint glow around each tube. Its width is decoration and carries no value; the tube itself keeps the clearance-proportional width.
- **Sharpness:** drawn at the screen's pixel density, capped at 2× so phones stay fast.

## Correction (12 November 2026): absorption goes by the portal vein through the liver (flow paths v3)

Found in the AI design draft of 12 November (`docs/reviews/2026-11_organ_level_design_draft.md`, section 7, item 1): paths v2 drew absorption as a straight line from the small intestine to the inferior vena cava at renal-artery level, a vessel connection that does not exist. Blood from the intestine drains by the superior mesenteric vein into the portal vein and through the liver, which is drained by the hepatic veins into the vena cava near the heart (ICRP 89, paragraph 246).

- New centre lines `body_map_portal_route_lines_v1.json`, extracted from the HRA United male file by `scripts/build_body_map_vessel_lines.py --portal`: the superior mesenteric vein, the hepatic portal vein, and the vena cava's centre where the hepatic veins join it.
- Flow paths v3 (`body_map_flow_paths_v3.json`, method `body-map-flow-paths-build-v3.0`): absorption runs from the small intestine to the nearest point of the superior mesenteric vein, up it and the portal vein, then straight through the liver to that point on the vena cava. Every other path is unchanged. v2 is kept unchanged for traceability.
- **The liver is passed through, not modelled.** No loss in the liver is drawn or calculated; the path still carries no value. The liver stays a context organ. The hepatic veins branch inside the liver and are not followed; the segment through the liver is a straight line for drawing.

