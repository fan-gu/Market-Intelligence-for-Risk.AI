"""Sensitivity-based what-if scenario calculation for MIRAI Scenario Lab."""

from __future__ import annotations

import hashlib
import json

import pandas as pd

from .core import TENOR_YEARS, VERSION
from .sensitivities import get_market_sensitivities, get_scenario_lab_specification


def _twist_loading(tenor: str) -> float:
    years = TENOR_YEARS.get(str(tenor), 5.0)
    minimum, maximum = min(TENOR_YEARS.values()), max(TENOR_YEARS.values())
    return -1.0 + 2.0 * (years - minimum) / (maximum - minimum)


def run_interactive_scenario(
    rate_currency: str = "EUR",
    curve_family: str = "All curve families",
    parallel_shift_bp: float = 0.0,
    curve_twist_bp: float = 0.0,
    fx_pair: str = "EUR/USD",
    fx_spot_move_pct: float = 0.0,
    volatility_shift_points: float = 0.0,
    horizon_days: int = 0,
    severity_multiplier: float = 1.0,
    allocation_weight: float = 1.0,
    scope_label: str = "Whole portfolio",
    as_of_date: str | None = None,
) -> dict:
    """Estimate P&L from Delta, Gamma, Vega, FX Delta, and Theta."""
    if severity_multiplier not in (1.0, 2.0):
        raise ValueError("Severity multiplier must be 1.0 (adverse) or 2.0 (extreme).")
    if allocation_weight < 0:
        raise ValueError("Allocation weight cannot be negative.")
    specification = get_scenario_lab_specification()
    if rate_currency not in specification["rate_currencies"] + ["All currencies"]:
        raise ValueError(f"Unknown rate currency: {rate_currency}")
    if curve_family not in specification["curve_families"] + ["All curve families"]:
        raise ValueError(f"Unknown curve family: {curve_family}")
    if fx_pair not in specification["fx_pairs"] + ["All FX pairs"]:
        raise ValueError(f"Unknown FX pair: {fx_pair}")

    frame = pd.DataFrame(get_market_sensitivities()["sensitivities"]).copy()
    frame["value"] = frame["value"].astype(float) * float(allocation_weight)
    detail_rows: list[dict] = []
    rate_filter = frame["risk_class"].eq("Rates")
    if rate_currency != "All currencies":
        rate_filter &= frame["currency"].eq(rate_currency)
    if curve_family != "All curve families":
        rate_filter &= frame["curve_type"].eq(curve_family)
    effective_parallel = float(parallel_shift_bp) * severity_multiplier
    effective_twist = float(curve_twist_bp) * severity_multiplier

    for measure, component in (("IR Delta (DV01)", "IR Delta"), ("IR Gamma", "IR Gamma")):
        for row in frame.loc[rate_filter & frame["measure"].eq(measure)].to_dict("records"):
            node_shock = effective_parallel + effective_twist * _twist_loading(row["tenor"])
            contribution = float(row["value"]) * node_shock if component == "IR Delta" else 0.5 * float(row["value"]) * node_shock**2
            detail_rows.append({"component": component, "currency": row["currency"], "curve_family": row["curve_type"], "curve": row["curve"], "tenor": row["tenor"], "applied_shock": f"{node_shock:+.1f} bp", "estimated_pnl": contribution})

    effective_volatility = float(volatility_shift_points) * severity_multiplier
    vega_filter = frame["measure"].eq("Vega")
    if rate_currency != "All currencies":
        vega_filter &= frame["currency"].eq(rate_currency)
    if curve_family != "All curve families":
        vega_filter &= frame["curve_type"].eq(curve_family)
    for row in frame.loc[vega_filter].to_dict("records"):
        detail_rows.append({"component": "IR Vega", "currency": row["currency"], "curve_family": row["curve_type"], "curve": row["curve"], "tenor": row.get("surface_node", row["tenor"]), "applied_shock": f"{effective_volatility:+.1f} vol points", "estimated_pnl": float(row["value"]) * effective_volatility})

    effective_fx = float(fx_spot_move_pct) * severity_multiplier
    fx_filter = frame["measure"].eq("FX Delta")
    if fx_pair != "All FX pairs":
        fx_filter &= frame["curve"].eq(fx_pair)
    for row in frame.loc[fx_filter].to_dict("records"):
        detail_rows.append({"component": "FX Delta", "currency": row["currency"], "curve_family": row["curve_type"], "curve": row["curve"], "tenor": "Spot", "applied_shock": f"{effective_fx:+.1f}%", "estimated_pnl": float(row["value"]) * effective_fx})

    theta_filter = frame["measure"].eq("Theta")
    if rate_currency != "All currencies":
        theta_filter &= frame["currency"].eq(rate_currency)
    for row in frame.loc[theta_filter].to_dict("records"):
        detail_rows.append({"component": "Theta", "currency": row["currency"], "curve_family": row["curve_type"], "curve": row["curve"], "tenor": "Time", "applied_shock": f"{int(horizon_days)} days", "estimated_pnl": float(row["value"]) * int(horizon_days)})

    detail = pd.DataFrame(detail_rows)
    component_order = ["IR Delta", "IR Gamma", "IR Vega", "FX Delta", "Theta"]
    values = detail.groupby("component")["estimated_pnl"].sum().to_dict() if not detail.empty else {}
    components = [{"component": name, "estimated_pnl": float(values.get(name, 0.0))} for name in component_order]
    estimated_pnl = float(sum(row["estimated_pnl"] for row in components))
    if abs(estimated_pnl) < 1e-9:
        estimated_pnl = 0.0
    if detail.empty:
        top_contributors = currency_contributions = curve_contributions = []
    else:
        top_contributors = detail.assign(abs_pnl=detail["estimated_pnl"].abs()).sort_values("abs_pnl", ascending=False).drop(columns="abs_pnl").head(15).to_dict("records")
        currency_contributions = detail.groupby(["currency", "component"], as_index=False)["estimated_pnl"].sum().to_dict("records")
        curve_contributions = detail.groupby(["currency", "curve", "component"], as_index=False)["estimated_pnl"].sum().assign(abs_pnl=lambda data: data["estimated_pnl"].abs()).sort_values("abs_pnl", ascending=False).drop(columns="abs_pnl").head(20).to_dict("records")

    parameters = {"rate_currency": rate_currency, "curve_family": curve_family, "parallel_shift_bp": float(parallel_shift_bp), "curve_twist_bp": float(curve_twist_bp), "fx_pair": fx_pair, "fx_spot_move_pct": float(fx_spot_move_pct), "volatility_shift_points": float(volatility_shift_points), "horizon_days": int(horizon_days), "severity_multiplier": float(severity_multiplier)}
    scenario_hash = hashlib.sha256(json.dumps({"parameters": parameters, "scope": scope_label, "as_of": as_of_date}, sort_keys=True).encode()).hexdigest()[:10].upper()
    return {
        "scenario_id": f"SCN-{VERSION}-{scenario_hash}", "version": VERSION,
        "as_of_date": as_of_date, "scope": scope_label, "allocation_weight": float(allocation_weight),
        "calculation_mode": "Sensitivity approximation", "parameters": parameters,
        "effective_shocks": {"parallel_shift_bp": effective_parallel, "curve_twist_bp": effective_twist, "fx_spot_move_pct": effective_fx, "volatility_shift_points": effective_volatility, "horizon_days": int(horizon_days)},
        "no_shock_reference": {"scenario_impact": 0.0, "definition": "Zero is the scenario impact before shocks; it is not current Actual P&L."},
        "scenario": {"estimated_pnl": estimated_pnl, "loss_amount": max(-estimated_pnl, 0.0)},
        "component_contributions": components, "currency_contributions": currency_contributions,
        "curve_contributions": curve_contributions, "top_contributors": top_contributors,
        "methodology": specification["methodology"], "governance_note": specification["governance_note"],
        "assumptions": [
            "Delta and Vega contributions are linear in their respective shocks.",
            "IR Gamma uses 0.5 x Gamma x rate-shock squared at each curve-tenor node.",
            "Curve twist loading runs from -1 at the shortest tenor to +1 at the longest tenor.",
            "Cross-gamma, smile dynamics, basis interactions and trade-level full revaluation are not modelled.",
        ],
    }
