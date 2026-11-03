# Digital human 1.1 — blood flow, extraction and drug movement over time (design plan)

Written 3 November 2026. Status: **approved by the platform owner on 3 November 2026**, with the three recommended decisions (see the end). Nothing is computed for layer C until its check plan (step 1.1d) is locked.

## The question it adds

Digital human 1.0 answers *where does lenalidomide leave the body, and how does that change with kidney function?* with clearance flows (mL/min of plasma cleared). 1.1 adds:

1. *How much blood goes through the vessels on the elimination route, and how much of the drug reaching the kidneys do they remove in one pass?*
2. *How does the amount of drug in the blood, leaving in urine and leaving by other routes change over the hours after a dose?*

It does **not** add drug concentrations inside organs (see "What it does not do").

## What the 1.0 map shows, and why it is not yet "flow through each tube"

The tubes in 1.0 are clearance: a rate of removal, in mL of plasma per minute. They are not blood flow and not amounts of drug. To show flow through a vessel, the map needs physiology (how much blood flows there). To show drug moving, it needs a concentration over time (how much drug that blood carries).

## Three layers, by confidence

| Layer | What it shows | Basis | Can it be checked? |
|---|---|---|---|
| **A. Reference blood flow** | Blood and plasma flow in the aorta at renal level, each renal artery and vein; drawn as a separate, quiet layer | Reference adult male physiology (cardiac output, kidney share, haematocrit) from a pinned source | It is reference physiology, not a model result; values are copied, not fitted |
| **B. Renal extraction per pass** | The share of drug entering the kidneys that leaves in urine in one pass: renal clearance ÷ renal plasma flow (adjusted for the blood-to-plasma ratio); drug in by the renal artery, out to urine, back by the renal vein | 1.0 renal clearance (2.0a model) + layer A + lenalidomide's blood-to-plasma distribution | Follows arithmetically from A and the 2.0a model; inherits the 2.0a band statuses |
| **C. Drug amounts over time** | After one dose: amount in plasma, cumulative amount in urine, cumulative amount by other routes; rates drawn as particle density on the tubes; a timeline control | A concentration–time model (decision 2) | Yes: against CC-5013-PK-001 group AUC, Cmax and half-life (EMA 2013), under a locked plan |

### Layer A: sources to pin (step 1.1a)

- **Cardiac output and organ blood-flow fractions for the reference adult male:** ICRP Publication 89 (2002), which takes resting organ flows from Williams & Leggett (1989). Secondary use of ICRP values (for example a cardiac output of 6.5 L/min for the reference male, as cited in Köller et al. 2021, *Front Physiol* 12:730418) is not enough: the values are copied from the primary tables, with page and table numbers, into a pinned extract.
- **Haematocrit** for the same reference male (to convert blood flow to plasma flow), from the same source.
- **Lenalidomide blood-to-plasma distribution:** the [14C]-lenalidomide mass-balance study in healthy men (Chen et al., *Cancer Chemother Pharmacol* 2012) reports that whole-blood and plasma radioactivity were comparable, "suggesting equal distribution between plasma and blood cells". That supports a blood-to-plasma ratio of about 1, but only qualitatively and for total radioactivity. It is recorded as an assumption with that status.
- The owner supplies the PDFs if they are not open access; they stay on her computer, as before.

The reference male matches the Atlas body already drawn. A female reference (ICRP gives one) would come with the female body, not before.

### Layer B: what the extraction means, and its limits

At normal function the 2.0a renal clearance is about 160 mL/min. With a renal plasma flow of roughly 600–650 mL/min (to be replaced by the pinned value), about a quarter of the drug reaching the kidneys would leave in urine on each pass, and the rest return through the renal veins. In the moderate band the same arithmetic inherits the 2.0a warning: renal clearance there is probably lower than shown, so extraction is too.

Renal clearance above filtration is secretion, which is limited by blood flow only when extraction is high; at about 25% it is not, so the clearance model and the flow layer do not contradict each other. If any band gave an extraction above 1, the page would refuse to draw it (a built-in consistency check).

### Layer C: the time course

