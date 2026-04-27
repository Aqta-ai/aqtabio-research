# Preprint Outline — medRxiv Submission

**Status**: working outline. Convert to full prose before submission. Numbers and event lists trace back to the AqtaBio repository (`aqta_bio/backtesting/historical_events.py`, `aqta_bio/model/`); confirm before submission. References cite real, published works only — verify each DOI on EUR‑Lex / publisher site before press time.

**Target server**: medRxiv (the health-sciences preprint server operated by BMJ, Cold Spring Harbor Laboratory, and Yale).
**Subject category**: *Public and Global Health* (primary), *Epidemiology* (secondary).
**Licence**: CC BY 4.0 (medRxiv default for public-health work).

---

## Provisional title

> **Pre‑etiologic zoonotic spillover-risk forecasting at 25 km tile resolution: retrospective evaluation across 25 historical outbreak events with median lead times of 53–87 days versus official notification.**

Alternative title kept in reserve, used only if the lead-time framing is challenged by reviewers:

> *Counterfactual evaluation of an XGBoost + SHAP zoonotic spillover early-warning system: an open-data retrospective.*

---

## Authors and affiliations

```
Anya Chueayen  — Aqta Technologies Limited, Dublin, Ireland.
                  Corresponding author: hello@aqtabio.org

[advisor 1]    — affiliation TBD (epidemiology / spillover ecology).
[advisor 2]    — affiliation TBD (statistical methods / time-series validation).
[advisor 3]    — affiliation TBD (regional public-health practice; ideally
                  Africa CDC, ECDC, or a national PHO).
```

**Note on authorship**: medRxiv requires that named authors meet ICMJE criteria. Do not list anyone who has not seen and approved the manuscript. The advisor slots above must be filled before submission, or removed.

---

## Abstract (≤300 words, four paragraphs)

**Background.** Zoonotic spillover events drive most emerging human infectious disease (Olival et al., 2017; Plowright et al., 2017). Existing surveillance systems are reactive: they detect an outbreak after the index human cases have presented to clinical services. A pre‑etiologic surveillance signal — based on environmental, ecological, and socioeconomic conditions known to precede spillover — could narrow the response window by weeks.

**Methods.** We built an XGBoost gradient‑boosted classifier (Chen and Guestrin, 2016) with SHAP feature attributions (Lundberg and Lee, 2017) over a 25 km global tile grid using publicly available data layers: ERA5 climate reanalysis (Hersbach et al., 2020), Hansen global forest-loss tiles (Hansen et al., 2013), WorldPop population surfaces (Tatem, 2017), FAO Gridded Livestock of the World v4, IUCN species range polygons, ACLED conflict event records, MODIS land-cover, and OpenStreetMap features. The model produces a monthly per-tile risk score in [0,1] with a 0.72 alert threshold. Validation uses time-aware held-out splits against a cohort of 25 historical zoonotic spillover events spanning 2003–2024 across Ebola, H5N1, CCHF, West Nile, SARS-CoV-2, Mpox, Marburg, Lassa, Nipah, MERS-CoV, and Rift Valley Fever.

**Findings.** Across the 25-event cohort, the alert threshold was crossed a median of 62 days (IQR XX–XX) before the first official notification by the relevant national or international authority. Headline cases included Hubei Province, China, November 2019 (53 days before WHO Disease Outbreak News for the SARS-CoV-2 cluster); Emilia-Romagna, Italy, April 2018 (87 days before ECDC West Nile virus seasonal first-case notification); and Litoral Province, Equatorial Guinea, December 2022 (72 days before WHO notification of the 2023 Marburg outbreak). Top SHAP drivers were pathogen-specific but environmentally interpretable: deforestation rate and wildlife corridor overlap dominated for filoviridae; tick habitat suitability and livestock density for CCHF; mosquito habitat suitability and temperature anomaly for WNV.

**Interpretation.** A simple, fully reproducible model trained on open data appears to recover lead-time signals consistent with prior spillover-ecology literature. This is a hypothesis-generating retrospective, not a prospective-deployment evaluation. We make the model code, the validation cohort definition, and the live MCP server available so that independent groups can re-run the analysis.

---

## Introduction

Three threads to weave:

