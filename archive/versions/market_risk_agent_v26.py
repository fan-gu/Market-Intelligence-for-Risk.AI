"""M.R. AI Agent V26: governed Delta aggregation and surface-based IR Vega."""

from __future__ import annotations

import pandas as pd
from google.genai import types

from archive.versions import market_risk_agent_v25 as v25


VERSION = "V26"
v25.v9.VERSION = VERSION

# Preserve the public version chain used by the dashboard.
v24 = v25.v24
v23 = v25.v23
v22 = v25.v22
v21 = v25.v21
v20 = v25.v20
v19 = v25.v19
v18 = v25.v18
v17 = v25.v17
v16 = v25.v16
v15 = v25.v15
v14 = v25.v14
v13 = v25.v13
v12 = v25.v12
v11 = v25.v11
v9 = v25.v9
v8 = v25.v8
SVAR_LIMIT_MULTIPLIER = v18.SVAR_LIMIT_MULTIPLIER

build_pla_demo_history = v25.build_pla_demo_history
evaluate_pla_test = v25.evaluate_pla_test
evaluate_pnl_explain_alerts = v25.evaluate_pnl_explain_alerts
build_supplied_stress_frame = v25.build_supplied_stress_frame
get_stress_evolution = v25.get_stress_evolution
get_material_stress_scenarios = v25.get_material_stress_scenarios
get_stress_scenario_catalog = v25.get_stress_scenario_catalog
get_stress_limit_monitor = v25.get_stress_limit_monitor
get_var_change_summary = v25.get_var_change_summary
get_var_change_attribution = v25.get_var_change_attribution
generate_daily_risk_brief = v25.generate_daily_risk_brief


DELTA_LIMITS = {
    "EUR": {"net": 160_000.0, "gross": 180_000.0},
    "USD": {"net": 130_000.0, "gross": 145_000.0},
    "JPY": {"net": 55_000.0, "gross": 65_000.0},
    "GBP": {"net": 70_000.0, "gross": 80_000.0},
    "HKD": {"net": 45_000.0, "gross": 55_000.0},
    "CNY": {"net": 50_000.0, "gross": 60_000.0},
    "TOTAL": {"net": 200_000.0, "gross": 440_000.0},
}

VEGA_SURFACE_WEIGHTS = {
    ("1Y", "2Y"): 0.20,
    ("1Y", "10Y"): 0.25,
    ("5Y", "2Y"): 0.25,
    ("5Y", "10Y"): 0.30,
}


def get_market_sensitivities():
    """Return Delta/Gamma tenor vectors and a compact expiry-by-tenor Vega surface."""
    source = v25.get_market_sensitivities()
    frame = pd.DataFrame(source["sensitivities"])
    vega = frame.loc[frame["measure"] == "Vega"].copy()
    non_vega = frame.loc[frame["measure"] != "Vega"].copy()

    group_columns = [
        "risk_class", "measure", "currency", "curve_type", "curve", "unit"
    ]
    vega_totals = vega.groupby(group_columns, as_index=False)["value"].sum()
    surface_rows = []
    for row in vega_totals.to_dict("records"):
        for (option_expiry, swap_tenor), weight in VEGA_SURFACE_WEIGHTS.items():
            surface_rows.append({
                **row,
                "tenor": swap_tenor,
                "option_expiry": option_expiry,
                "underlying_tenor": swap_tenor,
                "surface_node": f"{option_expiry} x {swap_tenor}",
                "value": float(row["value"]) * weight,
                "definition": (
                    f"IR Vega for {row['curve']} at {option_expiry} option expiry "
                    f"and {swap_tenor} underlying swap tenor."
                ),
            })

    for column in ("option_expiry", "underlying_tenor", "surface_node"):
        non_vega[column] = "N/A"

    return {
        **source,
        "sensitivities": non_vega.to_dict("records") + surface_rows,
        "vega_option_expiries": ["1Y", "5Y"],
        "vega_underlying_tenors": ["2Y", "10Y"],
        "usage_note": (
            "Deterministic V26 prototype feed. IR Delta and Gamma retain tenor vectors; "
            "IR Vega is represented as a 2 x 2 option-expiry by underlying-swap-tenor surface."
        ),
    }


