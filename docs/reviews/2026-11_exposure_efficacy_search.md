# AI-generated evidence search (Claude Fable, second account), not an independent review

## Lenalidomide: do exposure–efficacy analyses exist? (reviewer's checklist item O7)

| | |
|---|---|
| Date | 12 November 2026 |
| Model identifier | `claude-fable-5-2` |
| Repository read | `astridcmarin/marlo-scientific`, branch `main`, commit `f1eb8b6e9dd2516e4c8edda010fe17fb23d46e8b` (read only; nothing changed, no pull request, issue or commit) |
| Scope | A search for existing analyses only. No model is built or proposed. Nothing here is a dosing or clinical statement. The platform is not validated for clinical prediction. |

## Answer in brief

- **No quantitative exposure–efficacy model for lenalidomide was found** in any regulatory document or publication opened: none relates a pharmacokinetic exposure (AUC, Cmax, trough) to response, progression-free survival or M-protein in a form that could be reproduced.
- **Regulators say so directly** where they address it. The FDA's 2005 review states that such studies "were not performed". Five EMA variation reports (II-0056, X-0073-G, II-0079, II-0089-G, II-0107) contain no exposure–efficacy analysis; two say "No dose-response studies were submitted."
- **What does exist is weaker and of three kinds:**
  1. *One randomised dose comparison,* in del(5q) MDS, not myeloma: study MDS-004, 10 mg against 5 mg (different schedules), not powered to compare the two.
  2. *Dose-based retrospective analyses* by the sponsor (MDS: Sekeres 2018; myeloma: Dimopoulos 2011). Exposure is milligrams taken, not a concentration, and dose changes followed tolerability.
  3. *Small pharmacokinetic studies* in myeloma that looked for a link between measured concentration and response and reported none (Bridoux 2016; Kado 2015; the Akita University report), plus the Valencia thesis the platform already holds, whose association runs in the unexpected direction.
- **Verdict for O7: partial evidence, none of it usable for a calculation.** The gap is in the published evidence, not only in the platform.
- **This search is incomplete.** The page-reading tool reached a usage limit before seven items could be opened, and FDA supplement reviews could not be located or opened. They are listed in section 6.

## 1. What the platform already uses

Read first, as instructed.

- **Checklist O7** (`docs/REVIEWER_CHECKLIST.md:49`): "Exposure–response for efficacy. | None; the evidence scan found no usable source. Shown as a gap."
- **Exposure–safety model** (`lenalidomide_exposure_safety_v2.json` and its report text v2): relative odds of grade 3/4 thrombocytopenia and neutropenia per unit of ln AUC, from the sponsor's analysis CC-5013-MCL-001-PK as reported by the TGA. Safety only.
- **An earlier efficacy search** (`docs/DOSE_OPTIMISATION.md:73–94`, 31 October 2026) covered four sources: the FDA 2005 review, the Chen 2017 review, a PAGE 2015 poster and the Guglieri López thesis. Its conclusion: "no usable exposure–efficacy relationship for lenalidomide in myeloma was found."
- **The thesis** is pinned as `lenalidomide_exposure_response_guglieri_2017_v1.json` and shown as a cited finding, not used in any calculation.

This search adds: the EMA variation reports, the randomised MDS dose comparison, two sponsor dose-based analyses, and three small concentration–response studies.

## 2. How the search was done, and its limits

| Source type | How read | Limit |
|---|---|---|
| EMA 2008 withdrawal report; TGA clinical evaluation report; FDA 2005 review (the three attached files) | From the files. The FDA file is scanned: read by OCR, and PDF page 10 was also checked by eye against the page image. | TGA tables that are images were not read. Other FDA pages are OCR only. |
| EMA II-0056 and II-0107 | **Not attached in this conversation.** Opened from the EMA website. | See next row. |
| All web pages and PDFs | Opened with a page-reading tool. It returns an answer written by a small model that reads the page, and it limits each quotation to about 125 characters. | **Quotes from web sources below are short fragments as returned by that tool. I did not see the page text myself.** They should be checked against the PDF before any is pinned. Page numbers are those the tool reported. |
| Searches | Sixteen web searches. Search snippets were used only to find pages, never as a source. | Where a page could not be opened, the item is listed in section 6 with no numbers. |

Not opened: any eligibility annotation, the 200-trial sample, or anything under `instance/`.

## 3. Regulatory documents

