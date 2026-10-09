"""Deterministic historical PK teaching model; no fitted patient parameters."""

import hashlib
import json
import math
from pathlib import Path

import click

METHOD_VERSION = "single-dose-oral-pk-v1.0"
CATALOG_PATH = Path(__file__).parent / "data" / "lenalidomide_pk_v1.json"
CATALOG_SHA256 = "ed700b06cecb7be95f7bcb87f49a90f346d555241d6eaf9dc74d431f2db234ce"
SCALES = (0.5, 1.0, 2.0)
HORIZON_H = 48.0
LIMITATION = (
    "Historical fixed-parameter teaching model. The reference population was not a "
    "multiple myeloma population. The curve is simulated, not measured or fitted to "
    "this synthetic profile. Age, sex, weight, eGFR, indication and medications do not "
    "change the parameters. Clearance scaling is a mathematical what-if, not a renal "
    "function category. No dose recommendation, therapeutic range, efficacy, adverse "
    "event probability or pharmacodynamic response is calculated."
)


class PKValidationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def load_pk_catalog(path=CATALOG_PATH):
    try:
        content = Path(path).read_bytes()
        if hashlib.sha256(content).hexdigest() != CATALOG_SHA256:
            raise ValueError("Unverified parameter file")
        data = json.loads(content)
        return {**data, "sha256": CATALOG_SHA256}
    except (OSError, ValueError, TypeError) as exc:
        raise PKValidationError("PK parameter catalog is missing or changed; no curve was generated. Restore lenalidomide_pk_v1.json from Step 16.") from exc


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise PKValidationError(f"{label} requires a finite number.")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise PKValidationError(f"{label} requires a finite number.") from exc
    if not math.isfinite(number):
        raise PKValidationError(f"{label} requires a finite number.")
    return number


def validate_pk_inputs(drug, dose_mg, clearance_scale):
    if drug != "lenalidomide":
        raise PKValidationError("This release supports only the lenalidomide historical model.")
    dose = _finite_number(dose_mg, "Synthetic dose")
    if not 5 <= dose <= 40:
        raise PKValidationError("The teaching model accepts 5–40 mg, the source study's dose span. This is an implementation boundary, not a recommended dose range.")
    scale = _finite_number(clearance_scale, "Clearance comparison")
    if scale not in SCALES:
        raise PKValidationError("Choose a hypothetical clearance scale of 0.5, 1 or 2.")
    return dose, scale


def pk_availability(profile):
    if profile["selected_drug"] != "lenalidomide":
        return {"status": "unsupported_drug", "ready": False,
            "message": "Only lenalidomide has a model in this release. No curve is substituted for other drugs."}
    if profile["dose_value"] is None:
        return {"status": "missing_dose", "ready": False,
            "message": "Enter an invented dose in mg and preview the profile to open the teaching model. No dose is filled automatically."}
    if profile["dose_unit"] != "mg":
        return {"status": "unsupported_unit", "ready": False,
            "message": "The first model accepts mg only. mg/kg and mg/m² inputs are not converted."}
    try:
        validate_pk_inputs(profile["selected_drug"], profile["dose_value"], 1)
        catalog = load_pk_catalog()
    except PKValidationError as exc:
        return {"status": "unavailable", "ready": False, "message": str(exc)}
    return {"status": "ready", "ready": True, "message": "A fixed historical single-dose model is available for this invented mg input.",
        "method_version": METHOD_VERSION, "catalog_version": catalog["catalog_version"],
        "catalog_sha256": catalog["sha256"]}


def concentration(time_h, dose_mg, clearance_l_h, volume_l, ka_h, lag_h):
    """ng/mL; CL/F and V/F already contain F. Do not multiply by F again."""
    elapsed = max(0.0, time_h - lag_h)
    if elapsed == 0:
        return 0.0
    ke = clearance_l_h / volume_l
    delta = ka_h - ke
    # The continuous limit avoids cancellation if ka and ke coincide.
    if abs(delta) < 1e-10:
        factor = elapsed * math.exp(-ke * elapsed)
    elif delta > 0:
        factor = math.exp(-ke * elapsed) * (-math.expm1(-delta * elapsed)) / delta
    else:
        factor = math.exp(-ka_h * elapsed) * math.expm1(delta * elapsed) / delta
    return 1000.0 * dose_mg / volume_l * ka_h * factor