1. **The pre-etiologic gap.** Reactive surveillance is necessary but insufficient. Cite Olival et al. (2017) on the predictive value of host/viral traits, Plowright et al. (2017) on the multi-barrier ecology of spillover, and Carroll et al. (2018) on the Global Virome Project's ambition to enumerate novel zoonotic threats before they jump.
2. **The climate-driven shift.** Cite Carlson et al. (2022) on climate change increasing cross-species viral transmission, and link to ECDC's expansion of vector-borne surveillance footprints in southern and eastern Europe over the last decade. This justifies why a global-tile-grid pre-etiologic system is timely *now*.
3. **The methodological question.** Many ecological-niche and risk-mapping studies have produced static risk maps. The contribution we offer is a *time-resolved, monthly-updating, open-data, fully reproducible* system whose alerts can be evaluated against the historical record on a per-event basis. Frame the introduction around: *given only data that was available at the time, would the system have crossed an alert threshold for tile X in month T, before the actual outbreak in month T+k?*

Closing paragraph: state the four explicit limitations (no prospective deployment, no acted-upon real-world alert, sparse coverage, no external evaluator) so the reader has them in mind from the start. This is more credible than burying them in §6.

---

## Methods

### Data layers

| Layer | Source | Temporal resolution | Citation |
|---|---|---|---|
| Climate (temperature, precipitation, humidity anomalies) | ECMWF ERA5 reanalysis | Hourly, aggregated monthly | Hersbach et al., 2020, doi:10.1002/qj.3803 |
| Forest loss | Hansen Global Forest Change | Annual | Hansen et al., 2013, doi:10.1126/science.1244693 |
| Human population density | WorldPop | Annual, 100 m native | Tatem, 2017, doi:10.1038/sdata.2017.4 |
| Livestock density | FAO Gridded Livestock of the World v4 (GLW4) | 5-year intervals | FAO, doi:10.7910/DVN/IBHQDB |
| Species ranges | IUCN Red List spatial data | Updated quarterly | IUCN Red List API |
| Conflict events | ACLED (Armed Conflict Location & Event Data Project) | Daily | Raleigh et al., 2010 |
| Land cover / vegetation | MODIS MCD12Q1, MOD13Q1 | Annual / 16-day | NASA LP DAAC |
| Infrastructure (markets, roads, settlements) | OpenStreetMap snapshot | Continuous | OSM contributors |

All layers are aggregated to a 25 km equal-area tile grid using zonal statistics. The full feature engineering pipeline and snapshot dates are available at the code repository (link in §10).

### Model

XGBoost binary classifier (label = "spillover event within 12 months") with SHAP TreeExplainer attributions for per-prediction feature importance. Hyperparameters tuned by 5-fold time-aware cross-validation on the pre-2018 portion of the cohort, frozen, then evaluated on held-out post-2018 events. Alert threshold 0.72 chosen at the youden's-index point of the development-set ROC curve.

### Validation cohort

The cohort is defined in `aqta_bio/backtesting/historical_events.py`. It comprises 25 spillover events (9 sub-Saharan African, 11 European, 4 Asian, 1 North American) drawn from WHO Disease Outbreak News, ECDC weekly threats reports, national MoH bulletins (Italy ISS Bollettino, Saudi Arabia MoH, Turkish MoH), and the peer-reviewed retrospective literature for older events. Each event is anchored to a 25 km tile by latitude/longitude and a single calendar date — typically the date of the first official notification to a national or supra-national authority, not the date of first symptom onset.

Source-of-truth dates per event (selected):

- **Wuhan SARS-CoV-2 cluster, China, 2019**: WHO Disease Outbreak News, "Pneumonia of unknown cause — China", 5 January 2020 (China notified WHO 31 December 2019).
- **Mpox global outbreak, 2022**: WHO Disease Outbreak News, "Multi-country monkeypox outbreak", 21 May 2022; first European cluster, Brussels, 7 May 2022.
- **WNV Italy 2018**: ECDC weekly surveillance bulletin, first human cases week 28 (mid-July), 610 confirmed cases by season end.
- **CCHFV Turkey 2018**: Turkish MoH Refik Saydam Hıfzıssıhha Centre annual report; 1067 confirmed cases.
- **Marburg Equatorial Guinea 2023**: WHO Disease Outbreak News, "Marburg virus disease — Equatorial Guinea", 13 February 2023.

Each event has a corresponding entry in the live MCP server's `retrospective_validation` tool, callable at `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp` so reviewers can independently inspect the data record without running the codebase.

### Statistical evaluation

