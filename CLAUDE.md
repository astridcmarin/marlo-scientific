# Marlo Scientific — notes for AI coding sessions

Research and educational platform: clinical-trial intelligence, drug/regulatory knowledge, and a synthetic Patient Lab with published-model PK. Nothing here is validated for clinical prediction, prescribing or treatment selection; keep that distinction in code, outputs and wording.

## Start here

- `docs/README.md` — index of all documentation.
- `docs/PRODUCT_AND_SCIENCE_ROADMAP.md` — product direction and phases.
- `docs/PATIENT_LAB_2_0.md` — current Patient Lab work: scope, non-goals, architecture, step status, and recorded scientific decisions (Hughes 2019 lenalidomide model, Cockcroft–Gault weight basis).
- `docs/REPOSITORY_CHECKPOINT.md` — latest verification, findings and remaining gates; step-number history is in `docs/history/REPOSITORY_CHECKPOINT_2026-10-13.md` (step numbers are not unique; use module/schema versions).

## Conventions

- Reference data in `intelligence_store/data/*.json` is SHA-256 pinned by its loader. Changing a file means a new versioned file and a new pin, never an edit in place.
- Every value carries provenance: origin, method/formula and version, source location, assumptions. Unknown stays unknown; no silent defaults or unit conversions.
- Synthetic inputs only. Outputs keep `ready_for_patient_simulation` / validation flags false unless a documented review changes them.
- Tests use `unittest`: `python -m unittest discover -s tests`. Dependencies are in `requirements.txt`.
- Run the app and CLI tools from the repo root with `PYTHONPATH=.` and `flask --app app/app.py …`; schema changes need a new Alembic migration whose `down_revision` is the current head (`tests/test_migrations.py` checks the chain).
