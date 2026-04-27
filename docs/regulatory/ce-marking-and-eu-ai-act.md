# Regulatory Pathway Note: EU AI Act High-Risk Conformity and CE Marking

**Status**: planning document, not a status report. As of the date below, AqtaBio has **not** submitted any conformity assessment, has **not** engaged a notified body, and has **no** CE mark, FDA clearance, or AI Act conformity declaration. The purpose of this document is to set out the route we will take and the order in which we will take it, so that pilot partners, regulators, and grant-making bodies can read a single document and understand our regulatory posture.

**Last reviewed**: 25 April 2026.
**Owner**: Anya Chueayen, Aqta Technologies Limited (Dublin, Ireland — registered company in the European Union, primary regulatory jurisdiction).

---

## Executive summary

1. AqtaBio is a candidate **high-risk AI system** under the EU AI Act (Regulation (EU) 2024/1689), Annex III §5(a) — public authorities using AI to evaluate eligibility for, or to grant or revoke, essential public services including healthcare services. We will pursue conformity with the AI Act's high-risk regime as the primary regulatory commitment.
2. AqtaBio in its current population-level risk-prioritisation use case is **not** a medical device under the EU MDR (Regulation (EU) 2017/745), because its outputs do not drive clinical decisions for individual patients. CE marking under MDR is therefore not required for the current scope. The note below is explicit about the boundary so that any future expansion into clinical decision support triggers a re-classification review *before* deployment, not after.
3. **FDA SaMD** (Software as a Medical Device) submission is **not in scope** for v0.1.0. The US is not a primary market for the pilot phase; we will revisit this in 2027 if a US public-health partner asks.
4. The **gap analysis** against the AI Act high-risk requirements (Articles 8–17) has not yet been performed. Starting it is the single most important next regulatory action.

---

## Why the EU AI Act is the right primary regime

### Classification under the AI Act

Regulation (EU) 2024/1689 entered into force on 1 August 2024, with phased application: prohibitions from 2 February 2025, governance obligations and obligations on general-purpose AI models from 2 August 2025, **high-risk system obligations from 2 August 2026** (Article 113). The high-risk obligations are therefore the regime AqtaBio must be ready for, with a hard deadline that aligns roughly with the WHS Berlin window.

Article 6(2) of the Act, read with Annex III, lists eight high-risk use-case areas. Two are potentially relevant to AqtaBio:

- **Annex III §5 — "Access to and enjoyment of essential private services and essential public services and benefits"**, in particular §5(a):
  > *AI systems intended to be used by public authorities, or on behalf of public authorities, to evaluate the eligibility of natural persons for essential public assistance benefits and services, including healthcare services, as well as to grant, reduce, revoke, or reclaim such benefits and services.*
- **Annex III §5(d) — emergency-call triage**:
  > *AI systems intended to be used to evaluate and classify emergency calls by natural persons or to be used to dispatch, or to establish priority in the dispatching of, emergency first response services, including by police, firefighters and medical aid, as well as of emergency healthcare patient triage systems.*

AqtaBio's intended use is **resource-prioritisation for surveillance and outbreak preparedness at the population level by public-health agencies**. This sits closer to §5(a) than to §5(d): we do not triage emergency calls or individual patients, but our outputs influence how a public authority allocates surveillance capacity, which in turn affects population access to early detection. The Article 6(3) "filter" allows a provider to argue that a system listed in Annex III does not pose significant risk to fundamental rights, but the documentation burden of that argument is comparable to the conformity burden, and the precedent for AI in public-health administration sits squarely within the high-risk regime. We will therefore proceed on the assumption that AqtaBio is a high-risk AI system and pursue conformity accordingly.

### What conformity entails (Articles 8–17)

The high-risk obligations the provider must satisfy:

| Article | Obligation | AqtaBio current state |
|---|---|---|
| 9 | Risk-management system | Initial AqtaCore 8-layer governance scaffold exists; no formal ISO 14971 risk-management process. **Gap**. |
| 10 | Data and data governance | Public open-data sources only at present (ERA5, Hansen, WorldPop, FAO GLW4, IUCN, ACLED, MODIS, OSM); data-quality and bias documentation partial. **Gap**. |
| 11 | Technical documentation (Annex IV) | Architecture exists in code and READMEs; not yet structured as Annex IV technical-file. **Gap**. |
| 12 | Record-keeping (logging) | Audit-log architecture exists; needs to be tested against the Annex IV log retention and access controls. **Partial**. |
| 13 | Transparency and information to users | `aqtabio.org/proof-of-concept`, `/methodology`, and `/data-governance` cover the user-facing transparency baseline; no formal Annex IV "instructions for use" yet. **Partial**. |
| 14 | Human oversight | HITL sign-off step is implemented in the AqtaCore framework; needs formal documentation and evidence of operator competency. **Partial**. |
| 15 | Accuracy, robustness, cybersecurity | AUROC / AUCPR retrospective metrics in `aqta_bio/model/`; cybersecurity baseline exists; no penetration test on file. **Partial**. |
| 17 | Quality-management system | No QMS in place. **Gap**. ISO/IEC 42001:2023 (AI management system) is the canonical standard for satisfying this; ISO/IEC 27001 (information security) is a strong complement. |

