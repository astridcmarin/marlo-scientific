"""Add the v2 storage foundation to an existing Flask application."""

import os
from pathlib import Path

import click
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db, migrate
from .models import NormalizedTrial, TrialSnapshot
from .normalization import register_normalization_commands
from .cohorts import register_cohort_commands
from .summaries import register_summary_commands
from .intervention_names import register_intervention_name_commands
from .drug_aliases import register_alias_commands
from .mechanisms import register_mechanism_commands
from .protocols import register_protocol_commands
from .stopping import register_stopping_commands
from .safety import register_safety_commands
from .interactions import register_interaction_commands
from .patient_scenarios import register_scenario_commands
from .trial_criteria import register_criteria_commands
from .pharmacokinetics import register_pk_commands
from .site_feasibility import register_feasibility_commands
from .regulatory import register_regulatory_commands
from .workspaces import register_workspace_commands
from .watchlists import register_watchlist_commands
from .saved_scenarios import register_saved_scenario_commands
from .validation import register_validation_commands
from .patient_state import register_patient_state_commands
from .patient_state_revisions import register_patient_state_revision_commands
from .patient_state_comparison import register_patient_state_comparison_commands
from .patient_model_review import register_patient_model_review_commands
from .pk_parameter_reference import register_pk_parameter_reference_commands
from .transit_kernel import register_transit_kernel_commands
from .transit_regimen import register_transit_regimen_commands
from .published_transit_reference import register_published_transit_reference_commands
from .pk_model_inputs import register_pk_model_input_commands
from .covariate_estimation import register_covariate_estimation_commands
from .estimated_pk import register_estimated_pk_commands
from .population_pk import register_population_pk_commands
from .renal_group_check import register_renal_group_check_commands
from .kim_model import register_kim_model_commands
from .kim_renal_group_check import register_kim_renal_group_check_commands
from .kim_pk_runs import register_kim_pk_run_commands
from .bortezomib_platelets import register_bortezomib_platelet_commands
from .bortezomib_pk_ogawa_check import register_bortezomib_pk_ogawa_commands
from .bortezomib_pk_kuan_check import register_bortezomib_pk_kuan_commands
from .bortezomib_pbpk_iwasaki_check import register_bortezomib_pbpk_iwasaki_check_commands
from .bortezomib_pk_can1004_check import register_bortezomib_pk_can1004_commands
from .bortezomib_pk_falling_clearance import register_bortezomib_pk_falling_clearance_commands
from .label_exposure import register_label_exposure_commands
from .label_exposure_li_check import register_label_exposure_li_commands
from .label_exposure_iv import register_label_exposure_iv_commands
from .label_exposure_single_dose import register_label_exposure_single_dose_commands
from .label_exposure_dexamethasone_check import register_label_exposure_dexamethasone_commands
from .eligibility_corpus import register_eligibility_corpus_commands
from .eligibility_annotations import register_eligibility_annotation_commands
from .eligibility_annotations_v2 import register_eligibility_annotation_v2_commands
from .eligibility_validation import register_eligibility_validation_commands
from .eligibility_validation_posthoc import register_eligibility_validation_posthoc_commands
from .eligibility_validation_v2 import register_eligibility_validation_v2_commands
from .lenalidomide_renal_pathways import register_renal_pathway_commands
from .lenalidomide_esrd_dialysis import register_esrd_dialysis_commands
from .patient_model_binding import register_patient_model_binding_commands
from .treatment_requests import register_treatment_request_commands
from .model_coverage import register_model_coverage_commands
from .educational_pk import register_educational_pk_commands
from .educational_pk_runs import register_educational_pk_run_commands
from .educational_pk_comparison import register_educational_pk_comparison_commands
from .educational_pk_audit import register_educational_pk_audit_commands
from .educational_pk_metrics import register_educational_pk_metrics_commands
from .educational_pk_sensitivity import register_educational_pk_sensitivity_commands
from .patient_lab_checkpoint import register_patient_lab_checkpoint_commands
from .pk_validation_gap import register_pk_validation_gap_commands
from .pk_transcription_review import register_pk_transcription_review_commands
from .patient_lab_intended_use import register_patient_lab_intended_use_commands
from .pk_validation_artifacts import register_pk_validation_artifact_commands
from .patient_lab_milestone import register_patient_lab_milestone_commands
from .educational_pk_comparison_summary import register_educational_pk_comparison_summary_commands


