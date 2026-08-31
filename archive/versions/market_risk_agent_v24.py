"""M.R. AI Agent V24: material-movement detection and stress-limit monitoring."""

from __future__ import annotations

import pandas as pd
from google.genai import types

from archive.versions import market_risk_agent_v23 as v23


VERSION = "V24"
v23.v9.VERSION = VERSION
v22 = v23.v22
v21 = v23.v21
v20 = v23.v20
v19 = v23.v19
v18 = v23.v18
v17 = v23.v17
v16 = v23.v16
v15 = v23.v15
v14 = v23.v14
v13 = v23.v13
v12 = v23.v12
v11 = v23.v11
v9 = v23.v9
v8 = v23.v8
DRIVER_COLUMNS = v23.DRIVER_COLUMNS
build_pla_demo_history = v23.build_pla_demo_history
evaluate_pla_test = v23.evaluate_pla_test
evaluate_all_limits = v23.evaluate_all_limits
evaluate_pnl_explain_alerts = v23.evaluate_pnl_explain_alerts
build_supplied_stress_frame = v23.build_supplied_stress_frame
get_stress_evolution = v23.get_stress_evolution
get_material_stress_scenarios = v23.get_material_stress_scenarios
get_market_sensitivities = v23.get_market_sensitivities
get_var_change_summary = v23.get_var_change_summary
get_var_change_attribution = v23.get_var_change_attribution

STRESS_SCENARIO_LIMITS = {
    "2008 Lehman": 16_000_000.0,
    "2011 US downgrade": 10_000_000.0,
    "2020 COVID": 12_000_000.0,
    "2022 rate hikes": 12_000_000.0,
    "IR steepener": 6_000_000.0,
    "IR flattener": 6_000_000.0,
    "IR +100 bp": 5_000_000.0,
    "IR -100 bp": 5_000_000.0,
    "USD +10%": 4_000_000.0,
    "Vol +50%": 8_000_000.0,
    "IR +200 bp": 10_000_000.0,
    "IR -200 bp": 10_000_000.0,
    "USD +20%": 8_000_000.0,
    "Vol +100%": 16_000_000.0,
    "Credit +150 bp": 8_000_000.0,
    "Equity -30%": 10_000_000.0,
    "EUR/USD -15%": 7_000_000.0,
    "Basis +50 bp": 6_000_000.0,
    "Credit +300 bp": 16_000_000.0,
    "Equity -60%": 20_000_000.0,
    "EUR/USD -30%": 14_000_000.0,
    "Basis +100 bp": 12_000_000.0,
}


def _limit_status(consumption_pct):
    if consumption_pct >= 100.0:
        return "BREACH"
    if consumption_pct >= 80.0:
        return "WARNING"
    return "OK"


def get_stress_scenario_catalog():
    """Return the governed catalogue enriched with scenario P&L limits."""
    return [
        {
            **row,
            "limit": STRESS_SCENARIO_LIMITS.get(row["scenario"]),
            "limit_unit": "EUR P&L loss",
        }
        for row in v23.get_stress_scenario_catalog()
    ]


def get_stress_limit_monitor(as_of_date=None):
    """Evaluate scenario-level loss limits for priced stress results."""
    frame, metadata = build_supplied_stress_frame(as_of_date)
    if frame.empty:
        return {"status": "NO_DATA", "scenarios": [], "summary": {}}
    latest = frame.iloc[-1]
    rows = []
    for scenario, scenario_metadata in metadata.items():
        impact = float(latest[scenario])
        limit = float(STRESS_SCENARIO_LIMITS[scenario])
        consumption = abs(min(impact, 0.0)) / limit * 100.0
        rows.append({
            "scenario": scenario,
            "category": scenario_metadata["type"],
            "impact": impact,
            "limit": limit,
            "consumption_pct": consumption,
            "status": _limit_status(consumption),
        })
    return {
        "status": "EVALUATED",
        "as_of_date": str(pd.Timestamp(latest["cob_date"]).date()),
        "scenarios": rows,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "usage_note": (
            "Scenario limits are configurable deterministic V24 prototype limits. "
            "Consumption is absolute loss divided by limit; 80% is Warning and 100% is Breach."
        ),
    }