def get_delta_limit_summary(currencies=None):
    """Aggregate signed Net Delta and absolute Gross Delta by currency and total."""
    source = get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    frame = pd.DataFrame(source["sensitivities"])
    delta = frame.loc[
        (frame["measure"] == "IR Delta (DV01)")
        & frame["currency"].isin(selected)
    ].copy()

    rows = []
    for currency in selected:
        values = delta.loc[delta["currency"] == currency, "value"]
        net_delta = float(values.sum())
        gross_delta = float(values.abs().sum())
        limits = DELTA_LIMITS[currency]
        rows.append({
            "currency": currency,
            "net_delta": net_delta,
            "net_limit": limits["net"],
            "net_pct": abs(net_delta) / limits["net"] * 100.0,
            "gross_delta": gross_delta,
            "gross_limit": limits["gross"],
            "gross_pct": gross_delta / limits["gross"] * 100.0,
        })

    total_net = sum(row["net_delta"] for row in rows)
    total_gross = sum(row["gross_delta"] for row in rows)
    total_limits = DELTA_LIMITS["TOTAL"]
    rows.append({
        "currency": "TOTAL",
        "net_delta": total_net,
        "net_limit": total_limits["net"],
        "net_pct": abs(total_net) / total_limits["net"] * 100.0,
        "gross_delta": total_gross,
        "gross_limit": total_limits["gross"],
        "gross_pct": total_gross / total_limits["gross"] * 100.0,
    })
    return {
        "rows": rows,
        "usage_note": (
            "Net Delta is the signed sum of every curve and tenor. Gross Delta is the sum "
            "of their absolute values. TOTAL sums the displayed currency results; TOTAL limits "
            "are separate portfolio-level prototype limits and are not the sum of currency limits."
        ),
    }


def get_ir_vega_surface(currencies=None):
    """Return the compact IR Vega surface nodes for selected currencies."""
    source = get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    frame = pd.DataFrame(source["sensitivities"])
    rows = frame.loc[
        (frame["measure"] == "Vega") & frame["currency"].isin(selected)
    ].copy()
    return {
        "option_expiries": source["vega_option_expiries"],
        "underlying_tenors": source["vega_underlying_tenors"],
        "surface": rows.to_dict("records"),
        "usage_note": (
            "The vertical axis is option expiry and the horizontal axis is underlying swap tenor. "
            "This 2 x 2 prototype preserves each curve's total Vega; a production feed should supply "
            "native surface-node sensitivities."
        ),
    }


def evaluate_sensitivity_limits():
    """Evaluate Delta net/gross plus the remaining governed non-Gamma sensitivities."""
    frame = pd.DataFrame(get_market_sensitivities()["sensitivities"])
    delta_total = get_delta_limit_summary()["rows"][-1]
    rows = []
    for measure, exposure, limit, unit, owner, basis in [
        ("Net IR Delta", abs(delta_total["net_delta"]), delta_total["net_limit"], "EUR / bp", "Rates Risk", "Absolute signed net"),
        ("Gross IR Delta", delta_total["gross_delta"], delta_total["gross_limit"], "EUR / bp", "Rates Risk", "Gross absolute"),
        ("Vega", float(frame.loc[frame["measure"] == "Vega", "value"].abs().sum()), 150_000.0, "EUR / vol point", "Volatility Risk", "Gross surface Vega"),
        ("FX Delta", float(frame.loc[frame["measure"] == "FX Delta", "value"].abs().sum()), 1_100_000.0, "EUR / 1% spot", "FX Risk", "Gross absolute"),
        ("Theta", float(frame.loc[frame["measure"] == "Theta", "value"].abs().sum()), 40_000.0, "EUR / day", "Market Risk", "Gross absolute"),
    ]:
        consumption = 0.0 if limit == 0 else exposure / limit * 100.0
        rows.append({
            "measure": measure,
            "gross_exposure": exposure,
            "limit": limit,
            "consumption_pct": consumption,
            "status": v24._limit_status(consumption),
            "unit": unit,
            "owner": owner,
            "consumption_basis": basis,
        })
    return {
        "limits": rows,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "usage_note": (
            "IR Gamma is informational and has no limit. Delta has separate net and gross controls; "
            "below 80% is OK, 80% to below 100% is WARNING, and 100% or above is BREACH."
        ),
    }