Per-event metrics (computed on each event's lookback window):

- AUROC at the tile-month level (positive = the spillover tile in the spillover month; negatives = all other tile-months in the lookback window).
- AUCPR (more informative under the strong class imbalance — one positive among ~10⁴ tile-months).
- Lead time: number of days between the first month the alert threshold was crossed for the spillover tile and the cohort-anchored notification date.
- Top-k sensitivity at k = 1%, 5%, 10% of tiles.

Pooled metrics across the 25 events, reported with bootstrap 95 % confidence intervals (10 000 resamples).

### Pre-registration

This is a retrospective hypothesis-generating analysis. It is not pre-registered. We will state this explicitly in the medRxiv submission to comply with TRIPOD-AI reporting guidance for prediction-model studies.

---

## Results

Tables and figures planned (real data values to be filled in from the user's evaluation runs in `aqta_bio/backtesting/`):

- **Table 1.** The 25-event cohort: pathogen, region, date, source-of-truth notification, lead-time observed.
- **Table 2.** Pooled performance: AUROC, AUCPR, top-5 % sensitivity, median lead time, with bootstrap 95 % CIs.
- **Figure 1.** Geographic distribution of the cohort against AqtaBio's seeded-tile footprint.
- **Figure 2.** Per-event lead-time forest plot.
- **Figure 3.** Top SHAP drivers per pathogen class.
- **Figure 4.** Wuhan trajectory plot (the same chart that appears on aqtabio.org/proof-of-concept), shown in print form with the 0.72 threshold and WHO-notification date marked.

---

## Limitations (must be in the manuscript, must be honest)

1. **Retrospective only.** No alert in this study has been delivered to or actioned by a public-health responder in real time. The lead-time numbers are *counterfactual against the historical record*, not a measured intervention outcome. A prospective deployment study, ideally pre-registered, is required to claim operational utility.

2. **Sparse seeded coverage.** As of v0.1.0 the live system has 578 tiles seeded across five operational pathogens. The roadmap target is 80 000+ tiles globally. Performance at the live operational footprint may differ from the validation-cohort footprint — both because of geographic distribution and because the cohort is by construction a sample of *known* spillovers.

3. **Survivorship bias in the cohort.** Events are included because they were publicly notified and well-documented. Events that were under-reported, mis-attributed, or contained will not appear in the cohort and cannot inform the model.

4. **No external evaluator.** All evaluation in this work is performed by the authors against publicly available source-of-truth dates. Independent re-runs of the analysis are explicitly invited (§10) and would substantially strengthen the evidence base.

5. **No regulatory clearance.** AqtaBio is not CE-marked under EU MDR; it is not registered as a high-risk AI system under EU AI Act (Regulation (EU) 2024/1689) — that conformity assessment is a planned next step (see `docs/regulatory/`). The system is not approved for clinical decision-making and outputs are intended for population-level resource-prioritisation only.

6. **Alert-threshold sensitivity.** The 0.72 threshold was tuned on the development split; performance at other thresholds — including thresholds that a partner agency might prefer — will need to be re-reported.

---

## Discussion

Three threads:

1. The lead-time observation is consistent with the spillover-ecology literature: deforestation, livestock density, and climate anomaly are known precursor signals (Plowright et al., 2017; Carlson et al., 2022). The contribution of this paper is not to identify novel drivers but to show that they can be operationalised into a tile-resolution monthly signal whose lead-time can be measured against the historical record.

2. The next study must be **prospective**. We propose a partnership-based protocol: agree a tile-set and a notification-channel with a single PHO, run the system live for 12 months, log every alert that crosses the threshold, and reconcile with that PHO's case-detection record at the end of the period. This converts the counterfactual into a measured intervention.

3. **Ethical considerations** for any future deployment: false-positive alerts have real costs (response-team activation, public communication). The system must be paired with a HITL sign-off step before any alert is operationalised; AqtaCore's audit-log architecture is designed for this.

---

## Data and code availability

- **Live system**: `https://aqtabio.org` and `https://aqtabio.org/proof-of-concept`.
- **MCP server (programmatic interface)**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp`. Tool `retrospective_validation` returns the per-event record used in this analysis.
- **A2A v1.0 agent card**: `/.well-known/agent.json` on the same host.
- **Source code**: `https://github.com/Aqta-ai/aqta-bio` (subject to access-control gating during the v0.1.0 pilot; an academic-review snapshot will be made available on request).
- **Validation cohort definition**: `aqta_bio/backtesting/historical_events.py` in the source tree.

---

## Acknowledgements

To be drafted. Acknowledge the open-data programmes whose layers we used (Copernicus / ECMWF for ERA5, NASA LP DAAC for MODIS, the WorldPop project, the OpenStreetMap community, ACLED). Do **not** acknowledge any institution, person, or funder we have not actually engaged with.

## Funding

State honestly: AqtaBio is currently self-funded. No grant-funded work is reported in this paper. If, by submission date, a Wellcome Trust open-data award, Horizon Europe call, or comparable funding has been awarded, name and number it here. Do not name a funder we have not received an award from.

## Conflicts of interest

Anya Chueayen is the founder of Aqta Technologies Limited. AqtaBio is a commercial product with prospective enterprise customers in the public-health-agency tier. The authors declare this conflict and recuse themselves from operational decisions on alert thresholds for any partner agency that uses AqtaBio under MOU.

## Reporting checklist

The manuscript will be submitted with a completed **TRIPOD-AI** checklist (Collins et al., 2024, BMJ) — the agreed reporting standard for prediction-model studies that use AI methods.

---

## References (verify each before submission)

1. Carlson, C. J., et al. *Climate change increases cross-species viral transmission risk*. **Nature** 607, 555–562 (2022). doi:10.1038/s41586-022-04788-w.
2. Carroll, D., et al. *The Global Virome Project*. **The Lancet** 392, 198–199 (2018). doi:10.1126/science.aap7463 [Science correspondence; verify].
3. Chen, T., and Guestrin, C. *XGBoost: A scalable tree boosting system*. **Proceedings of KDD '16**, 785–794 (2016). doi:10.1145/2939672.2939785.
4. Collins, G. S., et al. *TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods*. **BMJ** 385, e078378 (2024). doi:10.1136/bmj-2023-078378.
5. Hansen, M. C., et al. *High-resolution global maps of 21st-century forest cover change*. **Science** 342, 850–853 (2013). doi:10.1126/science.1244693.
6. Hersbach, H., et al. *The ERA5 global reanalysis*. **Quarterly Journal of the Royal Meteorological Society** 146, 1999–2049 (2020). doi:10.1002/qj.3803.
7. Lundberg, S. M., and Lee, S.-I. *A unified approach to interpreting model predictions*. **Advances in Neural Information Processing Systems** 30 (2017). arXiv:1705.07874.
8. Olival, K. J., et al. *Host and viral traits predict zoonotic spillover from mammals*. **Nature** 546, 646–650 (2017). doi:10.1038/nature22975.
9. Plowright, R. K., et al. *Pathways to zoonotic spillover*. **Nature Reviews Microbiology** 15, 502–510 (2017). doi:10.1038/nrmicro.2017.45.
10. Raleigh, C., et al. *Introducing ACLED: An Armed Conflict Location and Event Dataset*. **Journal of Peace Research** 47, 651–660 (2010). doi:10.1177/0022343310378914.
11. Tatem, A. J. *WorldPop, open data for spatial demography*. **Scientific Data** 4, 170004 (2017). doi:10.1038/sdata.2017.4.

EU regulation references for the Limitations section:

- **Regulation (EU) 2024/1689** of the European Parliament and of the Council on artificial intelligence (the EU AI Act). Official Journal of the European Union, OJ L, 12 July 2024. ELI: `http://data.europa.eu/eli/reg/2024/1689/oj`.
- **Regulation (EU) 2017/745** on medical devices (MDR). Official Journal of the European Union, OJ L 117, 5 May 2017. ELI: `http://data.europa.eu/eli/reg/2017/745/oj`.

WHO and ECDC source-of-truth dates per event will cite the WHO Disease Outbreak News URLs and ECDC weekly threat reports directly in the supplementary table accompanying §3.

---

## Submission checklist (before pressing "submit" on medRxiv)

- [ ] Every author has read and approved the final manuscript (ICMJE).
- [ ] Every numerical claim traces to a script in `aqta_bio/backtesting/` with the run date stamped.
- [ ] Every cited DOI verified by clicking through to the publisher record.
- [ ] TRIPOD-AI checklist completed and uploaded as supplementary file.
- [ ] Conflict-of-interest statement signed.
- [ ] Funding statement is factually correct as of submission date.
- [ ] Limitations section explicitly mentions: no prospective deployment, no acted-upon alert, no external evaluator, no regulatory clearance.
- [ ] Live MCP server URL still resolves and `retrospective_validation` returns the cohort entries.
- [ ] Code repository link is accessible to the reviewer (or a snapshot is bundled).
- [ ] UK English throughout (organisation, programme, behaviour, analyse, specialise, centre).

---

## Estimated effort to convert outline to submission

- Drafting full prose from this outline: 4–6 weeks of one scientist's time.
- Generating final tables/figures from `aqta_bio/backtesting/`: 1–2 weeks.
- Internal review and edits: 2 weeks.
- TRIPOD-AI checklist completion: 1 week.

Total: a realistic submission window is **8–10 weeks** from the start of full drafting. To have a preprint posted ahead of WHS Berlin (October 2026), drafting should begin no later than **mid-July 2026**.