**Honest assessment**: roughly half-and-half "Partial" / "Gap". No section is in the "Done" column. The QMS gap is the largest single piece of work.

### Conformity assessment route

Annex VI / VII of the AI Act sets out the assessment routes for high-risk systems. For Annex III §5 systems, the default route is internal control by the provider (Annex VI) — no notified body required for the AI-Act conformity itself. This is meaningfully easier than the MDR path for medical devices.

Engaging a notified body remains worthwhile for a **voluntary informal pre-assessment**: BSI Group (UK), TÜV SÜD (DE), DEKRA (DE), and CSA Group (CA, EU-notified) all run AI-Act readiness advisory practices. The cost is in the low five-figure range (€) for a focused gap-analysis engagement. This is on the 12-month roadmap below.

---

## Why MDR / CE marking is *not* required for the current scope

Regulation (EU) 2017/745 (MDR) defines a medical device as an instrument, software or article intended by the manufacturer to be used for, *inter alia*, "diagnosis, prevention, monitoring, prediction, prognosis, treatment or alleviation of disease" (MDR Article 2(1)). The scope of "medical device" software is materially expanded by the MDCG 2019-11 guidance and EU case-law on Snitem & Philips (Case C‑329/16), which together establish that risk-stratification software is a medical device when it acts on data from an *individual patient* with the intention of supporting clinical decisions for that patient.

AqtaBio's outputs are **per-tile, population-level risk indices** with no patient identifier and no clinical-decision intent. The software does not act on data from any individual patient, does not produce a clinical recommendation for any individual patient, and is not labelled or marketed for that use. On the current scope, AqtaBio is therefore not a medical device under MDR. CE marking under MDR is not required.

**Boundary statement (must be repeated in any partner-facing documentation)**: if AqtaBio were used to drive clinical decisions for individual patients — for example, to feed into an EHR alert that prompts a clinician to test a specific patient for an enumerated pathogen — the use case would re-enter MDR scope, likely as Class IIa or IIb software. We will not deploy AqtaBio in that mode without first triggering an MDR conformity assessment.

---

## What we will pursue, in what order

A 12-month sketch. None of these milestones is currently in flight; this is the plan, not a status report. Dates assume a starting point of **Q3 2026**.

### Months 0–2: Gap analysis and QMS bootstrap

- Complete a written gap analysis against AI Act Articles 8–17, mapping each obligation to the existing AqtaCore controls and itemising what is missing. Output: a controlled document, version 1.0, retained as the first entry in the AqtaCore controlled-document register.
- Adopt the **ISO/IEC 42001:2023** (Artificial Intelligence Management System) standard as the QMS framework. ISO/IEC 42001 is the canonical international standard for an AI management system and is explicitly recognised by AI-Act readiness advisors.
- Stand up a controlled-document register, change-control workflow, and an AI-system risk register.

### Months 2–4: Technical documentation (Annex IV)

- Assemble the Annex IV technical file:
  - General description of the AI system, intended purpose, intended users.
  - Data sheets for every training/feature dataset (ERA5, Hansen, WorldPop, FAO GLW4, IUCN, ACLED, MODIS, OSM) and their licences.
  - Model card per ISO/IEC 5259 family conventions (data quality, bias considerations).
  - Performance metrics on the held-out 25-event cohort (AUROC, AUCPR, lead-time distribution) — same numbers that anchor the medRxiv preprint.
  - Cybersecurity controls: penetration-test plan, threat model, incident-response protocol.

### Months 4–6: Notified-body pre-assessment

- Engage one of BSI Group / TÜV SÜD / DEKRA for a voluntary AI-Act readiness pre-assessment (typical engagement: 6–10 weeks, budget mid-five-figures €).
- Address findings; iterate the technical file.

### Months 6–9: Transparency and human-oversight evidence

- Author the Annex IV "instructions for use" document for users (PHO operators).
- Document the HITL sign-off workflow with operator-competency requirements and evidence of competency-checks performed during pilots.
- Update `aqtabio.org/data-governance` to reflect AI-Act-aligned transparency disclosures.