def evaluate_all_limits():
    """Return the V25 limit inventory with the V26 sensitivity controls."""
    base = v24.evaluate_all_limits()
    rows = [row for row in base["limits"] if row["family"] != "Sensitivity"]
    for item in evaluate_sensitivity_limits()["limits"]:
        rows.append({
            "family": "Sensitivity",
            "metric": item["measure"],
            "exposure": item["gross_exposure"],
            "limit": item["limit"],
            "unit": item["unit"],
            "consumption_pct": item["consumption_pct"],
            "warning_threshold_pct": 80.0,
            "breach_threshold_pct": 100.0,
            "status": item["status"],
            "owner": item["owner"],
            "consumption_basis": item["consumption_basis"],
            "escalation_status": (
                "Immediate escalation required" if item["status"] == "BREACH"
                else "Owner review required" if item["status"] == "WARNING"
                else "No escalation"
            ),
        })
    return {
        **base,
        "limits": rows,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "usage_note": (
            "V26 separates governed Net and Gross Delta. SVaR is governed at 1.5x the "
            "approved Historical VaR limit; IR Gamma remains informational without a limit."
        ),
    }


def detect_material_risk_movements(as_of_date=None):
    """Refresh material limit findings with V26 sensitivity controls."""
    result = v24.detect_material_risk_movements(as_of_date)
    old_names = {"Gross IR Delta (DV01)", "IR Gamma", "Gross FX Delta", "Gross Vega"}
    findings = [
        item for item in result["findings"]
        if not (item["source"] == "Limits" and item["finding"] in old_names)
    ]
    for row in evaluate_sensitivity_limits()["limits"]:
        if row["status"] in {"WARNING", "BREACH"}:
            findings.append({
                "source": "Limits",
                "finding": row["measure"],
                "severity": "CRITICAL" if row["status"] == "BREACH" else "HIGH",
                "observed": row["consumption_pct"],
                "threshold": 100.0 if row["status"] == "BREACH" else 80.0,
                "unit": "%",
                "action": "Immediate escalation required" if row["status"] == "BREACH" else "Owner review required",
            })
    rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    findings.sort(key=lambda row: (rank[row["severity"]], row["source"], row["finding"]))
    return {
        **result,
        "finding_count": len(findings),
        "summary": {
            "critical": sum(row["severity"] == "CRITICAL" for row in findings),
            "high": sum(row["severity"] == "HIGH" for row in findings),
            "medium": sum(row["severity"] == "MEDIUM" for row in findings),
        },
        "findings": findings,
        "usage_note": "V26 materiality detection uses the same Delta and surface-Vega controls as the dashboard.",
    }


# Keep the inherited daily-brief function aligned with V26 materiality controls.
v25.detect_material_risk_movements = detect_material_risk_movements

v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Sensitivity feed with Delta/Gamma vectors and a compact IR Vega surface."
v8.TOOL_FUNCTIONS["get_delta_limit_summary"] = get_delta_limit_summary
v8.TOOL_DESCRIPTIONS["get_delta_limit_summary"] = "Net and Gross IR Delta with limits and consumption by currency."
v8.TOOL_FUNCTIONS["get_ir_vega_surface"] = get_ir_vega_surface
v8.TOOL_DESCRIPTIONS["get_ir_vega_surface"] = "IR Vega surface by option expiry and underlying swap tenor."
v8.TOOL_FUNCTIONS["evaluate_sensitivity_limits"] = evaluate_sensitivity_limits
v8.TOOL_DESCRIPTIONS["evaluate_sensitivity_limits"] = "Governed sensitivity limits; Gamma is informational only."
v8.TOOL_FUNCTIONS["evaluate_all_limits"] = evaluate_all_limits
v8.TOOL_DESCRIPTIONS["evaluate_all_limits"] = "V26 limit inventory with separate Net and Gross Delta controls."
v8.TOOL_FUNCTIONS["detect_material_risk_movements"] = detect_material_risk_movements
v8.TOOL_DESCRIPTIONS["detect_material_risk_movements"] = "Material risk findings refreshed with V26 sensitivity controls."

v9.SYSTEM_INSTRUCTION += """

V26 sensitivity conventions:
- Net Delta is the signed sum across curve and tenor nodes; Gross Delta is the sum of absolute node values.
- Use get_delta_limit_summary for currency and portfolio Delta limits and consumption.
- IR Gamma is informational and has no limit in this prototype.
- IR Vega is an option-expiry by underlying-swap-tenor surface; use get_ir_vega_surface.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v25.ask_risk_agent