The map would gain a timeline (0–48 h after a single 25 mg dose, matching the study design) and draw, at each time:
- particle density on each tube proportional to the drug moving through it (clearance × concentration, as mg/h);
- a small panel of three running totals: still in the body, out in urine, out by other routes (each as % of the dose).

The urine total at the end equals the fraction excreted unchanged that 1.0 already shows. That is a consistency check, not new evidence. The new, checkable content is the time course itself (peak, timing and decline), which is what the locked check in step 1.1d tests.

## What it does not do, and why

- **No drug concentrations inside organs.** These need tissue-to-plasma ratios for each organ. None are measured for lenalidomide in humans. They can be predicted from the drug's chemistry (Rodgers & Rowland, Poulin & Theil), and the whole-body volume of distribution could be checked against the observed one, but no organ value could be checked. That is a separate research module (PBPK) with its own plan, if ever.
- **No flow simulation through vessel shapes** (computational fluid dynamics). Drug elimination depends on organ flows, not on flow patterns inside a vessel; lumped flows are the standard in pharmacology.
- **No patient-specific blood flow.** Blood flow is reference physiology for a reference man, labelled so. The record mode changes creatinine clearance, not cardiac output or kidney size.
- **No multiple doses, dose advice or individual prediction.** Single 25 mg dose, as studied. Validation flags stay false.

## Architecture (reuses what exists)