### 3.1 What each says about exposure and efficacy

| Document | Indication | Statement (exact quote) | Location |
|---|---|---|---|
| FDA clinical pharmacology and biopharmaceutics review, NDA 21-880, 2005 (attached) | del(5q) MDS | "Clinical studies assessing the relationship between exposure and efficacy were not performed." | Section 2.2.4.1, PDF p. 10, printed p. 9 (checked by eye) |
| Same | | "The relationship between dose-concentration and response is largely unknown. The currently recommended 10 mg dose requires frequent dose reductions (approximately 80% of patients), suggesting that higher doses are not prudent. The efficacy of lower doses is unknown. Determination of an optimal dose is an unresolved dosing issue." | PDF p. 11, printed p. 10 (OCR only) |
| Same | | "The relationship between exposure and efficacy and safety is largely unknown." | Section 2.3.1, PDF p. 22, printed p. 21 (OCR only) |
| EMA withdrawal assessment report, EMEA/CHMP/249329/2008 (attached) | del(5q) MDS | "No pharmacodynamic data from MDS trial are available and therefore no relationship between plasma concentration and effect has been investigated in MDS patients." | p. 23/51 |
| Same | | "No dose response study was conducted in MDS patients and no MTD has been determined in this target population." | p. 24/51 |
| Same | | Study MDS-004 "investigates the efficacy and safety of 2 doses (5 and 10 mg/day) of lenalidomide vs. placebo … and might bring some answer to absence of a proper dose-response study." | p. 33/51 |
| EMA II-0056, EMA/297642/2013 (web) | del(5q) MDS | No exposure–response or concentration–response analysis for efficacy found by the tool in any of three passes over the report. Section 2.5.1 "Dose response study(ies)" describes how 10 mg and 5 mg were chosen. Results in 3.2 below. | Sections 2.4.2–2.4.4, 2.5.1 (pp. 22–27/123) |
| EMA X-0073-G, EMA/130972/2015 (web) | Newly diagnosed myeloma | "No new clinical pharmacology studies have been submitted." The only dose–response study cited (ECOG E4A03) compared dexamethasone doses with lenalidomide fixed. | Section 2.4.3, p. 19/95; section 2.5.1, pp. 20–21/95 |
| EMA II-0079, EMA/CHMP/642878/2015 (web) | Mantle cell lymphoma | "No dose-response studies were submitted." No pharmacokinetic or exposure–response section found. | Section 2.4.1, p. 9/70 |
| EMA II-0089-G, EMA/CHMP/108277/2017 (web) | Myeloma maintenance after transplant | "No dose-response studies were submitted." | Section 2.4.1, p. 11/99. The last 5,000 characters of this report were not read. |
| EMA II-0107, EMA/CHMP/693880/2019 (web) | Follicular lymphoma, with rituximab | "No new information regarding clinical pharmacology was submitted." No exposure–response passage found in any of three passes. | Section 2.3.2, p. 15/139 |
| TGA clinical evaluation report, 2016 (attached) | Newly diagnosed myeloma | The only exposure–response analysis is for toxicity: study CC-5013-MCL-001-PK aimed "to quantitatively describe the lenalidomide exposure-response relationship for measures of toxicities (neutropenia and thrombocytopenia)". A keyword search of the whole report found no exposure–efficacy analysis. | Heading "Population pharmacokinetics" |

Also in the EMA 2008 report, and not efficacy: Table 20 (p. 47/51) relates cumulative lenalidomide dose to progression to acute myeloid leukaemia in study MDS-003. It is a safety analysis by milligrams taken.

### 3.2 The one randomised dose comparison: study MDS-004 (EMA II-0056)