def init_storage(app):
    """Configure extensions and CLI only. Do not create tables on startup."""
    if "sqlalchemy" in app.extensions:
        raise RuntimeError(
            "This app already has SQLAlchemy. Integrate with its existing db "
            "object instead of initializing a second extension."
        )

    project_root = Path(__file__).resolve().parent.parent
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        configured_url = os.environ.get("DATABASE_URL", "").strip()
        if configured_url:
            app.config["SQLALCHEMY_DATABASE_URI"] = configured_url
        else:
            database_folder = project_root / "instance"
            database_folder.mkdir(parents=True, exist_ok=True)
            database_path = (database_folder / "intelligence.db").as_posix()
            app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)
    migrate.init_app(app, db, directory=str(project_root / "intelligence_migrations"))
    register_normalization_commands(app)
    register_cohort_commands(app)
    register_summary_commands(app)
    register_intervention_name_commands(app)
    register_alias_commands(app)
    register_mechanism_commands(app)
    register_protocol_commands(app)
    register_stopping_commands(app)
    register_safety_commands(app)
    register_interaction_commands(app)
    register_scenario_commands(app)
    register_criteria_commands(app)
    register_pk_commands(app)
    register_feasibility_commands(app)
    register_regulatory_commands(app)
    register_workspace_commands(app)
    register_watchlist_commands(app)
    register_saved_scenario_commands(app)
    register_validation_commands(app)
    register_patient_state_commands(app)
    register_patient_state_revision_commands(app)
    register_patient_state_comparison_commands(app)
    register_patient_model_review_commands(app)
    register_pk_parameter_reference_commands(app)
    register_transit_kernel_commands(app)
    register_transit_regimen_commands(app)
    register_published_transit_reference_commands(app)
    register_pk_model_input_commands(app)
    register_covariate_estimation_commands(app)
    register_estimated_pk_commands(app)
    register_population_pk_commands(app)
    register_renal_group_check_commands(app)
    register_kim_model_commands(app)
    register_kim_renal_group_check_commands(app)
    register_kim_pk_run_commands(app)
    register_bortezomib_platelet_commands(app)
    register_bortezomib_pk_ogawa_commands(app)
    register_bortezomib_pk_kuan_commands(app)
    register_bortezomib_pbpk_iwasaki_check_commands(app)
    register_bortezomib_pk_can1004_commands(app)
    register_bortezomib_pk_falling_clearance_commands(app)
    register_label_exposure_commands(app)
    register_label_exposure_li_commands(app)
    register_label_exposure_iv_commands(app)
    register_label_exposure_single_dose_commands(app)
    register_label_exposure_dexamethasone_commands(app)
    register_eligibility_corpus_commands(app)
    register_eligibility_annotation_commands(app)
    register_eligibility_annotation_v2_commands(app)
    register_eligibility_validation_commands(app)
    register_eligibility_validation_posthoc_commands(app)
    register_eligibility_validation_v2_commands(app)
    register_esrd_dialysis_commands(app)
    register_patient_model_binding_commands(app)
    register_treatment_request_commands(app)
    register_model_coverage_commands(app)
    register_educational_pk_commands(app)
    register_educational_pk_run_commands(app)
    register_educational_pk_comparison_commands(app)
    register_educational_pk_audit_commands(app)
    register_educational_pk_metrics_commands(app)
    register_educational_pk_sensitivity_commands(app)
    register_patient_lab_checkpoint_commands(app)
    register_pk_validation_gap_commands(app)
    register_pk_transcription_review_commands(app)
    register_patient_lab_intended_use_commands(app)
    register_pk_validation_artifact_commands(app)
    register_patient_lab_milestone_commands(app)
    register_educational_pk_comparison_summary_commands(app)

    @app.cli.command("db-check")
    def db_check():
        """Check connectivity and the migrated evidence table without writing."""
        try:
            if not inspect(db.engine).has_table(TrialSnapshot.__tablename__):
                raise click.ClickException(
                    "Evidence table is missing. Run the initial migration and upgrade."
                )
            count = db.session.scalar(select(func.count()).select_from(TrialSnapshot))
            if not inspect(db.engine).has_table(NormalizedTrial.__tablename__):
                raise click.ClickException(
                    "Normalized trial table is missing. Generate the Step 3 migration "
                    "and run db upgrade."
                )
            trial_count = db.session.scalar(
                select(func.count()).select_from(NormalizedTrial)
            )
        except SQLAlchemyError as exc:
            raise click.ClickException(
                "Database check failed. Verify configuration and run db upgrade."
            ) from exc
        click.echo(f"Database ready. Stored trial snapshots: {count}")
        click.echo(f"Normalized unique trials: {trial_count}")