- `intelligence_store/data/reference_physiology_icrp89_v1.json`: pinned extract (layer A), schema `reference-physiology-v1`, every value with table, page and units.
- `intelligence_store/body_map.py`: the view gains `blood_flow` (layer A values on the route) and `extraction` (layer B) in a new schema `body-map-view-v2`. v1 stays as it is for traceability.
- Layer C: a new module for the chosen concentration model (decision 2), with its own scope, report and run record, and a `time_course` block in the view (time grid, amounts, rates).
- Viewer: a "Blood flow" toggle (quiet arrows along the vessels, never wider than the clearance tubes' scale suggests a drug amount) and a timeline control; reduced-motion users get a stepped timeline.
- The 2D flow diagram and the numbers table gain the same values, so nothing is only in 3D.

## Validation strategy

- **Software:** flows conserve (renal artery in = renal vein out + urine, per side); extraction between 0 and 1 in every band; amounts sum to the dose at every time; the urine total equals the 1.0 fraction excreted; reproducible checksums.
- **Science:** layers A and B make no new claim beyond their sources and the 2.0a model. Layer C is checked in step 1.1d against the EMA 2013 group values (AUC, Cmax, half-life, per band) under a plan locked before the model is run. The check uses the same study as the 2.0a calibration, so it tests consistency of the time course, not independent validity; the report says so.

## Steps

| Step | What | Output |
|---|---|---|
| 1.1.0 | This plan, approved with the three decisions | this document |
| 1.1a | Sources pinned: ICRP 89 reference male (cardiac output, renal fraction, haematocrit); Chen 2012 blood-to-plasma statement | extract file + tests |
| 1.1b | Layers A and B in the view (`body-map-view-v2`), table and 2D diagram | data + page |
| 1.1c | Blood-flow layer and extraction drawn in 3D; kidney card shows extraction per pass | viewer |
| 1.1d | Concentration model for layer C: check plan locked, then the model and its check | plan, model, report |
| 1.1e | Timeline and amounts drawn; docs; checkpoint | page, viewer, docs |

## Decisions (taken 3 November 2026)

1. **Renal blood flow: held at the reference value** at every creatinine clearance, labelled as not adjusted for kidney function.
2. **Time course: a one-compartment model built on the 2.0a clearance** (option B), with a locked check against the CC-5013-PK-001 group values.
3. **Order: 1.1a–1.1c first** (sources, blood flow, extraction), then 1.1d–1.1e.

## Options as presented

1. **Renal blood flow when kidney function falls.** Renal plasma flow falls in kidney disease, but the relationship to creatinine clearance varies between studies and causes.
   - **Recommended:** hold blood flow at the reference value at every creatinine clearance, labelled "reference physiology, not adjusted for kidney function". Extraction then falls with clearance, which is the direction the data show.
   - Alternative: scale renal plasma flow with creatinine clearance from a published relationship (needs its own source and assessment first).
2. **Which concentration model drives the time course (layer C).**
   - **Recommended — B, a one-compartment model built on the 2.0a clearance:** clearance from the same pathway model as the map (so every number on the page agrees), with volume and absorption fixed from the EMA normal group, and a locked check against the group AUC, Cmax and half-life in every band. It works in both the explorer and record modes.
   - A — Hughes 2019 or Kim 2026 under their own scopes: published models, but their clearance differs from the map's, so the page would show two clearances for one patient; Kim needs eGFR, which the explorer does not have. Record mode only.
3. **Order.** **Recommended:** 1.1a–1.1c first (blood flow and extraction, no new model), then 1.1d–1.1e. The first half is useful on its own and needs only sources.

## Steps 1.1a and 1.1b delivered (3 November 2026)

**1.1a — sources pinned.**
- `intelligence_store/data/reference_physiology_icrp89_v1.json` (ICRP Publication 89, file SHA-256 `99f31655…`, kept on the owner's computer): reference adult male cardiac output **6.5 L/min** (Table 2.39, printed page 28), kidneys **19%** of it (Table 2.40, printed page 29; the Section 7.7.2 table gives the same), red cells **43%** of blood volume (Section 7.3, paragraph 309). Derived: renal blood flow 1235 mL/min, renal plasma flow 704 mL/min.
- `intelligence_store/data/lenalidomide_blood_plasma_chen_2012_v1.json` (Chen et al. 2012, open access): whole-blood to plasma AUC ratio of total radioactivity **0.931 ± 0.020** (Table 2, page 794); red cells held 36–44% of blood radioactivity against a haematocrit of 41–43% (page 796). Used as the blood-to-plasma ratio, status *assumed*, with three recorded limits (total radioactivity, six healthy men, rapid exchange assumed).
- Loader: `intelligence_store/reference_physiology.py`.

**1.1b — in the view** (`body-map-view-v2`): `blood_flow` (reference, the same at every creatinine clearance) and `extraction`, the share of drug arriving in renal arterial blood that leaves in urine in one pass, = renal plasma clearance ÷ blood-to-plasma ratio ÷ renal blood flow. It carries the band's evidence status, and the view refuses to build if it fell outside 0–1. The numbers panel, the kidney card and both run records show it, with the two assumptions and the two source checksums.

**Correction to the estimate in this plan.** The plan said "about a quarter" of the drug reaching the kidneys would be removed per pass, dividing renal clearance by renal *plasma* flow. That would be right only if the drug stayed out of red cells. Lenalidomide spreads into them about equally (Chen 2012), so the drug arriving is carried by whole blood, and extraction is about **14%** at normal function (162 mL/min ÷ 0.931 ÷ 1235 mL/min), 8% in the mild band, 5% at 40 mL/min and 3% at 20 mL/min.

## Step 1.1c delivered (3 November 2026): blood flow in 3D

- **"Blood flow" button** in the 3D toolbar (off by default, so the drug layer stays the main picture). When on, small red dots move in along each renal artery (aorta → artery → kidney) and blue dots back out along each renal vein to the inferior vena cava, with a label: blood to each kidney (reference adult), and the share of drug arriving that is removed per pass.
- **Constant width and speed.** Reference blood flow is the same at every creatinine clearance, so nothing about the blood layer changes with the record or the slider; only the drug strands and the extraction in the label do.
- **Geometry:** renal vein centre lines extracted from the named Atlas veins (`body_map_renal_vein_lines_v1.json`, pinned; built by `scripts/build_body_map_vessel_lines.py --veins` from the source checked against its SHA-256). Blood paths are built from pinned files (`body_map_paths.blood_paths`); a test checks that the way in follows the renal artery and the way out ends on the vena cava's centre line.
- **Fix found on the way:** with more buttons the toolbar wraps onto two rows, and the evidence banner covered the second row so its buttons could not be clicked. The banner and the organ card now sit below the toolbar, however many rows it has.

**Next:** 1.1d, the time-course model: its check plan is written and locked before anything is computed.

