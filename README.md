# Marlo Scientific

### Pharmaceutical Intelligence & Computational Pharmacology Platform

Marlo Scientific is a research-oriented software platform designed to integrate clinical trial intelligence, pharmaceutical knowledge, regulatory evidence, and computational pharmacology into a unified scientific environment.

The platform aims to provide researchers, pharmaceutical scientists, clinical research professionals, and regulatory affairs specialists with tools for exploring drug development evidence, investigating pharmacological mechanisms, and conducting computational research.

Marlo Scientific is currently under active development.

---

## Project Overview

Pharmaceutical research involves information distributed across clinical trial registries, regulatory publications, scientific literature, drug databases, and computational models.

Marlo Scientific is being developed to connect these resources within a structured research environment.

The platform combines three principal areas:

1. **Clinical Intelligence** — Clinical trial discovery, disease research, and treatment evidence.
2. **Pharmaceutical & Regulatory Intelligence** — Drug knowledge, mechanisms, safety information, and regulatory references.
3. **Computational Pharmacology** — Pharmacokinetic modeling, pharmacodynamic research, and experimental patient simulations.

The long-term objective is to establish an integrated scientific platform that supports evidence-based research throughout the drug development lifecycle.

---

## Core Capabilities

### 1. Clinical Trials Intelligence

The Clinical Intelligence system retrieves, processes, and organizes clinical study information.

Current development includes:

- ClinicalTrials.gov data integration.
- Clinical trial discovery by disease or condition.
- Study identification and classification.
- Trial status and recruitment analysis.
- Study phase and intervention analysis.
- Sponsor and collaborator information.
- Eligibility criteria extraction.
- Clinical outcome identification.
- Research cohort organization.
- Trial evidence snapshots.
- Research workspaces and saved analyses.

The system supports structured analysis of clinical trial information and provides a foundation for disease-specific research.

### 2. Pharmaceutical Intelligence

Marlo Scientific includes a pharmaceutical knowledge layer designed to organize drug-related scientific information.

Components include:

- Drug identity and alias normalization.
- Drug mechanisms of action.
- Pharmacological target information.
- Drug safety references.
- Drug interaction evidence.
- Intervention classification.
- Drug research capabilities.
- Scientific evidence organization.

These components are intended to connect medications with their clinical, pharmacological, and regulatory evidence.

### 3. Regulatory Intelligence

The regulatory intelligence components support the organization and examination of regulatory information relevant to pharmaceutical development.

Current development areas include:

- Regulatory reference datasets.
- Regulatory evidence views.
- Drug safety documentation.
- Source traceability.
- Scientific evidence review.
- Research documentation.
- Model verification records.

Future development may expand these capabilities to support additional regulatory research and drug lifecycle workflows.

### 4. Patient Lab

Patient Lab is an experimental research environment for exploring computational pharmacology using structured synthetic patient scenarios.

Developed components include:

- Synthetic patient-state representation.
- Patient characteristic management.
- Saved research scenarios.
- Patient-state revisions.
- Scenario comparison.
- Pharmacokinetic input preparation.
- Educational pharmacokinetic calculations.
- Model applicability assessments.
- Scientific verification workflows.

Patient Lab is intended for computational research and educational exploration.

It is not currently validated for clinical treatment recommendations or patient-specific therapeutic predictions.

### 5. Simulation Lab

Simulation Lab provides a developing environment for investigating pharmacological processes through computational models.

Implemented research components include:

**Pharmacokinetics**
- Drug concentration–time calculations.
- Drug exposure analysis.
- Pharmacokinetic parameter evaluation.
- Parameter sensitivity analysis.
- Treatment schedule exploration.

**Pharmacodynamics**
- Target occupancy modeling.
- Drug–target binding kinetics.
- Protein turnover modeling.
- Exposure–response relationships.
- Delayed-response and transit models.

**Scientific Evaluation**
- Synthetic numerical experiments.
- Model comparison.
- Evidence-based parameter review.
- Assumption sensitivity analysis.
- Computational verification.

These components form the foundation for future integrated physiological simulations.

---

## Scientific Research Areas

Marlo Scientific currently includes research and development work involving selected pharmaceutical models and disease datasets.

### Multiple Myeloma

Clinical trial intelligence development has included a research cohort containing more than 4,000 clinical trial records.