| Item | Finding |
|---|---|
| Citation | EMA assessment report, Revlimid, procedure EMEA/H/C/000717/II/0056, EMA/297642/2013, 25 April 2013. <https://www.ema.europa.eu/en/documents/variation-report/revlimid-h-c-717-ii-0056-epar-assessment-report-variation_en.pdf>. Regulatory review. |
| Population | Transfusion-dependent lower-risk MDS with del(5q). Randomised: placebo 67, 5 mg 69, 10 mg 69 (Tables 20–21, pp. 49–50/123). Modified intention-to-treat: 51, 47, 41 (Table 36, p. 74/123). |
| Exposure measure | **Assigned dose,** not a pharmacokinetic measure. The two arms also differ in schedule: 5 mg on "Days 1-28, every 28 days" (p. 46/123), 10 mg on 21 of 28 days (section 2.5.1). |
| Endpoint | Red-cell transfusion independence for at least 182 days; cytogenetic response. |
| Result | Transfusion independence: "56.1% (23 of 41 patients) in the 10 mg lenalidomide group, 42.6% (20 of 47 patients) in the 5 mg lenalidomide group" (p. 116/123; Table 36, p. 74/123, which also gives placebo 3 of 51, 5.9%). Intention-to-treat: "the corresponding figures were 55.1% and 34.8%" (p. 83/123). Cytogenetic response: "54% and 30.2% of evaluable patients" (p. 116/123). |
| Regulator's reading | "the 10 mg dose appeared to produce better results than 5 mg" but "Since MDS 004 was not designed to compare 5 mg 21/28d vs. 10 mg 28/28d, the optimal dose and regimen could still be further refined." (p. 117/123). "Even though the study was not powered to compare 5 mg with 10 mg dose" (p. 82/123). |
| Can the platform use it? | **Not as an exposure–efficacy relationship.** It is two dose levels with different schedules, in MDS. Hughes 2019 was built on myeloma, chronic lymphocytic leukaemia and acute leukaemias, and Kim 2026 on myeloma with renal impairment; neither includes MDS patients. Two points cannot define a curve, and the comparison was not powered. It can be **quoted** as the only randomised dose comparison found. |
| Limits | Not myeloma. Schedule confounds dose. Dose reductions were frequent, so the dose taken differed from the dose assigned. One apparent slip in the report's own text ("5 mg 21/28d vs. 10 mg 28/28d") reverses the schedules given elsewhere in the same report; it is quoted as printed. |

## 4. Published analyses

### 4.1 Dose-based analyses (exposure = milligrams, no pharmacokinetics)

**Sekeres et al. 2018**

| Item | Finding |
|---|---|
| Citation | Sekeres MA, Swern AS, Giagounidis A, List AF, Selleslag D, Mittelman M, et al. The impact of lenalidomide exposure on response and outcomes in patients with lower-risk myelodysplastic syndromes and del(5q). *Blood Cancer J* 2018;8(10):90. doi:10.1038/s41408-018-0126-z. <https://pmc.ncbi.nlm.nih.gov/articles/PMC6173782>. Journal article, open access; retrospective; funded by Celgene. |
| Population | Lower-risk del(5q) MDS, studies MDS-003 and MDS-004 pooled. "A total of 217 patients received an initial dose of lenalidomide 10 mg"; "69 patients received an initial dose of lenalidomide 5 mg" (Results). |
| Exposure measure | Initial dose group; cumulative dose in cycle 1 and in cycles 1–3; dose reduction as a time-varying factor. **No plasma concentration or AUC.** |
| Endpoints and results | Transfusion independence for at least 26 weeks: "57.1% for the 10 mg dose group vs. 34.8% for the 5 mg dose group (p < 0.001)" (Results). Per 100 mg of cumulative dose, odds ratio 3.41 (2.19–5.32) for cycle 1 and 1.59 (1.37–1.85) for cycles 1–3 (Table 1). Cytogenetic response: "65.2% of patients in the 10 mg dose group vs. 30.2% in the 5 mg dose group (p < 0.001)"; odds ratio per 100 mg 2.61 (1.50–4.56) for cycle 1 (Table 1). Overall survival and AML-free survival did not differ by starting dose (log-rank p = 0.6829 and 0.671) but were associated with cumulative dose in the first cycles (Table 1; Table 2). |
| Can the platform use it? | **No.** The exposure is milligrams, the disease is MDS, and the odds ratios come without intercepts or baseline rates, so no response probability can be reproduced. A dose could be converted to a typical AUC by the platform's models, but that would add nothing the dose does not already say. |
| Limits | The authors: "Limitations of this analysis include its retrospective nature and patient population heterogeneity." Dose reduction itself was associated with *better* outcome (hazard ratio for AML or death 0.44, 0.32–0.62, Table 2), which shows how strongly staying on treatment shapes these associations. Cumulative dose in early cycles depends on tolerating the drug. |

**Dimopoulos et al. 2011**

