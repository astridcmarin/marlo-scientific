"""Run-bound clinical-validation gap register; records evidence, never approval."""
import copy
import json
from pathlib import Path
import click
from sqlalchemy.exc import SQLAlchemyError
from .educational_pk_runs import read_pk_run
from .educational_pk_audit import audit_pk_run
from .educational_pk_metrics import summarize_pk_run
from .published_transit_reference import load_structure_contract,CONTRACT_SHA256
from .pk_parameter_reference import load_parameter_extract,EXTRACT_SHA256
from .model_coverage import load_coverage_contract,CONTRACT_SHA256 as COVERAGE_SHA256
from .educational_pk import CONTRACT_SHA256 as EXECUTION_SHA256
from .patient_state import digest

METHOD='educational-pk-validation-gap-v1.0'
LIMITATION='Planning and evidence-gap classification for one educational archive. It is not clinical validation, model qualification, regulatory acceptance, an applicability decision or a patient prediction.'


def validation_gap_report(run_id):
    row=read_pk_run(run_id)
    if row is None:raise ValueError('Saved educational PK run does not exist.')
    archived=row.payload['report'];review=archived['preflight_review']
    structure=load_structure_contract();parameters=load_parameter_extract();coverage=load_coverage_contract()
    audit=audit_pk_run(run_id);metrics=summarize_pk_run(run_id)
    binding=review['binding']
    contract_matches={
        'structure_contract_matches_archive':binding.get('structure_contract_sha256')==CONTRACT_SHA256,
        'parameter_extract_matches_archive':review.get('standalone_input_preview',{}).get('parameter_extract_sha256')==EXTRACT_SHA256,
        'coverage_contract_matches_archive':binding.get('coverage_contract_sha256')==COVERAGE_SHA256,
        'execution_contract_matches_archive':archived.get('execution_contract_sha256')==EXECUTION_SHA256}
    source={'doi':coverage['source']['doi'],'url':coverage['source']['url'],
        'structure_contract_version':structure['contract_version'],'structure_contract_sha256':CONTRACT_SHA256,
        'parameter_extract_version':parameters['extract_version'],'parameter_extract_sha256':EXTRACT_SHA256,
        'coverage_contract_version':coverage['contract_version'],'coverage_contract_sha256':COVERAGE_SHA256}
    gates=[]
    def gate(code,label,status,evidence,required):
        gates.append({'code':code,'label':label,'status':status,'current_evidence':evidence,
            'evidence_required_to_pass':required})
    source_ok=all(contract_matches.values())
    gate('source_traceability','Source identification and archived contract binding','passed' if source_ok else 'failed',
        ['DOI and reviewed source locations are recorded.','Archived run hashes are compared with the current reviewed structure, parameter and coverage contracts.',contract_matches],
        ['All source contracts must load with their expected hashes and match the archived execution binding.'])
    gate('equation_transcription','Independent source-equation transcription review','incomplete',
        ['A reviewed project extraction records final structure, units, equations and source locations.'],
        ['A second qualified reviewer independently transcribes the final source equations and resolves discrepancies.','Retain reviewer, date, source location and approved comparison record.'])
    math_pass=audit['status']=='mathematical_checks_passed'
    gate('numerical_verification','Numerical implementation verification','passed' if math_pass else 'failed',
        [f"Archived run audit status: {audit['status']}.",'Closed-form reference checks concentration, amounts, mass balance, event boundaries and AUC for the supported structure.'],
        ['All supported mathematical checks pass for predefined normal, boundary and regression cases.'])
    gate('source_model_reproduction','Published population-model reproduction','blocked',
        ['Published typical-value equations are represented.','Project contracts state that source data, dosing records, NONMEM run and subject-level outputs were unavailable.'],
        ['Authorized source analysis dataset and dosing records.','Original model code/control stream and software/version details.','Reproduce parameter estimates, objective function and diagnostic outputs against predefined tolerances.'])
    gate('internal_predictive_performance','Internal predictive performance','blocked',
        ['No observation-level source dataset is connected to this implementation.'],
        ['Prespecified goodness-of-fit diagnostics, residual analysis, visual predictive checks and resampling diagnostics using appropriate source data.','Document acceptance criteria before evaluation.'])
    gate('external_validation','External predictive validation','blocked',
        ['No independent observed concentration dataset is connected.'],
        ['A fit-for-purpose independent dataset with dosing, sampling, covariates and assay context.','Prespecified prediction-error and calibration metrics, subgroup checks and acceptance criteria.'])
    gate('uncertainty_and_variability','Population variability and uncertainty','blocked',
        ['Execution fixes random effects to zero.','Clearance sensitivity is a declared mathematical scenario and is not a probability distribution.'],
        ['Verified interindividual/residual variability models and covariance information.','Parameter uncertainty method, simulation design and calibration checks.','Distinguish uncertainty, variability and sensitivity in outputs.'])
    gate('individual_applicability','Individual applicability and covariate provenance','blocked',
        ['Patient state and explicit model covariates are preserved separately.','Range matches are coverage context only; input declarations are not independently authenticated.'],
        ['Validated covariate derivation and unit methods.','Eligibility/applicability rules supported by evidence, including joint covariate and regimen coverage.','Prospective governance for missing, conflicting and out-of-domain inputs.'])
    gate('clinical_endpoint_link','Exposure-to-response or safety validation','blocked',
        ['No PD, efficacy, toxicity or outcome model is implemented.'],
        ['A prespecified, evidence-supported PK/PD or exposure-response model.','Independent clinical endpoint validation and uncertainty characterization for each intended use.'])
    gate('intended_use_and_governance','Intended use, risk and change control','incomplete',
        ['Current outputs are explicitly synthetic and educational; clinical prediction and patient readiness remain false.'],
        ['Define users, decisions, population, setting, failure modes and prohibited uses.','Versioned change control, review roles, validation maintenance and incident handling.'])
    counts={status:sum(g['status']==status for g in gates) for status in ('passed','incomplete','blocked','failed')}
    report={'schema_version':'educational-pk-validation-gap-v1','method_version':METHOD,
        'status':'clinical_validation_not_established','run_id':row.id,'revision_id':row.revision_id,
        'source_payload_sha256':row.payload_sha256,'source_report_sha256':row.report_sha256,
        'source_binding':copy.deepcopy(binding),'source_reference':source,'contract_matches':contract_matches,
        'mathematical_audit':{'status':audit['status'],'method_version':audit['method_version'],'report_sha256':audit['report_sha256']},
        'sampled_metrics':{'status':metrics['status'],'method_version':metrics['method_version'],'report_sha256':metrics['report_sha256']},
        'gates':gates,'counts':counts,
        'minimum_sequence':['Resolve independent transcription review.','Obtain authorized source artifacts and reproduce the published population model.',
            'Complete internal diagnostics against prespecified criteria.','Validate predictions on independent observed data.',
            'Implement and evaluate variability and uncertainty.','Define intended use and applicability rules before any individual-level interpretation.',
            'Validate a separate exposure-response layer before efficacy or toxicity claims.'],
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'validation_approval':None,'database_writes_performed':False,'ode_solver_rerun':False,'network_refresh_performed':False,
        'limitation':LIMITATION}
    report['report_sha256']=digest(report)
    return report


def register_pk_validation_gap_commands(app):
    @app.cli.command('patient-pk-validation-gap')
    @click.option('--id','run_id',type=click.IntRange(min=1),required=True)
    @click.option('--json','json_output',is_flag=True)
    @click.option('--output',type=click.Path(dir_okay=False,path_type=Path))
    def command(run_id,json_output,output):
        """Show required evidence before clinical interpretation of a saved run."""
        try:
            report=validation_gap_report(run_id)
            if output:
                with output.open('x',encoding='utf-8') as handle:
                    json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
                click.echo(f'Exported validation-gap report: {output}')
            elif json_output:click.echo(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
            else:
                click.echo(f"Run #{run_id} | {report['status']} | Clinical prediction validated: false")
                for gate in report['gates']:click.echo(f"[{gate['status'].upper()}] {gate['label']}")
                click.echo(LIMITATION)
        except (ValueError,OSError,UnicodeError,SQLAlchemyError) as exc:raise click.ClickException(str(exc)) from exc