Research activities include:

- Clinical trial classification.
- Intervention normalization.
- Drug alias mapping.
- Treatment regimen identification.
- Pharmaceutical evidence curation.

### Lenalidomide

Research components include:

- Pharmacokinetic model development.
- Renal pharmacokinetic evidence.
- Published population pharmacokinetic model review.
- Model parameter transcription.
- Scientific source verification.
- Model applicability assessment.

### Bortezomib

Experimental research components include:

- Proteasome-related pharmacological modeling.
- Drug exposure and time-course analysis.
- Scientific observation review.
- Evidence comparison.
- Model assumption sensitivity analysis.

These research implementations are experimental and should not be interpreted as clinically validated prediction systems.

---

## Technology Stack

Marlo Scientific is primarily developed using Python and Flask.

| Technology | Application |
|------------|-------------|
| Python | Scientific computing and backend development |
| Flask | Web application framework |
| SQLAlchemy | Database integration |
| Alembic | Database migrations |
| HTML | Application interface |
| CSS | Interface design |
| JavaScript | Interactive functionality |
| JSON | Structured scientific reference data |
| Git | Version control |
| GitHub | Source code management |

The architecture separates scientific computation, application interfaces, research data, and software verification.

---

## Project Architecture

The repository is organized into the following primary components:

```text
marlo-scientific/
│
├── app/
│   ├── app.py
│   ├── static/
│   └── templates/
│
├── intelligence_store/
│   ├── data/
│   ├── pharmacokinetics.py
│   ├── protein_turnover.py
│   ├── target_occupancy.py
│   ├── target_binding_kinetics.py
│   ├── patient_state.py
│   ├── drug_knowledge.py
│   ├── regulatory.py
│   └── ...
│
├── landscape_ui/
│   ├── templates/
│   ├── static/
│   ├── simulation_lab_pages.py
│   ├── patient_lab_overview_pages.py
│   ├── drug_knowledge_pages.py
│   └── ...
│
├── intelligence_migrations/
│
├── docs/
│
├── examples/
│
├── scripts/
│
├── tests/
│
├── requirements.txt
└── README.md
```

### Component Responsibilities