### Months 9–12: Self-declaration of conformity (Annex VI route)

- For Annex III §5 systems on the internal-control route, the provider draws up the EU declaration of conformity (Article 47), affixes the CE marking *to the AI system if applicable* (in software-only systems, this is a metadata declaration), and registers in the EU AI Database (Article 71). This is the formal endpoint of the AI-Act conformity path.
- Maintain the post-market monitoring system (Article 72) and be ready to file serious-incident reports under Article 73 within the prescribed 15-day window.

### Voluntary alignment beyond the AI Act minimum

Even though MDR does not apply, and even though several of the following standards are not AI-Act-mandatory, partner agencies and regulators routinely ask about them. Voluntary alignment is therefore worth pursuing in parallel:

- **ISO 14971:2019** — application of risk management to medical devices. Useful framing even in non-device contexts.
- **ISO/IEC 23894:2023** — guidance on risk management for AI. Companion to 42001.
- **ISO/IEC 27001:2022** — information-security management. Strong signal to enterprise and government customers.
- **GDPR Article 35 DPIA** — Data Protection Impact Assessment. AqtaBio currently processes only open population-level data, with no personal data, but a DPIA is the right document for any future ingest of agency-private data.

---

## Honest gap statement (for reuse in pilot conversations and grant applications)

> AqtaBio v0.1.0 has not yet completed conformity assessment under any regulatory regime. The product team has identified the EU AI Act (Regulation (EU) 2024/1689) high-risk regime as the primary applicable framework on the basis that AqtaBio's intended users are public authorities making resource-prioritisation decisions for essential public services (Annex III §5(a)). The team has identified that the EU MDR does not apply to the current population-level scope, and has documented the boundary at which any future clinical-individual scope would re-enter MDR. A formal gap analysis against AI Act Articles 8–17 is the next planned step, with a target completion of within 60 days of the start of regulatory work. No notified body has yet been engaged. No CE marking, FDA clearance, or AI Act conformity declaration is claimed for v0.1.0.

This paragraph is written to be quoted verbatim, with no edits, in the methods or limitations section of the medRxiv preprint, in pilot-LOI follow-up emails, and in grant applications.

---

## Authoritative references

The following are the primary legal and standards instruments referenced above. Verify each link before any external use.

- **EU AI Act**. Regulation (EU) 2024/1689 of the European Parliament and of the Council of 13 June 2024 laying down harmonised rules on artificial intelligence. Official Journal of the European Union, 12 July 2024. ELI: <http://data.europa.eu/eli/reg/2024/1689/oj>.
- **EU AI Act, Annex III** (high-risk use cases). EUR-Lex consolidated text section. The "essential public services and benefits" category is §5; healthcare services are explicitly named within §5(a).
- **EU MDR**. Regulation (EU) 2017/745 of the European Parliament and of the Council of 5 April 2017 on medical devices. Official Journal of the European Union, OJ L 117, 5 May 2017. ELI: <http://data.europa.eu/eli/reg/2017/745/oj>.
- **MDCG 2019-11**. Guidance on qualification and classification of software in Regulation (EU) 2017/745 — MDR and Regulation (EU) 2017/746 — IVDR. Medical Device Coordination Group, October 2019. <https://health.ec.europa.eu/document/download/52d1fe46-bb35-4f7b-8266-e6b8a8073d75_en?filename=md_mdcg_2019_11_guidance_qualification_classification_software_en.pdf>.
- **CJEU Snitem & Philips (Case C-329/16)**. Court of Justice of the European Union judgment on the qualification of clinical-decision-support software as a medical device, 7 December 2017. ECLI: ECLI:EU:C:2017:947.
- **ISO/IEC 42001:2023**. Information technology — Artificial intelligence — Management system. International Organization for Standardization, 2023.
- **ISO/IEC 23894:2023**. Information technology — Artificial intelligence — Guidance on risk management. International Organization for Standardization, 2023.
- **ISO 14971:2019**. Medical devices — Application of risk management to medical devices. International Organization for Standardization, 2019.
- **ISO/IEC 27001:2022**. Information security, cybersecurity and privacy protection — Information security management systems. International Organization for Standardization, 2022.
- **GDPR Article 35**. Regulation (EU) 2016/679 (General Data Protection Regulation), Article 35 — Data protection impact assessment.

---

## Caveat

This document is *not* legal advice. Aqta Technologies Limited has not engaged external regulatory counsel as of the date above. Before AqtaBio is deployed for any production use that affects real-world public-health decisions, qualified EU regulatory counsel and a notified body's input must be sought. The document is intended for internal planning and for transparent disclosure to pilot partners; it is not a substitute for an independently reviewed conformity assessment.