def _curve_metrics(dose, clearance, volume, ka, lag):
    ke = clearance / volume
    peak_time = lag + math.log(ka / ke) / (ka - ke)
    u = max(0.0, HORIZON_H - lag)
    auc_window = 1000 * dose / volume * ka / (ka - ke) * (
        -math.expm1(-ke * u) / ke + math.expm1(-ka * u) / ka)
    return {"clearance_l_h": clearance, "volume_l": volume, "absorption_rate_h": ka,
        "lag_h": lag, "elimination_rate_h": ke, "half_life_h": math.log(2) / ke,
        "tmax_h": peak_time,
        "cmax_ng_ml": concentration(peak_time, dose, clearance, volume, ka, lag),
        "auc_0_48_ng_h_ml": auc_window, "auc_0_infinity_ng_h_ml": 1000 * dose / clearance,
        "c24_ng_ml": concentration(24, dose, clearance, volume, ka, lag),
        "c48_ng_ml": concentration(48, dose, clearance, volume, ka, lag)}


def simulate_pk(drug, dose_mg, clearance_scale=1.0):
    dose, scale = validate_pk_inputs(drug, dose_mg, clearance_scale)
    catalog = load_pk_catalog()
    p = catalog["parameters"]
    clearance = p["apparent_clearance_ml_min"]["value"] * 60 / 1000
    volume, ka, lag = (p[k]["value"] for k in (
        "apparent_volume_l", "absorption_rate_h", "lag_h"))
    baseline = _curve_metrics(dose, clearance, volume, ka, lag)
    comparison = _curve_metrics(dose, clearance * scale, volume, ka, lag)
    times = sorted({*(round(i / 10, 1) for i in range(481)), lag,
        baseline["tmax_h"], comparison["tmax_h"]})
    points = [{"time_h": t,
        "reference_ng_ml": concentration(t, dose, clearance, volume, ka, lag),
        "comparison_ng_ml": concentration(t, dose, clearance * scale, volume, ka, lag)} for t in times]
    result = {"label": "Historical lenalidomide PK teaching model", "method_version": METHOD_VERSION,
        "inputs": {"drug": drug, "dose_mg": dose, "clearance_scale": scale,
            "route": "oral", "dose_count": 1, "horizon_h": HORIZON_H},
        "catalog_version": catalog["catalog_version"], "catalog_sha256": catalog["sha256"],
        "source": catalog["source"], "parameter_basis": p,
        "assumptions": catalog["assumptions"], "equations": catalog["equations"],
        "reference": baseline, "comparison": comparison, "points": points,
        "comparison_auc_ratio": comparison["auc_0_infinity_ng_h_ml"] / baseline["auc_0_infinity_ng_h_ml"],
        "sampling": "0.1-hour display grid plus the lag and analytic peak times; metrics use closed-form equations.",
        "uncertainty": "Deterministic central curve only. No confidence or prediction interval; study variability is not reproduced.",
        "limitation": LIMITATION}
    result["report_sha256"] = digest(result)
    return result


def register_pk_commands(app):
    @app.cli.command("pk-demo")
    @click.option("--drug", default="lenalidomide", show_default=True)
    @click.option("--dose", "dose_mg", type=float, required=True)
    @click.option("--clearance-scale", type=float, default=1.0, show_default=True)
    @click.option("--json", "json_output", is_flag=True)
    def pk_demo(drug, dose_mg, clearance_scale, json_output):
        """Run a historical single-dose teaching model; no patient or cohort fitting."""
        try:
            report = simulate_pk(drug, dose_mg, clearance_scale)
        except PKValidationError as exc:
            raise click.ClickException(str(exc)) from exc
        if json_output:
            click.echo(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
            return
        click.echo(report["label"])
        click.echo(f"Method: {METHOD_VERSION} | Catalog: {report['catalog_version']}")
        click.echo(f"Invented single oral dose: {dose_mg:g} mg | Hypothetical clearance scale: {clearance_scale:g}")
        for label, values in (("Fixed reference", report["reference"]), ("What-if comparison", report["comparison"])):
            click.echo(f"{label}: Cmax {values['cmax_ng_ml']:.2f} ng/mL; Tmax {values['tmax_h']:.3f} h; half-life {values['half_life_h']:.3f} h; AUC 0–infinity {values['auc_0_infinity_ng_h_ml']:.2f} ng·h/mL")
        click.echo(f"Comparison/reference AUC ratio: {report['comparison_auc_ratio']:.3f}")
        click.echo(LIMITATION)