def detect_material_risk_movements(as_of_date=None):
    """Detect material VaR, P&L, sensitivity, stress and limit observations."""
    findings = []

    var_summary = get_var_change_summary(as_of_date)
    for comparison in var_summary.get("comparisons", []):
        if not comparison["available"] or comparison["change_pct"] is None:
            continue
        threshold = 10.0 if comparison["period"] == "Daily" else 15.0
        if abs(comparison["change_pct"]) >= threshold:
            findings.append({
                "source": "VaR",
                "finding": f"{comparison['period']} Historical VaR movement",
                "severity": "HIGH" if abs(comparison["change_pct"]) >= threshold * 2 else "MEDIUM",
                "observed": comparison["change_pct"],
                "threshold": threshold,
                "unit": "%",
                "action": "Review VaR movement attribution by risk factor.",
            })

    pnl_alerts = evaluate_pnl_explain_alerts()
    for row in pnl_alerts["desk_results"]:
        if row["status"] == "ALERT":
            findings.append({
                "source": "P&L",
                "finding": f"Unexplained P&L: {row['trading_desk']}",
                "severity": "HIGH",
                "observed": row["unexplained_to_apl_pct"],
                "threshold": row["threshold_pct"],
                "unit": "% of |APL|",
                "action": "Investigate missing drivers and valuation differences.",
            })

    stress_monitor = get_stress_limit_monitor(as_of_date)
    for row in stress_monitor.get("scenarios", []):
        if row["status"] in {"WARNING", "BREACH"}:
            findings.append({
                "source": "Stress",
                "finding": f"{row['scenario']} limit consumption",
                "severity": "CRITICAL" if row["status"] == "BREACH" else "HIGH",
                "observed": row["consumption_pct"],
                "threshold": 100.0 if row["status"] == "BREACH" else 80.0,
                "unit": "%",
                "action": "Escalate breach immediately." if row["status"] == "BREACH" else "Review scenario exposure with the limit owner.",
            })

    limit_evaluation = evaluate_all_limits()
    for row in limit_evaluation["limits"]:
        if row["status"] in {"WARNING", "BREACH"}:
            findings.append({
                "source": "Limits",
                "finding": row["metric"],
                "severity": "CRITICAL" if row["status"] == "BREACH" else "HIGH",
                "observed": row["consumption_pct"],
                "threshold": 100.0 if row["status"] == "BREACH" else 80.0,
                "unit": "%",
                "action": row["escalation_status"],
            })

    sensitivities = pd.DataFrame(get_market_sensitivities()["sensitivities"])
    for measure in ["IR Delta (DV01)", "IR Gamma", "Vega", "FX Delta"]:
        measure_frame = sensitivities.loc[sensitivities["measure"] == measure]
        gross_by_currency = measure_frame.groupby("currency")["value"].apply(lambda values: values.abs().sum())
        gross_total = float(gross_by_currency.sum())
        if gross_total == 0:
            continue
        leading_currency = str(gross_by_currency.idxmax())
        share = float(gross_by_currency.max() / gross_total * 100.0)
        if share >= 55.0:
            findings.append({
                "source": "Sensitivities",
                "finding": f"{measure} concentration: {leading_currency}",
                "severity": "MEDIUM",
                "observed": share,
                "threshold": 55.0,
                "unit": "% of gross",
                "action": "Review currency and tenor concentration.",
            })

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    findings.sort(key=lambda row: (severity_rank[row["severity"]], row["source"], row["finding"]))
    return {
        "as_of_date": var_summary.get("as_of_date"),
        "finding_count": len(findings),
        "summary": {
            "critical": sum(row["severity"] == "CRITICAL" for row in findings),
            "high": sum(row["severity"] == "HIGH" for row in findings),
            "medium": sum(row["severity"] == "MEDIUM" for row in findings),
        },
        "findings": findings,
        "usage_note": (
            "V24 materiality detection is deterministic and threshold-based. "
            "The LLM may explain findings but must not change their values or severity."
        ),
    }


v8.TOOL_FUNCTIONS["get_stress_scenario_catalog"] = get_stress_scenario_catalog
v8.TOOL_DESCRIPTIONS["get_stress_scenario_catalog"] = "Governed stress catalogue with scenario-level loss limits."
v8.TOOL_FUNCTIONS["get_stress_limit_monitor"] = get_stress_limit_monitor
v8.TOOL_DESCRIPTIONS["get_stress_limit_monitor"] = "Scenario-level stress loss, limit consumption and status."
v8.TOOL_FUNCTIONS["detect_material_risk_movements"] = detect_material_risk_movements
v8.TOOL_DESCRIPTIONS["detect_material_risk_movements"] = "Deterministic material findings across VaR, P&L, sensitivities, stress and limits."

v9.SYSTEM_INSTRUCTION += """

V24 controls:
- Use detect_material_risk_movements for consolidated material observations.
- Use get_stress_limit_monitor for scenario limit consumption and status.
- Treat 80% consumption as Warning and 100% as Breach.
- Materiality findings are deterministic; do not alter their severity with narrative judgment.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v23.ask_risk_agent