**app/**

Contains the main Flask application and application entry-point components.

**intelligence_store/**

Contains scientific computation, pharmaceutical knowledge, patient modeling, clinical trial processing, and associated data structures.

**landscape_ui/**

Contains the primary research interface, including Flask page modules, HTML templates, CSS, and JavaScript.

**intelligence_migrations/**

Contains database migration definitions.

**docs/**

Contains development documentation, scientific evidence reviews, verification protocols, and research planning materials.

**examples/**

Contains synthetic research examples and numerical test inputs.

**scripts/**

Contains scientific verification utilities, research workflows, and development scripts.

**tests/**

Contains automated tests for application functionality and scientific calculations.

---

## Local Development

### Requirements

- Python 3
- pip
- Git
- Project dependencies listed in `requirements.txt`

### Clone the Repository

```bash
git clone https://github.com/astridcmarin/marlo-scientific.git

cd marlo-scientific
```

### Create a Virtual Environment

```bash
python3 -m venv .venv
```

Activate the environment on macOS or Linux:

```bash
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Start the Application

From the repository root, with the virtual environment active:

```bash
export PYTHONPATH=.                    # lets Flask find intelligence_store and landscape_ui
flask --app app/app.py db upgrade      # create or update the database schema
flask --app app/app.py run
```

Open http://127.0.0.1:5000 for the landing page, http://127.0.0.1:5000/trials for the trial explorer and http://127.0.0.1:5000/landscape/ for the research workspace. Older search links of the form `/?condition=…` redirect to `/trials`.

By default the database is SQLite at `instance/intelligence.db`; set `DATABASE_URL` to use another database. A workspace signing key is generated in `instance/` on first use. The `instance/` folder is ignored by git.

Command-line tools are registered on the same app, for example `flask --app app/app.py covariate-estimate --example --compare-bases`. Run `flask --app app/app.py --help` for the full list.

### Run Tests

The project includes automated tests using Python testing utilities.

Run the same unittest discovery command used by GitHub Actions:

```bash
python -m unittest discover -s tests
```

The optional live ClinicalTrials.gov smoke check is separate from test discovery: `python scripts/smoke_clinicaltrials_api.py`. It requires network access. Containerization is not yet implemented.

See [the documentation index](docs/README.md) and [the current repository checkpoint](docs/REPOSITORY_CHECKPOINT.md) for implemented capabilities and outstanding scientific work.

Scientific model tests should be run whenever computational models or their supporting evidence contracts are modified.

---

## Scientific Verification and Validation

Scientific traceability is a central development principle of Marlo Scientific.

The platform incorporates research workflows for:

- Source documentation.
- Parameter provenance.
- Scientific assumption review.
- Numerical verification.
- Model applicability assessment.
- Computational reproducibility.
- Evidence integrity checks.
- Validation status reporting.

Software verification and scientific validation are treated as separate requirements.

Passing automated software tests does not establish that a computational model is clinically predictive.

Models must undergo appropriate scientific verification and validation before their outputs can be considered suitable for higher-stakes applications.

---

## Development Roadmap

Marlo Scientific is being developed incrementally.

### Phase 1 — Clinical and Pharmaceutical Intelligence

Develop structured research capabilities for clinical trials, medications, disease information, and scientific evidence.

**Status:** Substantial implementation; ongoing development.

### Phase 2 — Computational Pharmacology

Develop pharmacokinetic and pharmacodynamic modeling components.

**Status:** Experimental components implemented; verification and validation ongoing.

### Phase 3 — Integrated Physiological Modeling

Expand computational models to represent interactions among physiological compartments and organ systems.

**Status:** Planned development.

### Phase 4 — Disease Progression Modeling

Introduce computational models capable of representing selected disease processes and their evolution over time.

**Status:** Planned development.

### Phase 5 — Combination Therapy Modeling

Develop research capabilities for investigating multiple medications within shared computational scenarios.

**Status:** Planned development.

### Phase 6 — Digital Human Interface

Develop an interactive scientific visualization environment connecting:

Human Body → Organ → Tissue → Cell → Molecular Target

The objective is to support navigation between anatomical structures, pharmacological mechanisms, and available computational models.

**Status:** Long-term development objective.

### Phase 7 — Research Platform Expansion

Explore additional capabilities such as:

- Broader disease coverage.
- Expanded drug knowledge.
- Additional validated scientific models.
- Advanced research workspaces.
- User account management.
- Subscription-based platform access.
- Production infrastructure.

**Status:** Future development.

---

## Intended Users

Marlo Scientific is being designed for:

- Pharmaceutical researchers.
- Clinical research scientists.
- Pharmacologists.
- Regulatory affairs professionals.
- Biomedical researchers.
- Drug development teams.
- Computational scientists.
- Academic research institutions.

The platform's intended purpose is scientific research, evidence exploration, and computational investigation.

---

## Research and Clinical Use Disclaimer

**Marlo Scientific is experimental research software under active development.**

The platform is not a medical device and has not been established as a clinically validated decision-support system.

Computational outputs, synthetic patient simulations, pharmacokinetic estimates, and pharmacodynamic predictions are intended for research, development, and educational purposes only.

They must not be used independently to diagnose medical conditions, determine treatment suitability, select medication doses, or make clinical decisions.

Scientific models may contain assumptions, incomplete evidence, or limitations affecting their applicability.

---

## Project Status

**Active Development — Pre-Release**

Marlo Scientific is not currently available as a production subscription service.

Development priorities include scientific verification, architecture refinement, model integration, evidence traceability, and expansion of supported research capabilities.

Public release and commercial deployment have not yet been scheduled.

---

## Project Vision

Marlo Scientific aims to become an integrated environment where researchers can move from clinical evidence discovery to pharmaceutical investigation and computational experimentation.

The long-term vision is to connect clinical research, regulatory intelligence, drug mechanisms, and physiological modeling within a single scientific platform.

**Discover evidence. Investigate mechanisms. Explore pharmacology.**

---

## Ownership and Licensing

Copyright © 2026 Marlo Scientific.

All rights reserved.

Unless a separate license is explicitly provided, no permission is granted to reproduce, distribute, modify, or commercially reuse the source code.

The availability of this repository does not imply that the project is open-source software.

Third-party components and scientific reference materials remain subject to their respective licenses and terms.