| Item | Finding |
|---|---|
| Citation | Dimopoulos MA, Hussein M, Swern AS, Weber D. Impact of lenalidomide dose on progression-free survival in patients with relapsed or refractory multiple myeloma. *Leukemia* 2011;25:1620–1626. doi:10.1038/leu.2011.126. <https://www.nature.com/articles/leu2011126.pdf>. Journal article; sponsor-supported. |
| Population | Relapsed or refractory myeloma on lenalidomide with dexamethasone, studies MM-009 and MM-010. "Of 353 patients who received lenalidomide plus dexamethasone, 116 (33%) had not progressed" at 12 months; only those 116 were analysed. |
| Exposure measure | Timing of dose reduction: none (52), before 12 months (39), at or after 12 months (25). **No pharmacokinetic data.** |
| Endpoint and result | Progression-free survival from a 12-month landmark. Median: not reached with reduction at or after 12 months; 28.0 months (17.5–36.7) with reduction before 12 months; 36.8 months with none (Table 2). Reduction at or after 12 months was an "independent predictor of improved PFS (hazard ratio, 0.47" (95% CI 0.23–0.98; Table 3). |
| Can the platform use it? | **No.** It concerns when a dose was reduced, in patients selected for having done well for a year. It gives no relationship between exposure and effect. |
| Limits | The authors: "it is exploratory in nature and is based on a small number of patients in each subgroup"; "prospective studies are needed to confirm these findings". The landmark was chosen after 6- and 9-month analyses were not significant (as reported by the reading tool). Dose reductions were clinicians' decisions. |

### 4.2 Studies that measured concentration and looked at response

| Study | Type; population; n | Exposure measure | Efficacy endpoint and result (exact quote) | Usable by the platform? |
|---|---|---|---|---|
| **Bridoux et al. 2016**, *Cancer Chemother Pharmacol* 78:173–182, doi:10.1007/s00280-016-3068-9. <https://link.springer.com/article/10.1007/s00280-016-3068-9> | Journal article; phase 2; relapsed or refractory myeloma with stable renal impairment, lenalidomide with dexamethasone; "Among 38 patients" | Observed AUC and Cmax from serial sampling (per the repository's extract, day 5) | "Overall response was 76 %"; "no exposure-dependent trend in efficacy or toxicity" (Abstract). The sponsor's review restates it: "no apparent pattern was observed between lenalidomide Cmax and the grade of hematologic AEs or efficacy" (Chen 2017, section "Exposure Response"). | **No.** Doses were adjusted to kidney function so that AUC was "within ±25 % of the target AUC in each group". With exposure deliberately held similar, the absence of a trend says little. No model is reported. Only the abstract page was opened here; the owner holds the article. The platform already uses this study for pharmacokinetic checks. |
| **Kado et al. 2015**, ASH abstract 3700 (*Blood* 126:3700). <https://ash.confex.com/ash/2015/webprogramscheduler/Paper78718.html> | Meeting abstract; relapsed and refractory myeloma, Japan; "Thirteen Japanese patients" on "Len at 10–25 mg" | One plasma concentration "three hours after Len administration in the first cycle" | Best response over three cycles. "However, there was no correlation between Len concentrations and best responses." | **No.** Thirteen patients, one time point, no model. |
| **Kado et al. 2020**, *Biol Pharm Bull* 43(8):1253–1258, doi:10.1248/bpb.b20-00337. <https://www.jstage.jst.go.jp/article/bpb/43/8/43_b20-00337/_html/-char/en> | Journal article; relapsed and refractory myeloma, one centre; 31 analysed | Concentration 3 h after the dose on day 7 of cycle 1; concentration-to-dose ratio | Compares patients who continued three cycles unchanged (23) with those whose treatment was modified (8), not exposure with response: "There were no significant differences in efficacy between the continuous and modifying groups." Partial or complete response 11 (47.8%) against 3 (37.5%), p = 0.6980 (Table 2). | **No.** Not an exposure–efficacy analysis. Authors' limits include "the sample size was small". |
| **Takahashi (Akita University), grant report 26461414, 2014–2016.** <https://kaken.nii.ac.jp/en/file/KAKENHI-PROJECT-26461414/26461414seika.pdf>. The same group's article (Kobayashi et al., *Ther Drug Monit* 2018;(3):301–309, doi:10.1097/FTD.0000000000000499) **could not be opened.** | Grant report (Japanese with English abstract); newly diagnosed myeloma, elderly, Japan; "Forty patients were enrolled in this study." | Estimated AUC over 24 h from samples before and 1, 2 and 4 h after the dose (per the 2017 EHA abstract PB1999 of the same study) | As reported by the reading tool from an English figure legend: no significant difference in AUC between patients with partial response or better (n = 16) and the others (n = 9), P = 0.637. Overall response 68.6% of 35 evaluable. **No verbatim sentence was returned for this result,** so it is unconfirmed until the report or the article is read. | **No.** Small, no model; and unverified as stated. |
| **Guglieri López 2017**, doctoral thesis, Universitat de València (already pinned by the platform) | Thesis; myeloma, routine practice, one centre; 54 patients, 15 with samples | AUC from the author's population model; typical values for 65% of patients | Time to progression: "patients with lenalidomide AUC0-∞ above 1,110 µg·h/L (median value of the studied sample) had an increased risk of disease progression of 19.7% per each 100 µg·h/L increase of AUC0-∞ (Table 5.17)" (section 6.4.1, PDF p. 215; quote from the repository's extract, not re-read here) | **No,** for the five reasons already recorded in `docs/DOSE_OPTIMISATION.md:84–92`. |

