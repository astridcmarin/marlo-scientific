# AI-generated design draft (Claude Fable, second account), not an independent review

## Digital human, next step: an organ-level, PBPK-style model of lenalidomide. What the body map could truthfully show

| | |
|---|---|
| Date | 12 November 2026 |
| Model identifier | `claude-fable-5-2` |
| Repository read | `astridcmarin/marlo-scientific`, branch `main`, commit `f1eb8b6e9dd2516e4c8edda010fe17fb23d46e8b` (merge of PR #118, 12 November 2026) |
| Kind of document | Design only. No code was written, no model was run, nothing in the repository was changed, and no pull request, issue or commit was made. |
| Platform status | Research and education. Nothing here is validated for clinical prediction; nothing here is a dosing or clinical statement. |

### How values are labelled in this document

| Label | Meaning |
|---|---|
| **observed** | Measured in a study and quoted from a source with its location. |
| **reference** | An ICRP 89 reference value for a reference woman or man. Not a measurement of any person. |
| **derived** | Arithmetic done in this draft on quoted values; the formula is shown. |
| **predicted** | Would come from a model or a prediction method. None is computed in this draft. |
| **to be sourced** | No number is given because no attached source states it. |

### What was read, and how

- **Repository (read only, shallow clone):** `CLAUDE.md`; `docs/PRODUCT_AND_SCIENCE_ROADMAP.md`, `STATUS_BY_DRUG.md`, `SIMULATION_2_RENAL_PATHWAYS.md`, `DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md`, `DATASET_LEDGER.md`, both November reviews (in full); `docs/PATIENT_LAB_2_0.md` (outline and keyword reading only); `intelligence_store/body_map.py`, `body_map_paths.py`, `body_map_assets.py`, `dialysis_evidence.py` (in full); `body_map_time_course.py`, `body_map_context.py`, `patient_renal_pathways.py`, `population_pk.py` (docstrings and function list); `landscape_ui/body_map_pages.py`, the three body-map templates, `body-map-explorer.js`, `body-map-timeline.js` (in full); `body-map-viewer.js` (lines 1–440 in full, the rest by keyword); the asset manifest, flow-path and vessel-line files (summarised by script); `reference_physiology_icrp89_v1.json` and the two Chen 2012 extracts.
- **Attached sources** (SHA-256 of each file as received):

| Source | SHA-256 (first 12) | Matches the repository's pin? | How read |
|---|---|---|---|
| ICRP Publication 89 (`ANIB_32_3-4.pdf`, three parts rejoined, 282 pages) | `99f3165571a0` | yes (`reference_physiology_icrp89_v1.json`) | text layer, `pdftotext -layout` |
| Chen et al. 2012 (`280_2011_Article_1760.pdf`) | `0647d1cfa5a3` | yes (both Chen 2012 extracts) | text layer, both in layout and in reading order |
| EMA 2008 withdrawal assessment report | `c27c16b42062` | yes (per the 10 November review) | text layer |
| FDA 2005 clinical pharmacology and biopharmaceutics review, NDA 21-880 | `59be36a9ae21` | yes (`docs/DOSE_OPTIMISATION.md:79`) | **scanned images, no text layer.** Read by OCR (tesseract). PDF pages 6, 14 and 15 were also checked by eye against the page image. Any other FDA quote below is marked "OCR only". |
| TGA AusPAR clinical evaluation report (`.docx`) | `a3655357387f` | not pinned (review finding F28) | converted with pandoc. Tables 9, 10 and 11 are images in the file and were **not** read. The conversion loses page and section numbers, so locations are given by heading. |

- **Web:** eleven searches, to locate studies that are not attached and to get links. Anything taken from a search result is marked "abstract only, not pinned".
- **Quotes:** copied from the extracted text. Three kinds of repair were made and nothing else: footnote letters attached to table row names were dropped (for example "Adipose tissuea"); characters the text layer garbles were restored ("∞", "µ", ">"); line breaks and end-of-line hyphens were removed. A script compared every quotation in this draft with the source texts after these repairs.
- **Not opened:** any eligibility annotation, the 200-trial sample, anything under `instance/`. Disclosure: two keyword searches (`NDA 21-880`; tissue and physicochemical terms) ran over the repository tree by file content. They printed only matching lines from documentation and non-eligibility modules. No eligibility file was opened or displayed.

---

## Summary

1. **The evidence supports a small model, not a whole-body one.** Gut lumen, blood, kidneys (filtration plus secretion into urine), one or two lumped "rest of body" spaces, and a small non-renal loss that cannot be assigned to an organ. The liver and portal vein belong on the picture as the anatomical way in, with no elimination attached.
2. **In the attached sources, no lenalidomide concentration was measured in any human solid organ.** Human observations exist for plasma, whole blood and red cells, urine, faeces and semen. Kidney, brain and "tissues" are covered by rat statements without numbers. Bone marrow, the site of action in myeloma, has nothing.
3. **Organ partition cannot be predicted from the attached sources.** Rodgers & Rowland and Poulin & Theil need logP, pKa, fraction unbound and blood-to-plasma ratio. The attached sources give the last two and neither of the first two.
4. **No check on human plasma or urine data can be blind.** Every human dataset that could test the model has been seen by the platform, and now also by this draft.
5. **The organ-level body map can honestly show:** reference physiology for a woman and for a man; where human observations exist and where they do not; a labelled, lumped model of amounts over time. **It must not show** an organ concentration as observed, a predicted partition without its label, or a lump painted onto individual organs.
6. **An anatomy review found 19 issues** in the current map (section 7). The main one: absorbed drug is drawn from the small intestine straight into the inferior vena cava at kidney level, bypassing the portal vein and liver.
7. **First step proposed for approval:** pin a second ICRP 89 extract with women's and men's values side by side (section 9, step 1). It needs no model and no decision about PBPK.

---

## 1. What the platform has now

**Model.** The body map (`body-map-view-v2`, `intelligence_store/body_map.py`) is a clearance split, not a distribution model:

- Five nodes: gut, blood plasma, kidney (glomerulus, tubule), urine, non-renal routes (`body_map.py:51–60`).
- Clearance from the 2.0a pathway model, intact-nephron reading, calibrated on the normal group of CC-5013-PK-001: filtration = unbound fraction × creatinine clearance; secretion = renal clearance minus filtration, scaled with creatinine clearance; non-renal clearance held constant (`docs/SIMULATION_2_RENAL_PATHWAYS.md`, "2.0a").
- Reference renal blood flow for the ICRP 89 **man only**, and the share of drug removed per pass through the kidneys (`body_map.py:202–229`).
- **Time course:** one well-mixed space with first-order absorption, on the map's own clearance. The module states "one well-mixed body, constant volume" among its limits (`docs/DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md`, "Step 1.1e delivered"). The timeline shows the share of the dose in gut, body, urine and other routes.
- The code says what is absent: "The arrows are clearance flows, not amounts or concentrations in organs: no source gives lenalidomide tissue concentrations" (`body_map.py:10–11`).

**Checks.**

- *Software:* every input file is SHA-256 pinned and the view refuses to build if one changed; extraction outside 0–1 raises an error (`body_map.py:221–222`); the time course is checked against a numerical solution and for mass balance; the urine total must equal the map's fraction excreted; context organs cannot carry a model value (`body_map_assets.py:36–39`); the browser checks each 3D file's checksum.
- *Science (all consistency checks, none blind):* 2.0a (impaired groups of the calibration study), 2.0c (end-stage disease, inconclusive), 2.0d (steeper secretion, not adopted), 2.0e (bioavailability re-check), time course v1 and v2.
- *Known to be wrong, and shown:* the peak is too low in every group; the moderate and severe bands depend on the unmeasured bioavailability; in the moderate band the model's urine share is 67% against 38–42% observed (`docs/DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md`, "Step 1.1d result").

---

## 2. The smallest organ-level structure the evidence supports

### 2.1 The science in brief

A PBPK model replaces abstract compartments with organs. Each organ has a volume, a blood flow and a tissue-to-plasma partition coefficient (Kp, the concentration ratio at equilibrium). Two questions decide the structure.

**Which organs can the data tell apart?** Only blood and urine were sampled over time in humans. A plasma curve can support at most two or three distribution spaces. The TGA report describes the sponsor's population model as "A two-compartment model with first order input" (TGA CER, heading "Population pharmacokinetics"). Any organ beyond that is drawn from physiology and prediction, not from lenalidomide data.

**What limits uptake into tissue: blood flow or the membrane?**
- *Perfusion-limited:* the drug crosses membranes easily, so tissue fills as fast as blood delivers it. Needs only flow, volume and Kp.
- *Permeability-limited:* the membrane is the slow step. Needs a permeability–surface-area term for each tissue, which is rarely measured.

Lenalidomide's properties point both ways:
- For easy distribution: low protein binding, equal spread between plasma and blood cells, a volume of distribution near body weight, rapid absorption.
- For membrane limitation: the FDA review calls it "highly hydrophilic" with "low permeability in the Caco-2 system" (PDF p. 15, printed p. 14, checked by eye), and the applicant classed it as low permeability. The rat study found brain distribution "extremely low" (EMA 2008, p. 12/51).

**Conclusion for the design.** Treat the kidneys and the lumped tissues as perfusion-limited, but give each lump a distribution flow that may be *lower* than its blood flow (the "minimal PBPK" form of Cao & Jusko 2012). That states honestly that the data cannot separate flow from permeability. Treat the brain as not perfusion-limited and give it no value.

### 2.2 Compartments

| # | Compartment | Why it is in | Uptake | What humans data exist for it |
|---|---|---|---|---|
| 1 | **Gut lumen** (dose) | Oral drug. Absorption is high: "at least 90% of the dose absorbed" (Chen 2012, p. 796). | First-order absorption | None directly. The amount "not yet absorbed" is a model construct (the timeline already says so). |
| 2 | **Portal vein and liver** | Anatomy: intestinal blood reaches the circulation through the liver. No elimination is assigned: "It was concluded that lenalidomide was resistant to both Phase I and Phase II metabolism" (FDA 2005, PDF p. 16, OCR only). | Pass-through. In the mathematics it can sit inside lump 6 until a liver Kp is sourced. | None. |
| 3 | **Blood** (arteries, veins, heart chambers and lung vessels as one pool; plasma and cells in equilibrium) | The sampled space. | — | **Observed:** plasma curves; whole blood and red-cell radioactivity (men). |
| 4 | **Kidneys** | The eliminating organ; renal clearance and urine amounts are observed; reference blood flow is known; highest radioactivity in the rat. | Perfusion-limited tissue; elimination by filtration and secretion (2.3) | Renal clearance and urine recovery. No tissue concentration. |
| 5 | **Urine** (cumulative amount) | Main exit. | — | **Observed:** amounts over time. |
| 6 | **Rest of body, fast lump** | The plasma curve supports one or two distribution spaces. | Perfusion-limited with a distribution-flow fraction | None per organ. |
| 7 | **Rest of body, slow lump** (optional) | Only if a locked plan shows one lump cannot give the peak and the terminal phase together. | As 6 | None per organ. |
| 8 | **Non-renal loss** | Small and real: metabolites and faeces (2.4). | Cleared from the blood pool; **not assigned to an organ** | **Observed:** faecal radioactivity, metabolite shares. |

Not compartments, but shown as evidence:
- **Brain:** animal data only, "extremely low" (rat). Excluded from the lumps so that they do not imply brain exposure.
- **Semen:** a human observation in men (section 4). It holds 0.0062% of the dose, so it is not part of the mass balance.
- **Dialyser:** only the total removed by one session is known (`dialysis_evidence.py`); not modelled now.

```
 dose -> [1 gut lumen] --absorption--> (2 portal vein -> liver, no loss) --> [3 blood] <--> [6 fast lump] ( <--> [7 slow lump] )
                                                                               |  ^
                                                             renal artery      v  |  renal vein
                                                                           [4 kidneys] --filtration + secretion--> [5 urine]
                                                                  [3 blood] --non-renal loss, organ not assigned--> [8]
```

Why not a full set of fourteen organs: each further organ adds a Kp that no lenalidomide measurement in humans constrains. The 2.0 document already reached this conclusion ("Building one would mean inventing most of its parameters", `docs/SIMULATION_2_RENAL_PATHWAYS.md:9`). The structure above adds only what is observed (blood, kidney elimination, urine) or needed to conserve mass (the lumps).

### 2.3 Renal clearance: filtration plus active secretion

**What is observed.**

| Statement | Source, location | Quote | Type |
|---|---|---|---|
| Most of the dose leaves unchanged in urine | EMA 2008, p. 20/51 | "the overall urinary recovery of unchanged drug being approximately 85% of the administered single oral dose" | observed |
| Same, radiolabel study | TGA CER, heading "Metabolic profiles" | "mean ± SD unchanged lenalidomide 81.74 ± 3.61% (urine), 0.45% ± 0.24% (feces)" | observed, 6 healthy men |
| Renal clearance exceeds filtration | Chen 2012, p. 796 | "Mean renal clearance (260 ml/min) of the plasma radioactivity was nearly two-fold greater than the normal glomerular filtration rate (125 ml/min), suggesting that renal elimination likely includes both passive and active processes." | observed (total radioactivity, 0–12 h) and the authors' reading |
| Renal clearance, value | Chen 2012, p. 793 | "The mean renal clearance was estimated to be 261 ± 30 mL/min based on the amount of radioactive equivalents recovered in urine and the radioactive plasma AUC from 0 to 12 h postdose." | observed, 6 healthy men, mean age 29.7 years |
| Renal clearance, regulator's statement | EMA 2008, p. 20/51 | "Renal clearance was at least 190 ml/min, suggesting that active renal secretion occurs." | observed, study not named |
| The transporter is unknown | Chen 2012, p. 796 | "lenalidomide is a weak substrate of P-glycoprotein, but not a substrate of human organic anionic transporters OAT1/OAT3, human cationic transporter OCT1 and human organic anion transporting polypeptide OATP2 [20]. If there is an active secretion component in the renal excretion of lenalidomide, it is not known which renal transporter(s) may be responsible." | observed in vitro, cited by the authors |
| Kinetics are linear | EMA 2008, p. 20/51 | "The maximum concentration (Cmax) and area-under-the-curve (AUC) increased in a dose-proportional manner over the dose range studied (5 to 400 mg)." | observed |

**How to represent it.**
- **Filtration** = fraction unbound × glomerular filtration rate, acting on plasma water arriving at the kidney.
- **Secretion** = one linear clearance, with no named transporter and no saturation. Linear kinetics over 5–400 mg give no support for a Michaelis–Menten term, and no transporter is identified to hang it on.
- **No reabsorption term.** Nothing in the attached sources measures it.
- **Scaling with kidney function:** keep the platform's intact-nephron reading (both terms proportional to creatinine clearance) and its 2.0e status. The organ model must not quietly change the clearance model; that would make every earlier check void.
- **Flow limitation does not matter here.** The platform derives a per-pass extraction of about 14% at normal function (`docs/DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md:105`, derived). At that level renal clearance is set by filtration and transport, not by blood flow, so the choice of organ clearance equation (well-stirred or parallel-tube) changes almost nothing. The plan should state this and test it numerically.

**A conflict to settle before any run.** Three renal clearances are on file for normal function: the platform's 162 mL/min (85% of CL/F in the normal group of CC-5013-PK-001; `SIMULATION_2_RENAL_PATHWAYS.md:23`), the EMA's "at least 190 ml/min", and Chen 2012's 261 ± 30 mL/min in young healthy men. They come from different people and methods (parent drug against total radioactivity; 7 mixed subjects against 6 young men). The 2.0 document already lists the first mismatch as unreconciled (`SIMULATION_2_RENAL_PATHWAYS.md:48`). The organ model inherits it.

### 2.4 The small non-renal clearance

| Statement | Source, location | Quote | Type |
|---|---|---|---|
| Faeces | Chen 2012, p. 793 | "mean total fecal elimination of radioactivity accounted for only 3.95 ± 1.94% of the dose" | observed |
| Metabolites | TGA CER, "Metabolic profiles" | "Metabolites A (hydroxy-lenalidomide) and B (N-acetyl-lenalidomide) contributed 4.59% and 1.83% to the excreted radioactive dose, respectively." | observed |
| Not cytochrome P450 | EMA 2008, p. 20/51 | "Lenalidomide is not metabolised via cytochrome P450 in humans and further enzymatic systems have not been studied." | observed in vitro |
| Hydrolysis | EMA 2008, p. 12/51 | "Lenalidomide is metabolically stable in vitro, metabolism related to hydrolysis is seen in vivo" | observed, species not separated |

Representation: one constant clearance from the blood pool, labelled "organ not assigned". It must not be drawn at the liver: no attached source places it there, and hydrolysis in plasma would not be hepatic. Its size depends on bioavailability (10–29 mL/min across 90–100% absorbed; 2.0e, D3) and keeps that range.

One wording point: the map says the non-renal routes are "not identified" (`body_map.py:59`, `body_map_pages.py:153`). Chen 2012 identifies part of them (two minor metabolites, faeces). "Small; partly identified (two minor metabolites, about 4% of radioactivity in faeces); organ not known" would be closer to the source.

### 2.5 Oral absorption

| Statement | Source, location | Quote | Type |
|---|---|---|---|
| Extent | Chen 2012, p. 796 | "it can be concluded that the absorption of lenalidomide (at least 90% of the dose absorbed) is very high in humans following oral administration. Further, based on the 82% of the dose excreted in intact form in urine within 24 h postdose, the oral bioavailability of lenalidomide is at least 82% in humans." | observed bounds |
| Absolute bioavailability | EMA 2008, p. 19/51 | "Absolute bioavailability has not been determined in humans." | — |
| Rate | Chen 2012, p. 793 | "the maximum concentrations were achieved between 0.5 and 1 h postdose" | observed, suspension, fasted |
| Class | FDA 2005, PDF p. 29 (OCR only) | "The Applicant classifies lenalidomide as BCS Class 3: High Solubility - Low Permeability." | applicant's classification |
| Solubility | FDA 2005, PDF p. 6, printed p. 5 (checked by eye) | "exhibits the greatest solubility in 0.1N HCl buffer with an equilibrium solubility of 18 mg/mL. Solubility was significantly lower in less acidic buffers, ranging from about 0.4 to 0.5 mg/mL." | observed |
| Food | EMA 2008, pp. 19–20/51 | "co-administration with food delays absorption of the active substance" | observed |

Representation: first-order absorption from the gut lumen into portal blood; fraction absorbed carried as the 2.0e scenarios (1.0, 0.95, 0.90); no first-pass loss in the liver (supported in vitro, not measured in vivo). A mechanistic gut model (segments, dissolution, transit) is not supported: the drug dissolves readily and no regional absorption data are attached. Fasted state only.

The absorption rate is the one parameter that can only come from data already seen (time of peak). The plan must say so, as time-course plan v2 did.

---

## 3. Parameters and where each value comes from

### 3.1 Physiology: ICRP Publication 89, women and men separately

All values below are **reference** values. Locations: printed page, then PDF page of the attached file. Quotes are the table row as printed, with the column order the table uses. No sex multiplier is used anywhere: each column is read from the source.

**Body size.** Table 2.9, p. 19 (PDF 33). Column order in the source: Male, Female.

| Quantity | Women | Men | Quote (row "Adult") |
|---|---|---|---|
| Height (cm) | 163 | 176 | "Adult 176 163 73 60 1.90 1.66" |
| Mass (kg) | 60 | 73 | same row |
| Surface area (m²) | 1.66 | 1.90 | same row |

**Heart and blood.**

| Quantity | Women | Men | Location | Quote |
|---|---|---|---|---|
| Cardiac output (L/min) | 5.9 | 6.5 | Table 2.39, p. 28 (PDF 42) | "Adult 6.5 5.9" (Male, Female) |
| Total blood volume (mL) | 3900 | 5300 | Section 7.3, paragraph 309, p. 138 (PDF 152) | "reference values for total blood volume (5300 ml for adult males and 3900 ml for adult females)" |
| Plasma volume (mL) | 2400 | 3000 | Table 2.12, p. 20 (PDF 34) | "Plasma 3000 2400" (Male, Female) |
| Red cell volume (mL) | 1500 | 2300 | Table 2.12, p. 20 (PDF 34) | "Red blood cells 2300 1500" |
| Red cells, share of blood volume | about 38% (37–48%) | about 43% (42–52%) | paragraph 309, p. 138 (PDF 152) | "red blood cells represent about 43% (42–52%) of the total blood volume in adult males and about 38% (37–48%) in adult females" |
| Blood mass (g) | 4100 | 5600 | Table 2.8, p. 18 (PDF 32) | "Blood 290 530 1500 2500 4800 3500 5600 4100" (last two: adult M, F) |

**Organ masses (g).** Table 2.8, pp. 18–19 (PDF 32–33). The last two numbers of each quoted row are adult male, then adult female. ICRP 89 gives masses, not volumes.

| Organ or tissue | Women | Men | Quote (row as printed) |
|---|---|---|---|
| Kidneys (2) | 275 | 310 | "Kidneys (2) 25 70 110 180 250 240 310 275" |
| Liver | 1400 | 1800 | "Liver 130 330 570 830 1300 1300 1800 1400" |
| Small intestine, wall | 600 | 650 | "Wall 30 85 220 370 520 520 650 600" |
| Small intestine, contents | 280 | 350 | "Contents 56 93 117 163 280 280 350 280" |
| Stomach, wall | 140 | 150 | "Wall 7 20 50 85 120 120 150 140" |
| Heart, tissue only | 250 | 330 | "Heart – tissue only 20 50 85 140 230 220 330 250" |
| Lung, tissue only | 420 | 500 | "Lung – tissue only 30 80 125 210 330 290 500 420" |
| Brain | 1300 | 1450 | "Brain 380 950 1310/1180 1400/1220 1420 1300 1450 1300" |
| Skeletal muscle | 17 500 | 29 000 | "Muscle, skeletal 800 1900 5600 11 000 24 000 17 000 29 000 17 500" |
| Adipose tissue | 22 500 | 18 200 | "Adipose tissue 930 3800 5500 8600 12 000 18 700 18 200 22 500" |
| Skin | 2300 | 3300 | "Skin 175 350 570 820 2000 1700 3300 2300" |
| Total skeleton | 7800 | 10 500 | "Total skeleton 370 1170 2430 4500 7950 7180 10 500 7800" |
| Marrow, active | 900 | 1170 | "Marrow, active 50 150 340 630 1080 1000 1170 900" |
| Spleen | 130 | 150 | "Spleen 9.5 29 50 80 130 130 150 130" |
| Pancreas | 120 | 140 | "Pancreas 6 20 35 60 110 100 140 120" |
| Total body (kg) | 60 | 73 | "Total body (kg) 3.5 10 19 32 56 53 73 60" |

**Regional blood flow.** Table 2.40, p. 29 (PDF 43); the same values are in the Section 7.7.2 table, p. 142 (PDF 156). Column order in the source: Male, Female. Basis: "Normal values for regional blood volumes and the distribution of cardiac output have been proposed on the basis of an extensive review and analysis of the literature (Williams and Leggett, 1989; Leggett and Williams, 1991, 1995)" (paragraph 318, p. 142). The mL/min columns are **derived**: cardiac output × percentage.

| Organ or tissue | Women, % of cardiac output | Women, mL/min (derived) | Men, % of cardiac output | Men, mL/min (derived) | Quote |
|---|---|---|---|---|---|
| Kidneys | 17 | 1003 | 19 | 1235 | "Kidneys 19 17" |
| Liver, arterial | 6.5 | 383.5 | 6.5 | 422.5 | "Liver 6.5 (arterial) 6.5 (arterial)" |
| Liver, total | 27.0 | 1593 | 25.5 | 1657.5 | "25.5 (total) 27.0 (total)" |
| Small intestine | 11 | 649 | 10 | 650 | "Small intestine 10 11" |
| Large intestine | 5.0 | 295 | 4.0 | 260 | "Large intestine 4.0 5.0" |
| Stomach and oesophagus | 1.0 | 59 | 1.0 | 65 | "Stomach and oesophagus 1.0 1.0" |
| Pancreas | 1.0 | 59 | 1.0 | 65 | "Pancreas 1.0 1.0" |
| Spleen | 3.0 | 177 | 3.0 | 195 | "Spleen 3.0 3.0" |
| Brain | 12 | 708 | 12 | 780 | "Brain 12 12" |
| Coronary tissue | 5.0 | 295 | 4.0 | 260 | "Coronary tissue 4.0 5.0" |
| Skeletal muscle | 12 | 708 | 17 | 1105 | "Skeletal muscle 17 12" |
| Fat | 8.5 | 501.5 | 5.0 | 325 | "Fat 5.0 8.5" |
| Skin | 5.0 | 295 | 5.0 | 325 | "Skin 5.0 5.0" |
| Skeleton | 5.0 | 295 | 5.0 | 325 | "Skeleton 5.0 5.0" |
| All other tissues | 1.92 | 113 | 1.39 | 90 | "All other tissues 1.39 1.92" |

Checks done in this draft on the table (derived):
- Each column sums to 100.0% when the liver is counted by its arterial share only (the portal organs are listed separately).
- **Men:** arterial 6.5 + portal organs (stomach and oesophagus 1.0, small intestine 10, large intestine 4.0, pancreas 1.0, spleen 3.0 = 19.0) = 25.5, equal to the printed total.
- **Women: the same sum is 6.5 + 21.0 = 27.5, but the table prints 27.0.** The women's column is not internally consistent by 0.5 percentage points. The extract must record this and the plan must say which figure is used. It is not a transcription error in this draft: both tables in the PDF print 27.0.

**Regional blood volume.** Table 2.14, p. 21 (PDF 35), % of total blood volume, Male then Female.

| Organ or tissue | Women | Men | Quote |
|---|---|---|---|
| Kidneys | 2.0 | 2.0 | "Kidneys 2.0 2.0" |
| Liver | 10 | 10 | "Liver 10 10" |
| Small intestine | 3.8 | 3.8 | "Small intestine 3.8 3.8" |
| Skeletal muscle | 10.5 | 14 | "Skeletal muscle 14 10.5" |
| Fat | 8.5 | 5.0 | "Fat 5.0 8.5" |
| Brain | 1.2 | 1.2 | "Brain 1.2 1.2" |

**Kidney function.**

| Quantity | Women | Men | Location | Quote |
|---|---|---|---|---|
| Glomerular filtration rate | **to be sourced** (ICRP 89 gives no value for women) | about 125 mL/min, "middle-aged adult male" | Section 8.3, paragraph 380, p. 159 (PDF 173) | "In a middle-aged adult male, the glomerular filration rate (GFR) averages about 125 ml/min" [spelling as printed] and "is lower on average in females than males" |
| Renal plasma flow | 622 mL/min (derived: 1003 × (1 − 0.38)) | 704 mL/min (derived: 1235 × (1 − 0.43)); ICRP's own text: "about 700 ml/min" for "the young adult male" | Tables 2.39, 2.40, paragraph 309; paragraph 380 | as above |

The platform's kidney input is creatinine clearance from the record or the slider, not a reference GFR, so the missing value for women does not block the model. It does block any statement that a "reference woman" has a particular filtration clearance.

**Gut transit** (only if a gastric-emptying step is wanted). Table 2.37, p. 28 (PDF 42): "Liquids – non-caloric 10 mins 30 mins 30 mins 30 mins 30 mins" (adult males and females both 30 minutes); "Total diet 75 mins 70 mins 70 mins 70 mins 95 mins" (adult males 70, females 95 minutes); small intestine 4 h in every column.

**Not in ICRP 89, to be sourced:**
- Tissue densities, needed to turn masses into volumes. The only density quoted where this draft looked is for blood: "Assuming a specific gravity of blood of 1.06" (p. 91, PDF 105). To be sourced from ICRP Publication 23 or ICRP 89 Section 4, by table.
- Tissue composition (water, neutral lipid, phospholipid fractions), needed by the partition methods. To be sourced from Poulin & Theil 2002 and Rodgers & Rowland 2006, by table.
- Lumping rule: which ICRP tissues form the fast and slow lumps. A design choice, fixed in the plan, not a sourced value.

**Existing extract.** `reference_physiology_icrp89_v1.json` holds three values for men only (cardiac output 6.5, kidneys 19%, red cells 43%). All three match the PDF. Its `applies_to` says "Reference adult male". The values above need a new versioned file with a new pin, as `CLAUDE.md` requires. The 10 November review recorded the ICRP file as "present but scanned; not checked"; the file has a usable text layer.

### 3.2 Drug-specific values

| Parameter | Value | Source, location | Quote | Type; limits |
|---|---|---|---|---|
| Molecular weight | 259.25 g/mol | FDA 2005, PDF p. 6, printed p. 5 (checked by eye) | "the molecular weight is 259.25 grams per mole" | observed |
| Plasma protein binding, in vitro | 23% (myeloma), 29% (healthy) | EMA 2008, p. 20/51 | "The mean binding was 23 and 29% in plasma from myeloma patients and healthy volunteers, respectively. No concentration dependency was observed." | observed; "semi-racemic" radiolabel, ultrafiltration, 30–10000 ng/ml |
| Fraction unbound | 0.77 (myeloma), 0.71 (healthy) | derived: 1 − bound fraction | — | derived |
| Fraction unbound, ex vivo | about 0.60 | **not in the attached sources.** The repository cites Chen 2007 (`lenalidomide_pathway_unbound_fraction_assessment_v1.json`) | — | observed, per the repository; not re-read here |
| Blood-to-plasma ratio | 0.931 ± 0.020 (AUC); 0.963 ± 0.028 (Cmax) | Chen 2012, Table 2, p. 794 | "AUC∞ ratio 0.923 ± 0.017 NA 0.931 ± 0.020"; "Cmax ratio 0.983 ± 0.074 NA 0.963 ± 0.028" (columns: lenalidomide, plasma radioactivity, whole blood; ratio to plasma radioactivity) | observed; **total radioactivity, 6 healthy men, one dose** |
| Red-cell share | 44–36% of blood radioactivity | Chen 2012, p. 793 | "radioactivity into erythrocytes averaged from 44 to 36% of the whole blood radioactivity from 0.25 to 12 h postdose. These values were comparable to the mean hematocrit (42–43%) for these subjects." | observed; men only |
| Apparent volume, V/F | 75.8 ± 7.3 L | Chen 2012, Table 2, p. 794 | "V/F (l) 75.8 ± 7.3 75.1 ± 10.6 NC" | observed; 6 men, mean weight 83.95 kg |
| V/F per kg | 0.90 L/kg | derived: 75.8 ÷ 83.95 | — | derived; apparent (÷ F) |
| Apparent volume, Vz/F, normal kidney function | 58 (15) L | EMA 2008, Table 4, p. 21/51 | "Vz/F (l) 58 (15) 51 (13) 62 (15) 41 (8) 52 (8) 86 (14)" | observed, mean (SD), n = 7 |
| Apparent volume, range | "50-200 l" | EMA 2008, p. 20/51 | "The apparent oral volume of distribution was different between doses and studies but may be in the order 50-200 l." | observed, regulator's summary |
| Vz/F, healthy against patients | 86 L against 56 L | FDA 2005, FDA Table 3, PDF p. 14, printed p. 13 (checked by eye) | table row Vz/F (L): 86 (healthy, study 1398/142); not reported (PK-003); 56 (patients); +54 (% change) | observed |
| Central volume, population model | 48.3 L | TGA CER, "Population pharmacokinetics" | "The typical value of lenalidomide central volume of distribution (V2/F) at the median body weight of 76.3 kg for a male subject was 48.3 L." | model estimate (sponsor); the covariate equation is an image, not read |
| Apparent clearance, healthy young men | 318 ± 41 mL/min | Chen 2012, Table 2, p. 794 | "CL/F (ml/min) 318 ± 41 294 ± 35 NC" | observed |
| Apparent clearance, normal group of the renal study | 207 (59) mL/min | EMA 2008, Table 4, p. 21/51 | "CL/F (ml/min) 207 (59) 166 (49) 71 (12) 52 (101) 39 (7) 62 (9)" | observed; the severe SD "(101)" is a known misprint (review F26) |
| Renal clearance | 261 ± 30 mL/min | Chen 2012, p. 793 | quoted in 2.3 | observed; radioactivity-based |
| Unchanged in urine | about 85%; 81.74 ± 3.61% | EMA 2008, p. 20/51; TGA CER | quoted in 2.3 | observed |
| Fraction absorbed | at least about 0.90 | Chen 2012, p. 796 | quoted in 2.5 | observed bound |
| Half-life | 2.78 ± 0.40 h | Chen 2012, Table 2, p. 794 | "t1/2 (h) 2.78 ± 0.40 2.97 ± 0.36 3.05 ± 0.38" | observed |
| Parent share of plasma radioactivity | 92% of AUC | Chen 2012, p. 793 | "lenalidomide comprised 98% of Cmax and 92% of AUC for the total plasma radioactivity" | observed |
| The same, from metabolite profiling | 77.44% of AUC | TGA CER, "Metabolic profiles" | "In plasma, lenalidomide was the predominant component (77.44% of AUC of the total plasma radioactivity)" | observed; **differs from the line above** (different method: profiling of pooled samples against assay ratio). To be reconciled. |
| Sex effect | on volume, limited; on clearance, none found | TGA CER, "Population pharmacokinetics" | "Body weight and sex had a limited effect on the volume of distribution (V2/F), but had no effect on CL/F" | sponsor's model; 147 subjects, 69% male |
| Sex effect, earlier | not studied | FDA 2005, PDF p. 4 (OCR only) | "The effects of gender on the pharmacokinetics of lenalidomide have not been studied." | — |
| **logP** | **to be sourced** | not in any attached source | The FDA review says only "highly hydrophilic" (PDF p. 15) | — |
| **pKa** | **to be sourced** | not in any attached source | The only indirect sign is the pH-dependent solubility quoted in 2.5 | — |

### 3.3 Tissue-to-plasma partitioning: observed data against prediction methods

**Observed.** A Kp is measured by sampling tissue and plasma together at steady state or over a full time course. For lenalidomide the attached sources hold no such measurement in humans, and none with numbers in animals (section 4).

**Prediction methods, briefly.**

| Method | Idea | Inputs from the drug | What it cannot see |
|---|---|---|---|
| **Poulin & Theil** (2000; 2002) | The drug dissolves in each tissue's water, neutral lipids and phospholipids in proportion to its lipophilicity; binding in plasma and tissue is scaled from the unbound fraction. | logP (an oil:water value for fat), fraction unbound | Ionisation effects on binding; transporters; slow membrane passage |
| **Rodgers & Rowland** (2005; 2006) | Unbound, un-ionised drug distributes into intra- and extracellular water and lipids. Ionised strong bases also bind acidic phospholipids. Acids, weak bases and neutrals bind albumin or lipoprotein in tissue fluid. | logP, pKa (it selects the equation), fraction unbound, blood-to-plasma ratio (for red-cell binding of bases) | Transporters; slow membrane passage |

Both give an equilibrium, passive, perfusion-limited Kp. For a hydrophilic, weakly bound drug, both tend to return values close to each tissue's water content, so the predicted organs would differ mainly by water fraction. That is a statement about the methods, not a result for lenalidomide.

**Do the attached sources give the four inputs?**

| Input | Needed by | Given by the attached sources? | Action |
|---|---|---|---|
| logP | both | **No** | To be sourced from a primary measurement: the originator's quality documentation (EMA Revlimid assessment report, quality section; FDA chemistry review for NDA 21-880), by page. A value copied from a database must be traced to its origin and marked measured or calculated. |
| pKa | Rodgers & Rowland | **No** | As above. The ionisation class at pH 7.4 decides which equation applies, so this is not optional. |
| Fraction unbound | both | **Yes**: 0.77 or 0.71 in vitro (derived from EMA 2008, p. 20/51) | Decide in the plan which value; the ex vivo 0.60 is in the repository, not in the attached files. |
| Blood-to-plasma ratio | Rodgers & Rowland; also the conversion between plasma and blood clearance | **Yes, with limits**: 0.931 (Chen 2012, Table 2), total radioactivity, men | For women no measurement exists. The plan must state the rule (the same ratio, or the same cell-to-plasma partition with women's haematocrit) as an assumption. |

**What could check a prediction.**
- *The whole-body volume.* The predicted steady-state volume is the sum of Kp × volume over organs. But humans have only apparent volumes after oral dosing (Vz/F, V/F); there is no intravenous study ("Absolute bioavailability has not been determined in humans"). A true steady-state volume is therefore not observed. Agreement within the 50–200 L spread would be weak evidence.
- *Animal tissue data.* A mouse study with measured tissue concentrations exists but is not attached (section 4, row 12). It could test the method in the mouse. It cannot show that a human organ value is right.

**Recommendation.** Do not predict organ Kp values until logP and pKa are pinned from a primary source. Until then, the organ-level model is the lumped form of 2.2, whose lump parameters are tied to the observed apparent volume and are not organ values.

---

## 4. Tissue-distribution evidence for lenalidomide

### 4.1 Item by item

| # | Evidence | Source, location | Quote | Species | Can support | Cannot support |
|---|---|---|---|---|---|---|
| 1 | Radiolabel, oral | EMA 2008, p. 12/51 | "The highest concentration of radioactivity following oral administration of [14C]-lenalidomide to rat was in the kidney. Distribution to the brain was extremely low. Distribution to the foetus was limited after oral administration to pregnant rats" | Rat | A ranking: kidney highest, brain very low | Any number; parent drug as distinct from metabolites; humans |
| 2 | Whole-body autoradiography | EMA 2008, p. 14/51 | "In a whole body autoradiography study in the rat, tissues levels were comparable to the plasma values." | Rat | That tissue levels are of the order of plasma, as a general statement | Any organ-specific value; which tissues; time course |
| 3 | Volume of distribution across species | EMA 2008, p. 12/51 | "The volume of distribution observed in all species tested indicated an extensive distribution into tissues" | Rat, dog, monkey (named for bioavailability) | Drug leaves the blood | Where it goes |
| 4 | Protein binding | EMA 2008, pp. 12, 20, 21/51; FDA 2005, PDF p. 15 (checked by eye) | "The plasma protein binding is low in all species including humans (19% to 29%)"; "Mean plasma protein binding was 23%, in human subjects with multiple myeloma and 29% in healthy human volunteers." | Human and animals | Fraction unbound for filtration and for partition methods | Binding in tissue |
| 5 | Apparent volume | see 3.2 | see 3.2 | Human | Size of the lumped distribution space, divided by F | Distribution among organs; a true steady-state volume |
| 6 | Blood cells | Chen 2012, p. 796 | "lenalidomide, as the primary radioactive component in circulation, is distributed nearly equally between cellular and plasma components of whole blood" | Human, 6 men | Plasma represents blood; a blood-to-plasma ratio near 1 in men | Women; patients; parent drug alone (total radioactivity) |
| 7 | Semen, radiolabel, single dose | Chen 2012, p. 793 and p. 796 | "The mean radioactive concentration in semen collected between 2 and 3 h postdose was 492 ± 20.7 ngEq/g and similar to the radioactive Cmax equivalent observed in plasma. The semen concentration of radioactivity at 72 h time point was 31.7 ± 5.6 ngEq/g."; "Only a very small amount of the radioactivity (0.0062% of the dose; 1.479 µg equivalent of [14C]-lenalidomide) was recovered from semen."; the 2–3 h samples were "composed of lenalidomide (representing approximately half of the total sample radioactivity)" and metabolites | Human, 6 men | Drug-related material reaches a male reproductive fluid at a concentration of the order of the plasma peak; about half was parent drug | A tissue concentration in testis or prostate; a Kp (one sample per man, a fluid mixed from several glands); anything in women |
| 8 | Semen, the same study as reported to the TGA | TGA CER, under "Metabolism and excretion", study CC-5013-PK-006, "Mass balance results" | "The geometric mean radioactive concentration equivalent in semen collected between 2 and 3 hours post-dose (453.6 ngEq/g) was similar to the radioactive Cmax equivalent observed in plasma (415.6 ngEq/g)." | Human | As row 7 | As row 7. Note 453.6 (geometric mean) against 492 (arithmetic mean), and 0.0059% against 0.0062% of the dose: different statistics of the same data. |
| 9 | Semen, multiple doses (CC-5013-PK-008) | TGA CER, heading "Study CC-5013-PK-008" | "The sponsor stated that the lenalidomide concentrations in semen (304 to 823 ng/mL) at 2 hours post-dose approximated the therapeutic levels in plasma."; "Lenalidomide was undetectable in semen 3 days after discontinuation of the drug. The time course of lenalidomide concentration in semen roughly mirrored that in plasma." | Human, 24 men | Parent drug in semen; decline roughly parallel to plasma | As row 7. The table of values (Table 9) is an image and was not read. |
| 10 | Excreta | Chen 2012, p. 796 | "Total recovery of the [14C]-radioactivity averaged 94.3% of the administered dose, with mean contributions of 90.3, 3.95 and 0.0062% from urine, feces and semen, respectively." | Human, 6 men | Mass balance; no long retention in tissue | Where the unrecovered 5.7% was |
| 11 | Membrane permeability | FDA 2005, PDF p. 15, printed p. 14 (checked by eye) | "showed low permeability in the Caco-2 system. More consistent with its lipophilicity, lenalidomide showed high permeability in the PAMPA system." | In vitro | Doubt about treating every tissue as perfusion-limited | A permeability value for any tissue |
| 12 | Mouse tissue concentrations (**not attached**) | Rozewski et al. 2012, *AAPS J* 14:872–882. As described in the abstract of Hughes et al. 2019 (*Cancer Chemother Pharmacol* 84:1073–1087) | "Tissue samples included plasma, liver, lung, heart, spleen, kidney, hind limb muscle, and brain."; "brain tissue concentrations in mice are 0.9–2.3% of plasma concentrations" | Mouse | Would give measured animal tissue-to-plasma ratios for seven tissues | Humans. **Abstract only, not pinned; values not to be used until the full text is read under a plan.** |
| 13 | Monkey cerebrospinal fluid (**not attached**) | PubMed record 22109830 | "Lenalidomide was detected in the CSF of 2 of 3 animals, with a CSF penetration of 11% in each." | Rhesus monkey, 3 animals | Low entry to cerebrospinal fluid in a primate | Brain tissue; humans. **Abstract only, not pinned.** |
| 14 | Semen, published version of row 9 (**not attached**) | Chen et al. 2010, *J Clin Pharmacol*, doi 10.1177/0091270009355157 | "The mean lenalidomide concentration in semen was 478 ng/mL at 2 hours and 10.0 ng/mL at 24 hours, which was higher than was the corresponding drug concentration in plasma (219 ng/mL at 2 hours and undetectable at 24 hours)" | Human, 24 men | The paired plasma value that the TGA text omits | As row 7. **Abstract only, not pinned.** |

Foetal, placental and milk findings appear in the sources (rows 1 and 2 mention the foetus). They are out of scope and are not used.

### 4.2 Per organ: what kind of evidence exists

"Attached" means the five attached sources. A cell marked "located" means a study was found by search but is not attached or pinned.

| Organ, tissue or fluid | Observed in humans | Animal only | Predicted only | Nothing |
|---|---|---|---|---|
| Plasma | **Yes** (concentration over time) | | | |
| Whole blood, red cells | **Yes** (total radioactivity; men) | | | |
| Urine | **Yes** (amounts over time) | | | |
| Faeces | **Yes** (amount of radioactivity; not a tissue) | | | |
| Semen | **Yes** (men; a fluid, single samples) | | | |
| Dialysate | **Yes**, as amount removed by one session (repository, EMA 2013 extract; not attached) | | | |
| Kidney tissue | | **Yes** (rat: highest radioactivity, no number; mouse data located) | | |
| Brain | | **Yes** (rat: "extremely low"; mouse and monkey data located) | | |
| Liver, lung, heart, spleen, skeletal muscle | | General rat statement only ("tissues levels were comparable to the plasma values"); organ-specific mouse data located | **Yes**, if a method is run | |
| Adipose, skin, bone, gut wall, pancreas | | General rat statement only | **Yes**, if a method is run | |
| **Bone marrow** (site of action in myeloma) | | | Could be predicted | **Nothing attached** |
| Lymph nodes, tumour tissue | | | | **Nothing** |
| Testis, prostate | | | | **Nothing** (semen is not tissue) |
| Ovary, uterus, breast | | | | **Nothing**; and out of scope |
| Cerebrospinal fluid | | Monkey (located, abstract only) | | |

Two consequences for the picture:
- The organ the reader most wants to see for a myeloma drug, the bone marrow, is the one with no data of any kind.
- Every human distribution study (mass balance, blood cells, semen) was done in men. For women, organ-level distribution is unobserved at every level.

---

## 5. How the model would be checked

### 5.1 Data that could test it, and whether the platform has seen them

| Dataset | What it could test | Seen by the platform? | Role a check could have |
|---|---|---|---|
| CC-5013-PK-001 (EMA 2008 Table 4; EMA 2013; Chen 2007): plasma by kidney-function group; % of dose in urine per group | Peak, half-life and AUC by band; urine share by band | **Yes.** Built from (normal group), tuned on (time course), checked not blind (ledger v6) | Consistency only |
| The same study, end-stage groups on and off dialysis | Non-renal clearance; dialysis removal | **Yes** (2.0c; dialysis panel) | Consistency only; residual kidney function unknown |
| Bridoux 2016 (myeloma, by kidney function) | AUC, peak, half-life at steady state | **Yes** | Consistency only |
| Kim 2026 (myeloma) | Clearance by group; its distribution parameters | **Yes**; also built from (time course v2) | Consistency only |
| Chen 2012 mass balance: cumulative urine at 12 h ("approximately 84%") and 24 h ("88.5%"), final 90.3%; unchanged 82%; plasma Table 2 (peak 413 ± 77 ng/ml, AUC∞ 1,319 ± 162 h·ng/ml, half-life 2.78 h, CL/F 318, V/F 75.8) | **Urine recovery over time**, which no current check uses; the plasma curve in young healthy men; blood against plasma | **Yes.** The file is pinned twice (blood-to-plasma ratio; absorption bounds, built from). It was read in full by the 10 November review and by this draft. | Consistency only. It is "seen, never fitted" for the plasma and cumulative-urine endpoints. |
| TGA CER: PK-008 plasma after 25 mg for 4 days; sponsor's population model | Steady-state plasma; central volume | **Yes** (file used for exposure–safety; text read) | Consistency only |
| FDA 2005 review: healthy single doses 5–400 mg; urine "57 — 79% of the dose" within 48 h (PDF p. 16, OCR only) | Dose range | **Yes** (file in the owner's folder; cited in `DOSE_OPTIMISATION.md`) | Consistency only |
| Mouse tissue study (row 12) | The partition method, in the mouse | Not pinned. **Abstract-level statements were read for this draft on 12 November 2026**, including one numeric range for brain. | At best "prespecified, outcome partly known": the published mouse PBPK abstract already reports which tissues fitted. |

**No blind check on human data is possible.** This matches the ledger ("Every lenalidomide renal-impairment dataset available is seen"). A plan for the organ-level model must use the roles `checked_not_blind` or `tuned_on`, and must not pass through `assert_blind_allowed`.

**An expectation, disclosed now so that it cannot count as a finding later.** Apparent clearance in the mass-balance study (318 mL/min, young healthy men) is about 1.5 times that of the calibration group (207 mL/min; derived ratio 1.54). A model calibrated on CC-5013-PK-001 will therefore predict too much exposure and too slow a urine recovery for the mass-balance subjects unless their kidney function is entered, and their creatinine clearance is not reported in the article. The author of this draft has seen both numbers.

### 5.2 What must be fixed before anything is run

1. **Structure and equations:** the compartments of 2.2 and no others; whether lump 7 exists.
2. **Physiology file:** the new ICRP extract for women and men, pinned; the rule for the women's liver-flow inconsistency; the lumping rule.
3. **Which body is run against which data.** CC-5013-PK-001 groups contain women and men (Chen 2007 Table I, in the repository). The plan must fix how a mixed group is represented: for example a women's run and a men's run weighted by the group's counts. No average body.
4. **Drug inputs with their sources:** fraction unbound (which of 0.77, 0.71, 0.60); blood-to-plasma ratio for men; the stated assumption for women.
5. **The renal clearance conflict of 2.3:** which value calibrates the model and why. Changing it would be a new clearance model with its own plan, not part of this one.
6. **Bioavailability scenarios:** 1.0, 0.95, 0.90, as in 2.0e.
7. **Partition:** either "lumped only, no organ Kp", or the method, its version, the tissue-composition table and the pinned logP and pKa. A rule that no Kp is adjusted to improve the plasma fit.
8. **Every fitted parameter, named, with the data it is fitted to.** The honest minimum: lump volume or Kp and distribution-flow fraction, tuned on the normal group only.
9. **Endpoints and one acceptance rule.** The 10 November review (F03) found three different rules behind the word "consistent". This plan should use one, state it beside each result, and report a result within a few per cent of the limit as "indeterminate".
10. **Numerical tests,** written and run on synthetic values before the lock (the `CLAUDE.md` rule, F18):
    - mass is conserved at every time;
    - organ flows sum to cardiac output; volumes sum to the body;
    - renal extraction equals the value in `body-map-view-v2` at steady state;
    - **collapse test:** with instant tissue equilibration the model reproduces the one-compartment time course v1;
    - women's and men's runs differ exactly where the physiology differs, and nowhere else.
11. **The decision rule:** what the map shows for each possible outcome, written before the run.
12. **Ledger and findings entries;** a decision record in `docs/decisions/` (required for a new scientific framework).

### 5.3 What would count as failing

**Software failure (stops everything):** any test in point 10 fails.

**Scientific inconsistency (shown on the page, not repaired by tuning):**

| Endpoint | Failing means | Note |
|---|---|---|
| Plasma peak, by band | Outside the pre-set interval of the observed group value | v1's peak is too low in every group. **If the organ model is no better than v1 without fitting anything new, that is a result and must be said:** the model adds a picture, not accuracy. |
| Half-life and AUC, by band | Outside the interval | The moderate and severe gaps come from the clearance model and will persist. Declared in advance. |
| Share of dose in urine, by band | Outside the observed range | Moderate band: 67% against 38–42% is already known and will persist. |
| Cumulative urine at 12 h and 24 h, healthy men | Away from "approximately 84%" and "88.5%" (total radioactivity) by more than the pre-set margin | New endpoint. Compares model parent drug with observed total radioactivity; the plan must fix the conversion (parent drug was more than 90% of the radioactivity in urine: Chen 2012, abstract, p. 789, where the text layer prints ">" as "["). |
| Whole-body distribution | Model steady-state volume ÷ F outside the observed apparent volumes | Weak: only apparent volumes exist. |
| Organ ranking, if Kp values are predicted | The prediction contradicts the animal observations: kidney not among the highest, or brain not far below plasma | A passive method is expected to fail for the brain. The brain then carries "prediction contradicted by animal data", and no brain value is shown. |

**What no outcome can show.** Passing every row means the model is consistent with human plasma and urine data that were already known. It says nothing about whether any organ concentration is right. That sentence belongs on the page.

---

## 6. What the body map could then honestly show, and what it must not

### 6.1 Could show

- **Reference physiology, for a woman and for a man:** organ blood flow, organ mass, blood volume, each labelled "ICRP 89 reference woman" or "reference man" with table and page.
- **Human observations, on the structures they belong to:** the plasma curve with its data; cumulative urine; the red-cell share; faecal recovery; in the male body, the semen observation.
- **The lumped model over time:** share of the dose in gut lumen, blood, kidneys, rest of body, urine and other routes, summing to 100%.
- **Evidence class per organ:** the table of 4.2, on the organ cards.
- **Only after sourced inputs and a locked check:** predicted organ partition, switched off by default, with its label.

### 6.2 Display rules

| # | Rule |
|---|---|
| R1 | **Every organ carries one of four evidence classes**, shown by outline and a text tag, never by colour alone: *Observed in humans* (solid outline); *Animal only* (dashed outline, species named); *Predicted, not measured* (hatched); *No data* (grey; the card says "No data for this organ" and shows no number). |
| R2 | **No organ concentration is ever shown as observed** unless a human measurement in that organ is quoted with source and location. Today that list is: plasma, whole blood, urine, faeces, semen. |
| R3 | **A predicted partition or concentration always appears with its label:** the method and version, the four inputs with their sources, and the sentence "Predicted from the drug's chemistry. No measurement in this human organ exists." It is never the default view. |
| R4 | **No heat map across organs.** A continuous colour scale would place observed, animal, predicted and empty organs on one visual scale. Numbers go in cards and tables. |
| R5 | **A lump is not painted onto organs.** "Rest of body" is one bar or one box. Muscle, fat, skin and the others stay grey with "part of the lumped rest of body; not modelled separately". |
| R6 | **Animal findings stay in words and keep their species:** "In rats, radioactivity was highest in the kidney." No conversion to a human concentration. |
| R7 | **The body matches the physiology.** Women's reference values are drawn only on a female body, men's on a male body. If the pair does not match, the page refuses to draw, as it does for a changed checksum. No sex multiplier anywhere. |
| R8 | **Drug evidence in women is stated as missing where it is:** "Distribution studies (mass balance, blood cells, semen) were done in men only." |
| R9 | **Bone marrow shows "No data"** in plain view, because a reader will look there first. |
| R10 | **Brain shows "Animal only: very low in rats"** and no number, until a pinned source supplies one. |
| R11 | **Semen** appears only on the male body, as an observation card: the quoted finding, "a fluid, not a tissue; not a model output". No advice text. |
| R12 | **One quantity per visual scale.** Clearance (mL/min), blood flow (mL/min), amount (% of dose) and concentration (ng/mL) never share a width or colour scale. This extends the existing rule that blood-flow dots never look like drug. |
| R13 | **Status is inherited.** An organ-level output carries the weakest status among its inputs: the band's status from 2.0e, the time course's peak warning, the Kp class. |
| R14 | **Model constructs are named as such:** "not yet absorbed", "rest of body" and "other routes" keep the words "model construct" or "organ not assigned". |
| R15 | **Wording stays typical and impersonal:** "the model's typical value for a reference woman", never "your kidney" or "this patient's liver". The banner, the run record and both false flags stay. |
| R16 | **Enforced in code, not only in text:** a view is not built if any organ value lacks an evidence class and a source; context organs still cannot carry a value; a test fails if a predicted value is rendered without the R3 label. |

### 6.3 Must not show

- An organ concentration presented, coloured or animated as if measured.
- Predicted partitioning without the R3 label, or as the default view.
- Drug "arriving" in bone marrow, tumour or lymph nodes.
- A female body driven by men's physiology, or the reverse.
- Kidney "tissue concentration" derived from renal clearance. Clearance is a rate of removal, not an amount in tissue.
- Any statement about dose, risk or an individual.

---

## 7. Anatomy review of the current body map

Read from code and data at the commit above; no page was rendered. Coordinates are those of the pinned files ("+y up; body left is +x"). Severity: **A** = anatomically wrong or likely to mislead; **B** = imprecise naming or labelling; **C** = minor.

| # | Sev. | File and line | Issue | Suggested fix |
|---|---|---|---|---|
| 1 | A | `intelligence_store/body_map_paths.py:114–118` (and docstring `:13–15`); `landscape_ui/body_map_pages.py:127–128, 154` | **Absorption is drawn as a straight line from the middle of the small intestine to the inferior vena cava at renal-artery level.** Intestinal blood drains to the portal vein and through the liver; the liver "is drained by the hepatic veins into the inferior vena cava near the heart" (ICRP 89, paragraph 246, p. 119). The drawn end point is far below that junction. The docstring records the shortcut ("It does not pass through the liver"), but the picture shows a vessel connection that does not exist. | Route the path along the Atlas "hepatic portal vein" (present in the manifest's vessel labels) to the liver, then by the hepatic veins to the vena cava. Label: "by the portal vein through the liver; no loss in the liver is modelled". Until the liver is a model node, end the dashed path at the portal vein. |
| 2 | A | `body_map_paths.py:105–107`; `body-map-viewer.js:405–413`; `body_map_pages.py:151`; `body-map-viewer.js:528` | **Filtration and secretion are drawn as two tubes inside the renal artery,** from the aorta to the kidney, with the label "Into the kidneys: filtration … + secretion … mL/min" anchored at the aorta. Neither process happens in the artery. Filtration is "from the glomerular capillaries into Bowman's space" (ICRP 89, paragraph 379, p. 159), in the cortex; secretion is from the peritubular capillaries into the tubule. A clearance drawn as a tube in an artery reads as "this much flows in". | Let the artery carry only the blood layer. Draw filtration and secretion as two short strands that start inside the cortex and run through the medulla to the renal pelvis. Anchor the label at the kidney: "Cleared by the kidneys". The planned nephron zoom would complete this. |
| 3 | B | `body_map_paths.py:99` | The kidney end point is the centre of the capsule's bounding box, which lies near the renal sinus, not in the filtering cortex. (`np.vstack([...])` of a single array also does nothing.) | Use a point in the cortex for process strands (fix 2); keep the centre only for blood paths. |
| 4 | B | `intelligence_store/body_map.py:52`; `body_map_pages.py:93`; `landscape_ui/templates/landscape_body_map.html:66` | **One node, three names:** "Digestive tract (oral dose)" with the UBERON term for the whole digestive tract; "Small intestine: oral dose" on the card; "Gut" in the diagram. Only the small intestine is drawn as a simulation organ. | One name, "Small intestine (site of absorption)", with the UBERON term for the small intestine (to be confirmed against the ontology). |
| 5 | B | `intelligence_store/data/body_map_assets_v1.json`, `sources.innerscene_stomach.placement` ("approximate, by eye"), part `stomach` (class `context`) | An oral dose passes the stomach, but the stomach is a context organ, not from the reference body, and placed by hand. Its bounding box (x −0.008 to 0.128, y 0.270 to 0.444, z −0.054 to 0.094 m) overlaps those of the spleen, pancreas and upper left kidney, so the meshes may intersect. | Keep it as context while it carries no value, with its "placed by hand" note. If the dose route is ever drawn from the mouth, the stomach needs a checked placement first. |
| 6 | B | `body_map.py:53`; `body_map_pages.py:87–91`; manifest parts 1–4 | The node "Blood plasma" (a fluid) is drawn by the heart and every artery and vein. The card says "The heart and vessels stand for the blood". In an organ-level model the heart is also a tissue with its own (unmeasured) value, so the two meanings will collide. | Rename the node "Blood (circulation)". Keep the heart as pump and container. If heart muscle ever gets a value, it must be a separate node with its own evidence class. |
| 7 | B | `landscape_body_map.html:36`; `body_map_pages.py:25`; `body-map-viewer.js:59–62, 74` | The legend says "Coloured: carries model results". The colours are anatomical conventions (arteries red, veins blue, heart red, intestine pink). The heart and the "unlabelled vessels" carry no result. | "Coloured: on the modelled route. Colours are anatomical and show no amount." |
| 8 | B | `body_map_pages.py:31`; `body-map-viewer.js:88–89, 137–141` | The camera preset "Side" does not say which side. From the rotation and projection code, it shows the body's **right** side (derived from the code, not rendered). | Label it "Right side", or add a left view. |
| 9 | B | `landscape_body_map.html:33`; `body-map-viewer.js` (no left/right marker found) | The default view is from the front, so the body's left is on the viewer's right. This standard convention is not stated in the canvas label, and no L/R marker was found. Left and right kidneys differ on the map (the left is higher, as in life). | Add small "R" and "L" markers and "front view" to the canvas label. |
| 10 | B | `body_map.py:57`; `body_map_pages.py:83`; manifest parts 15–19 | The node "Urine (unchanged drug)" uses the term for the fluid but is drawn by organs: renal pelvis and calyces, ureters, bladder, urethra. The card title is "Ureters and bladder", omitting the pelvis and the urethra, both of which open this card. | Node name "Urinary tract (unchanged drug in urine)"; card title "Renal pelvis, ureters, bladder and urethra". |
| 11 | C | `body_map_paths.py:94, 110–112` | Both urine paths end at the centre of the bladder's bounding box, so the two ureters meet at one central point. The ureters open separately at the back and base of the bladder. The urethra is a route organ but no path reaches it. | End each path at the end of its own ureter centre line; optionally add a quiet path from bladder to urethra. |
| 12 | B | `body_map_pages.py:153`; `body-map-viewer.js:530`; `body_map_paths.py:16–17` | The label "Non-renal: … routes not identified" is anchored at the aorta at kidney level, next to the kidney label, which invites reading it as a place. "Not identified" is also stronger than Chen 2012 (see 2.4). | Move the label off the body, into the key strip. Wording: "Other routes: small; two minor metabolites and about 4% in faeces (Chen 2012); organ not known". |
| 13 | B | `body_map_pages.py:173`; compare `landscape_body_map.html:55` | The 3D blood label says "reference adult"; the table says "reference adult male, ICRP 89". | Say "reference adult male" in both, and switch with the body when a women's extract exists. |
| 14 | C | `intelligence_store/body_map.py:204` | Each kidney is given exactly half of the renal blood flow. A drawing choice, stated in the basis text, not an ICRP value. | Keep; add "split equally for drawing" to the 3D label. |
| 15 | C | `body_map_pages.py:113` | "pressed out of the glomerular capillaries into the tubule". More exactly, into Bowman's space, where the tubule begins. | "…out of the glomerular capillaries into Bowman's space, the start of the tubule." |
| 16 | C | `landscape_body_map.html:65–77` | The 2D flow diagram has no arrowheads; direction is implied only by position. "Kidney" is singular. The word "secretion" (y = 146) sits 24 units below its line (y = 122), while "filtration" (y = 84) sits 10 above its line (y = 94). | Add arrow markers; "Kidneys"; place both labels the same distance from their lines. |
| 17 | C | `intelligence_store/data/body_map_vessel_lines_v1.json`, `naming_note` | The Atlas nodes named left and right renal artery are on the opposite sides of the body. The platform assigns sides by position, which is correct, and records the swap. | No change to the map. Consider reporting it to the Human Reference Atlas, and keep the test that checks sides by position. |
| 18 | C | `body_map_paths.py:117–118` | The absorption path ends in a vein and the kidney inflow starts in the aorta. The passage between them (right heart, lungs, left heart) is not drawn, although the heart is coloured as part of the route. | A quiet connector, or one sentence on the blood card: "blood returns to the heart and lungs before reaching the kidneys". |
| 19 | C | `landscape_ui/templates/body_map_timeline_panel.html:16` | The column "Body" stands for one well-mixed space that includes the blood. | Rename "Body (blood and tissues together)" now; split it only when the organ-level model exists. |

Not checked: how the page looks when rendered; vessel shapes inside the 3D files; the test files; whether the UBERON identifiers in `body_map.py:51–57` still match the ontology.

---

## 8. Risks and open questions

### Risks

| Risk | Why it matters | Guard |
|---|---|---|
| The picture claims more than the model | An organ that lights up reads as "the drug is here" | Rules R1–R5 and R16; a wording audit before release |
| No unseen human data | No check can be blind; some outcomes are already predictable (5.1) | Say so in the plan and on the page; use the ledger's not-blind roles |
| Organs are not identifiable from plasma | Different organ assignments give the same plasma curve | Lumps, not organs (2.2); collapse test |
| Missing inputs filled from secondary sources | A database logP may be calculated, not measured | Primary source or "to be sourced"; record measured or calculated |
| Tuning Kp to rescue the peak | It would turn a known structural gap into an apparent success | Rule in the plan: no Kp adjusted to plasma |
| The clearance model's open problems carry over | Moderate and severe bands depend on bioavailability; three renal clearances disagree | Inherit status (R13); settle 2.3 before running |
| Healthy volunteers against patients | CL/F 318 (young men), 207 (renal study, normal group), 177 mL/min (myeloma; EMA 2008 Table 3, p. 19/51: "Cl/F (ml/min) 278 (± 18%) 277 (± 20%) 177 (± 42%)") | Never mix populations in one calibration; name the population on every curve |
| Reference adults against myeloma patients | ICRP reference values describe healthy adults; cardiac output and organ flows change with age and kidney disease | Label physiology "reference woman/man", as now; no "patient-specific" physiology |
| Sex | Distribution data are from men; women's blood-to-plasma ratio is unmeasured; ICRP 89 gives no GFR for women; the women's liver-flow figures disagree by 0.5 points | R7 and R8; the assumptions listed in 5.2 |
| Total radioactivity against parent drug | Blood-to-plasma ratio, renal clearance (261) and semen values are radioactivity; parent share is 92% or 77.44% depending on the method | Carry the limit with each value; reconcile the two shares |
| Racemate | "Individual enantiomers were shown to undergo significant non-enzymatic racemisation in human plasma" (EMA 2008, p. 15/51) | Model the total, and say so |
| A scanned source | FDA quotes not checked by eye rest on OCR | Check each used FDA quote against the page image before pinning |
| ICRP reuse terms | The existing extract notes "reuse needs ICRP permission" | Record individual values with citation, as now; check before reproducing whole tables on a page |
| Scope creep | A female body "with hormone effects" is on the roadmap | Hormonal, menstrual-cycle and pregnancy models stay out of this track |

### Open questions for the owner

1. **Lumped only, or predicted organ partition as well?** This draft recommends lumped only until logP and pKa are pinned.
2. **Which renal clearance calibrates the organ model:** 162 (current), or a reconciled value? A change is a new clearance model.
3. **Women:** run a reference woman from the first version, with the stated assumptions for blood-to-plasma ratio? This draft recommends yes for physiology (step 1) and a female mesh before any female picture.
4. **Is a mouse check wanted?** It tests the prediction method, not human organs, and its outcome is partly published.
5. **Fraction unbound:** 0.77 (as checked in 2.0a), 0.71 (healthy) or 0.60 (ex vivo)? For the organ model it affects filtration and any partition prediction.
6. **Parent share of plasma radioactivity:** 92% or 77.44%? Which does the platform quote?
7. **The women's liver blood flow in ICRP 89:** use the printed total (27.0%) or the sum of its parts (27.5%)?
8. **Should the semen finding be shown at all** on an educational map? It is the only human "tissue-side" observation, and it is easy to over-read.

---

## 9. Phased plan

Small steps, each with a gate. Steps 1–4 need no new model and are useful even if the organ-level model is never built.

| Step | What | Output | Gate before the next step |
|---|---|---|---|
| **1** | **ICRP 89 extract for women and men:** the values of 3.1, each with table, printed and PDF page, and quote; the women's liver-flow note; what ICRP 89 does not give. Men's v1 values re-confirmed. | `reference_physiology_icrp89_v2.json` (new file, new pin; v1 kept), loader test, data-file index | Owner checks each quote against the PDF page. Derived sums reproduce (100.0%; 25.5 = 25.5; 27.5 ≠ 27.0 recorded). No page changes. |
| 2 | **Tissue-distribution evidence extract:** the quotes of section 4 and the per-organ evidence class of 4.2. Ledger update: Chen 2012 plasma and urine values recorded as seen; the three located studies recorded as "abstract seen 12 November 2026". TGA `.docx` pinned (F28). | `lenalidomide_tissue_distribution_evidence_v1.json`; ledger v7 | Owner review. Each FDA quote used is checked against the page image. |
| 3 | **Anatomy fixes** from section 7: labels and names first (4, 6–10, 12–16, 19), then geometry (1, 2, 3, 11) as new versioned path files. | Wording changes; `body_map_flow_paths_v3.json` | Tests: the absorption path ends at the portal vein or liver; process strands start in the cortex. v2 paths kept. Screenshots reviewed by the owner. |
| 4 | **Evidence classes on the existing map:** organ cards show observed / animal only / predicted / no data from step 2. No new number. | `body-map-view-v3` (v2 kept) | Overclaiming audit of the new text. Rules R1, R2, R6, R9, R10 enforced by test. |
| 5 | **Decision record:** lumped model only, or with predicted partition (question 1). If partition is wanted: logP and pKa pinned from a primary source. | `docs/decisions/…`; possibly a physicochemical extract | If no primary source can be pinned, organ partition stops here. |
| 6 | **Check plan locked,** with the executable check run on synthetic values (5.2). | Plan file, check module, tests; ledger and findings entries | `validate_plan_datasets` passes with not-blind roles. Owner approves the decision rule. |
| 7 | **Model built and check run** exactly as the plan states. | Model module, report in `docs/verification/` | Numerical tests pass. Result classified by the plan's rule, failures included. |
| 8 | **Organ-level view** under the rules of 6.2. | Page and viewer changes; run record | Wording audit; both flags false; a rendered-page review. |
| 9 | **Female reference body** (mesh and its own asset manifest), then the women's picture. | Assets, manifest, paths for the female body | R7 enforced by test. No hormonal, cycle or pregnancy content. |

**First step to approve: step 1,** the ICRP 89 extract for women and men. It is small, needs no model and no decision on PBPK, corrects the map's present limitation to a reference man, and gives the owner a first look at one real inconsistency in the source (the women's liver blood flow) before anything depends on it.

---

## Sources

**Attached and read**

1. ICRP, 2002. *Basic Anatomical and Physiological Data for Use in Radiological Protection: Reference Values.* ICRP Publication 89. Annals of the ICRP 32(3–4). File `ANIB_32_3-4.pdf`. <https://doi.org/10.1016/S0146-6453(03)00002-2>
2. Chen N, Wen L, Lau H, Surapaneni S, Kumar G. Pharmacokinetics, metabolism and excretion of [14C]-lenalidomide following oral administration in healthy male subjects. *Cancer Chemother Pharmacol* 2012;69:789–797. <https://doi.org/10.1007/s00280-011-1760-3> (open access: <https://pmc.ncbi.nlm.nih.gov/articles/PMC3286592>)
3. European Medicines Agency. Withdrawal assessment report for Lenalidomide Celgene Europe, EMEA/CHMP/249329/2008. Medicine page (the report is under "All documents"): <https://www.ema.europa.eu/en/medicines/human/EPAR/lenalidomide-celgene-europe>
4. US Food and Drug Administration, Center for Drug Evaluation and Research. Clinical pharmacology and biopharmaceutics review, NDA 21-880 (REVLIMID), 2005. File `021880s000_Revlimid_BioPharmR.pdf`. Expected location, built from the file name and **not opened in this session**: <https://www.accessdata.fda.gov/drugsatfda_docs/nda/2005/021880s000_Revlimid_BioPharmR.pdf>
5. Therapeutic Goods Administration. AusPAR Attachment 2: Extract from the Clinical Evaluation Report for Lenalidomide (Revlimid), February 2016. <https://tga.gov.au/sites/default/files/auspar-lenalidomide-160205-cer.docx>

**Repository**

6. Marlo Scientific, <https://github.com/astridcmarin/marlo-scientific>, branch `main`, commit `f1eb8b6e9dd2516e4c8edda010fe17fb23d46e8b`. Files as named in the text.

**Located by search, not attached, not pinned (abstract or search-result text only)**

7. Rozewski DM, et al. Pharmacokinetics and tissue disposition of lenalidomide in mice. *AAPS J* 2012;14:872–882. <https://doi.org/10.1208/s12248-012-9401-2> (<https://pmc.ncbi.nlm.nih.gov/articles/PMC3475844>)
8. Hughes JH, Upton RN, Reuter SE, Rozewski DM, Phelps MA, Foster DJR. Development of a physiologically based pharmacokinetic model for intravenous lenalidomide in mice. *Cancer Chemother Pharmacol* 2019;84:1073–1087. <https://doi.org/10.1007/s00280-019-03941-z> (<https://pmc.ncbi.nlm.nih.gov/articles/PMC7375688>)
9. Chen N, Lau H, Choudhury S, Wang X, Assaf M, Laskin OL. Distribution of lenalidomide into semen of healthy men after multiple oral doses. *J Clin Pharmacol* 2010. <https://doi.org/10.1177/0091270009355157>
10. Plasma and cerebrospinal fluid pharmacokinetics of thalidomide and lenalidomide in nonhuman primates. PubMed record 22109830. <https://read.qxmd.com/read/22109830/plasma-and-cerebrospinal-fluid-pharmacokinetics-of-thalidomide-and-lenalidomide-in-nonhuman-primates>
11. Tong Z, Yerramilli U, Surapaneni S, Kumar G. The interactions of lenalidomide with human uptake and efflux transporters and UDP-glucuronosyltransferase 1A1. *Cancer Chemother Pharmacol* 2014;73:869–874. <https://doi.org/10.1007/s00280-014-2415-y>
12. Chen N, Zhou S, Palmisano M. Clinical pharmacokinetics and pharmacodynamics of lenalidomide. *Clin Pharmacokinet* 2017;56:139–152. <https://doi.org/10.1007/s40262-016-0432-1>

**Methods (cited for the approach; no value taken from them)**

13. Poulin P, Theil FP. A priori prediction of tissue:plasma partition coefficients of drugs to facilitate the use of physiologically-based pharmacokinetic models in drug discovery. *J Pharm Sci* 2000;89:16–35.
14. Poulin P, Theil FP. Prediction of pharmacokinetics prior to in vivo studies. 1. Mechanism-based prediction of volume of distribution. *J Pharm Sci* 2002;91:129–156. <https://doi.org/10.1002/jps.10005>
15. Rodgers T, Leahy D, Rowland M. Physiologically based pharmacokinetic modeling 1: predicting the tissue distribution of moderate-to-strong bases. *J Pharm Sci* 2005;94:1259–1276. <https://doi.org/10.1002/jps.20322>
16. Rodgers T, Rowland M. Physiologically based pharmacokinetic modelling 2: predicting the tissue distribution of acids, very weak bases, neutrals and zwitterions. *J Pharm Sci* 2006;95:1238–1257 (erratum 2007;96:3153–3154). <https://doi.org/10.1002/jps.20502>
17. Cao Y, Jusko WJ. Applications of minimal physiologically-based pharmacokinetic models. *J Pharmacokinet Pharmacodyn* 2012;39:711–723. <https://doi.org/10.1007/s10928-012-9280-2>

*End of draft. AI-generated; not reviewed by a human; not an independent review.*

---

## Handling (12 November 2026, approved by the platform owner)

- **Step 1 done:** `intelligence_store/data/reference_physiology_icrp89_v2.json`, the reference woman and man side by side. Every quote was checked against the PDF in the main session with `scripts/check_source_quotes.py` (54 of 54 found; PDF SHA-256 matches). The main session added six rows this draft's table left out (bronchial tissue, thyroid, lymph nodes, gonads, adrenals, urinary bladder) and the red-marrow sub-row; with them both blood-flow columns sum to 100.0%, as the draft states. The women's liver total (27.0% printed, 27.5% by its parts) is recorded. The pages still use v1.
- **Step 3, labels first:** the anatomy fixes in section 7 that change only names and labels are in the next update; geometry fixes (items 1, 2, 3, 11) follow as new versioned path files.
- **Open questions** in section 8 are for the owner and remain open.