### 4.3 Sponsor analyses and reviews that turn out to be safety only

| Source | What it contains |
|---|---|
| Chen N, Ette E, Zhou S, Weiss D, Palmisano M. *Blood* 2013;122(21):3234 (meeting abstract). Read from an indexing site that reproduces the abstract (<https://www.sciencegate.app/keyword/888038>); the publisher's page could not be opened. | Population pharmacokinetics and exposure–safety in 147 subjects. "LEN AUC was a significant predictor of the probability of experiencing grade 3/4 thrombocytopenia and neutropenia." **No efficacy analysis.** This is the analysis behind the platform's exposure–safety model. |
| Chen N, Zhou S, Palmisano M. *Clin Pharmacokinet* 2017;56:139–152. <https://pmc.ncbi.nlm.nih.gov/articles/PMC5247551> | Sponsor's review. It reports no quantitative exposure–efficacy model. On efficacy it cites only Bridoux 2016: "These data suggest that a high Cmax is not critical for efficacy". It also states "Because early lenalidomide dose intensity is considered crucial for optimal outcomes [67]"; reference 67 could not be retrieved. |

## 5. Conclusion for O7

**Partial evidence; none usable.**

| Question | Answer |
|---|---|
| Does a published or regulatory exposure–efficacy analysis exist for lenalidomide in myeloma? | Not as a model. Three small studies with measured concentrations report no relationship with response (one unverified), in settings where exposure varied little or patients were few. One thesis reports an association in the unexpected direction, with the weaknesses the platform has already recorded. |
| In MDS? | One randomised comparison of two dose levels (MDS-004), not powered for it and confounded by schedule, and one retrospective dose-based analysis of the same trials. Both favour the higher dose. Neither uses pharmacokinetics. |
| In lymphoma? | Nothing found. The EMA reports for mantle cell and follicular lymphoma contain no exposure–response analysis. |
| Is any exposure measure compatible with Hughes 2019 or Kim 2026? | Only trivially. Where a study reports a dose, the models can give a typical AUC, but no source supplies an efficacy function of AUC to apply it to. The studies with measured AUC report no function at all. |
| Is anything reproducible from what is reported? | No. No source gives a complete model (structure, parameters, baseline). |
| What limits recur? | Dose follows tolerability and kidney function, so dose and exposure are confounded with how the patient is doing. Selection of patients who stayed on treatment. Small samples. Exposure deliberately equalised across kidney-function groups. Combination with dexamethasone. |

**What would be needed to close O7:**
1. **A sponsor analysis with randomised dose levels in myeloma,** or with adequate adjustment. None was found in public documents. The places still to look are in section 6.
2. **Failing that, a recorded decision** that O7 is a gap in the published evidence. The checklist row could then cite this search and the regulators' own statements, and stay a gap.
3. **The MDS-004 result could be shown as a quoted finding** (as the thesis is), clearly marked as MDS, two dose levels, different schedules, not powered. That is an owner decision; it would not change O7 for myeloma.

Nothing found supports placing an efficacy scale beside the platform's dose view. Its present statement, "a lower exposure here is not a better dose", remains the accurate one.

## 6. Not found, or not opened

**Searched for and not found**
- Any tumour-growth or M-protein model driven by lenalidomide concentration or AUC. (The PAGE 2015 poster in the repository has no exposure term. A PAGE abstract on a dexamethasone M-protein model appeared in search results and was not opened.)
- Any exposure–efficacy analysis in mantle cell, follicular or other lymphoma.
- Any FDA clinical pharmacology or multidisciplinary review for a REVLIMID efficacy supplement. Searches returned only approval letters and labels for the supplements.

**Could not be opened in this session** (no content from these is used above)

| Item | Why it matters |
|---|---|
| Drugs@FDA listing for NDA 021880 | To confirm which supplements have a posted review. The page was refused by the tool. |
| REVLIMID label, section 12 (2019 PDF) | To confirm that section 12.2 contains no exposure–response statement. Only the first half of the file was read; the platform's own extract records 12.2 as the QT study. |
| Kobayashi et al., *Ther Drug Monit* 2018 | The published version of the Akita study; needed to verify the P = 0.637 finding. |
| Kim et al. 2026 (the platform's Kim model source) | A search snippet suggests it discusses the absence of an established pharmacokinetic target for efficacy. The page returned a robot check. The owner holds the article. |
| Komrokji et al., *Blood* 2012;120:3419–3424 (MDS study PK-002) | Cited by the sponsor's review for exposure and blood-count falls; whether it relates exposure to erythroid response was not checked. The EMA notes "The efficacy analysis of PK-002 study is based upon data from a small subset of patients (N = 7)" (II-0056, p. 22/123). |
| Chen 2017, reference 67 | The source for "early lenalidomide dose intensity is considered crucial". |
| Song et al., *Front Pharmacol* 2022 | By its title an exposure–safety study; not opened, so not confirmed to lack efficacy. |

**Not searched**
- The original Revlimid EPAR scientific discussion (2007, studies MM-009 and MM-010).
- Japanese PMDA review reports and Health Canada summaries.
- Conference abstracts beyond ASH 2013 and 2015, EHA 2017 and PAGE.
- Paediatric, CLL and solid-tumour studies.

## Sources

**Attached files read**
1. European Medicines Agency. Withdrawal assessment report, Lenalidomide Celgene Europe, EMEA/CHMP/249329/2008. <https://www.ema.europa.eu/en/medicines/human/EPAR/lenalidomide-celgene-europe>
2. US FDA. Clinical pharmacology and biopharmaceutics review, NDA 21-880 (REVLIMID), 2005. File `021880s000_Revlimid_BioPharmR.pdf` (link not opened in this session: <https://www.accessdata.fda.gov/drugsatfda_docs/nda/2005/021880s000_Revlimid_BioPharmR.pdf>).
3. Therapeutic Goods Administration. AusPAR Attachment 2, Extract from the Clinical Evaluation Report for Lenalidomide, February 2016. <https://tga.gov.au/sites/default/files/auspar-lenalidomide-160205-cer.docx>

**Opened on the web**
4. EMA. Revlimid II/0056 assessment report, EMA/297642/2013. <https://www.ema.europa.eu/en/documents/variation-report/revlimid-h-c-717-ii-0056-epar-assessment-report-variation_en.pdf>
5. EMA. Revlimid X/0073/G assessment report, EMA/130972/2015. <https://www.ema.europa.eu/en/documents/variation-report/revlimid-h-c-717-x-0073-g-epar-assessment-report-variation_en.pdf>
6. EMA. Revlimid II/0079 assessment report, EMA/CHMP/642878/2015. <https://www.ema.europa.eu/en/documents/variation-report/revlimid-h-c-717-ii-0079-epar-assessment-report-variation_en.pdf>
7. EMA. Revlimid II/0089/G assessment report, EMA/CHMP/108277/2017. <https://www.ema.europa.eu/en/documents/variation-report/revlimid-h-c-717-ii-0089-g-epar-assessment-report-variation_en.pdf>
8. EMA. Revlimid II/0107 assessment report, EMA/CHMP/693880/2019. <https://www.ema.europa.eu/en/documents/variation-report/revlimid-h-c-717-ii-0107-epar-assessment-report-variation_en.pdf>
9. Sekeres MA, et al. *Blood Cancer J* 2018;8:90. <https://pmc.ncbi.nlm.nih.gov/articles/PMC6173782>
10. Dimopoulos MA, et al. *Leukemia* 2011;25:1620–1626. <https://www.nature.com/articles/leu2011126.pdf>
11. Bridoux F, et al. *Cancer Chemother Pharmacol* 2016;78:173–182 (abstract page). <https://link.springer.com/article/10.1007/s00280-016-3068-9>
12. Kado Y, et al. ASH 2015, abstract 3700. <https://ash.confex.com/ash/2015/webprogramscheduler/Paper78718.html>
13. Kado Y, et al. *Biol Pharm Bull* 2020;43:1253–1258. <https://www.jstage.jst.go.jp/article/bpb/43/8/43_b20-00337/_html/-char/en>
14. Takahashi N. Grant report 26461414, "Therapeutic drug management of the novel agents for multiple myeloma". <https://kaken.nii.ac.jp/en/file/KAKENHI-PROJECT-26461414/26461414seika.pdf>
15. Kobayashi T, et al. EHA 2017, abstract PB1999. <https://library.ehaweb.org/eha/2017/22nd/182713/takahiro.kobayashi.clinical.impact.of.the.plasma.lenalidomide.concentration.html>
16. Chen N, et al. *Blood* 2013;122(21):3234, as reproduced at <https://www.sciencegate.app/keyword/888038>
17. Chen N, Zhou S, Palmisano M. *Clin Pharmacokinet* 2017;56:139–152. <https://pmc.ncbi.nlm.nih.gov/articles/PMC5247551>

**Repository**
18. Marlo Scientific, <https://github.com/astridcmarin/marlo-scientific>, branch `main`, commit `f1eb8b6e9dd2516e4c8edda010fe17fb23d46e8b`: `docs/REVIEWER_CHECKLIST.md`, `docs/STATUS_BY_DRUG.md`, `docs/DOSE_OPTIMISATION.md`, `intelligence_store/data/lenalidomide_exposure_safety_v2.json`, `model_analysis_report_text_lenalidomide_exposure_safety_2016_v2.json`, `lenalidomide_exposure_response_guglieri_2017_v1.json`.

**Located, not opened** (see section 6)
19. Kobayashi T, et al. *Ther Drug Monit* 2018;(3):301–309 (volume not confirmed). doi:10.1097/FTD.0000000000000499
20. Komrokji RS, et al. *Blood* 2012;120:3419–3424. doi:10.1182/blood-2012-03-415661
21. Song Z, et al. *Front Pharmacol* 2022;13:931495. <https://doi.org/10.3389/fphar.2022.931495>

*End of search. AI-generated; not reviewed by a human; not an independent review.*

## Handling (12 November 2026, approved by the platform owner)

- **Quotes checked in the main session.** The ten quotes from the three EMA reports the owner holds (EMEA/CHMP/249329/2008, II-0056, II-0107) were found word for word in the PDF text layer (`pdftotext -layout`, whitespace normalised). In II-0056 and II-0107 the terms "exposure-response", "concentration-response" and "exposure-efficacy" do not occur. The FDA 2005 quotes were already checked on 31 October (`docs/DOSE_OPTIMISATION.md`). The same day the owner downloaded EMA X-0073-G (SHA-256 `1784000286c5…`), II-0079 (`262d55040259…`), II-0089-G (`5eef4db35f50…`) and Sekeres 2018 (`44e9e3defc77…`): the three EMA quotes were found on the pages stated (19, 9 and 11), and none of the three reports contains "exposure-response", "concentration-response" or "exposure-efficacy". Every Sekeres quote and all twelve odds-ratio, interval and p values in section 4.1 were found in the article (two quotes only with `pdftotext -raw`, because of a hyphenated line break and a column break). **Not checked:** Dimopoulos 2011, Kado 2015 and 2020, and the Akita report; the owner does not hold these files. The Akita result (P = 0.637) has no verbatim source and stays unconfirmed.
- **Checklist O7** now reads as a gap in the published evidence, citing the regulators' statements, the 31 October search and this one. It remains a gap.
- **MDS-004 is not shown on the platform.** It is in MDS, not myeloma, its two arms differ in schedule, and it was not powered to compare them; shown beside a myeloma dose view it would invite a dose ranking the evidence does not support. It stays in this document only.
- **Nothing is pinned** from this search, and no calculation changes. The dose page wording ("a lower exposure here is not a better dose") stands.
- **Still open:** FDA supplement reviews (Drugs@FDA, NDA 021880), Kobayashi 2018, the Kim 2026 discussion (held by the owner), the 2007 EPAR scientific discussion, PMDA and Health Canada reviews.
