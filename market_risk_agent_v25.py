"""M.R. AI Agent V25: short-tenor limits and an auditable daily risk brief."""

from __future__ import annotations

import pandas as pd
from google.genai import types

import market_risk_agent_v24 as v24


VERSION = "V25"
v24.v9.VERSION = VERSION
v23 = v24.v23
v22 = v24.v22
v21 = v24.v21
v20 = v24.v20
v19 = v24.v19
v18 = v24.v18
v17 = v24.v17
v16 = v24.v16
v15 = v24.v15
v14 = v24.v14
v13 = v24.v13
v12 = v24.v12
v11 = v24.v11
v9 = v24.v9
v8 = v24.v8
DRIVER_COLUMNS = v24.DRIVER_COLUMNS
build_pla_demo_history = v24.build_pla_demo_history
evaluate_pla_test = v24.evaluate_pla_test
evaluate_all_limits = v24.evaluate_all_limits
evaluate_pnl_explain_alerts = v24.evaluate_pnl_explain_alerts
build_supplied_stress_frame = v24.build_supplied_stress_frame
get_stress_evolution = v24.get_stress_evolution
get_material_stress_scenarios = v24.get_material_stress_scenarios
get_stress_scenario_catalog = v24.get_stress_scenario_catalog
get_stress_limit_monitor = v24.get_stress_limit_monitor
get_var_change_summary = v24.get_var_change_summary
get_var_change_attribution = v24.get_var_change_attribution
detect_material_risk_movements = v24.detect_material_risk_movements

TENOR_WEIGHTS = {
    "1M": 0.03,
    "3M": 0.05,
    "6M": 0.07,
    "1Y": 0.10,
    "2Y": 0.17,
    "5Y": 0.28,
    "10Y": 0.20,
    "30Y": 0.10,
}

SENSITIVITY_LIMITS = {
    "IR Delta (DV01)": {"limit": 250_000.0, "unit": "EUR / bp", "owner": "Rates Risk"},
    "IR Gamma": {"limit": 5_000.0, "unit": "EUR / bp²", "owner": "Rates Risk"},
    "Vega": {"limit": 150_000.0, "unit": "EUR / vol point", "owner": "Volatility Risk"},
    "FX Delta": {"limit": 500_000.0, "unit": "EUR / 1% spot", "owner": "FX Risk"},
    "Theta": {"limit": 40_000.0, "unit": "EUR / day", "owner": "Market Risk"},
}


def get_market_sensitivities():
    """Return curve sensitivities with additional sub-one-year tenor buckets."""
    source = v24.get_market_sensitivities()
    frame = pd.DataFrame(source["sensitivities"])
    rate_frame = frame.loc[frame["risk_class"] == "Rates"].copy()
    non_rate_rows = frame.loc[frame["risk_class"] != "Rates"].to_dict("records")

    group_columns = [
        "risk_class", "measure", "currency", "curve_type", "curve", "unit"
    ]
    curve_totals = rate_frame.groupby(group_columns, as_index=False)["value"].sum()
    expanded = []
    for row in curve_totals.to_dict("records"):
        for tenor, weight in TENOR_WEIGHTS.items():
            expanded.append({
                **row,
                "tenor": tenor,
                "value": float(row["value"]) * weight,
                "definition": (
                    f"{row['measure']} for {row['curve']}, allocated to the {tenor} tenor bucket."
                ),
            })

    return {
        **source,
        "tenors": list(TENOR_WEIGHTS),
        "sensitivities": expanded + non_rate_rows,
        "usage_note": (
            "Deterministic V25 prototype feed across EUR, USD, JPY, GBP and HKD. "
            "Rate-curve totals are preserved across 1M, 3M, 6M, 1Y, 2Y, 5Y, 10Y and 30Y buckets."
        ),
    }


def evaluate_sensitivity_limits():
    """Evaluate governed gross limits for each sensitivity measure."""
    frame = pd.DataFrame(get_market_sensitivities()["sensitivities"])
    rows = []
    for measure, rule in SENSITIVITY_LIMITS.items():
        measure_frame = frame.loc[frame["measure"] == measure]
        exposure = float(measure_frame["value"].abs().sum())
        limit = float(rule["limit"])
        consumption = 0.0 if limit == 0 else exposure / limit * 100.0
        rows.append({
            "measure": measure,
            "gross_exposure": exposure,
            "limit": limit,
            "consumption_pct": consumption,
            "status": v24._limit_status(consumption),
            "unit": rule["unit"],
            "owner": rule["owner"],
        })
    return {
        "limits": rows,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "usage_note": (
            "Sensitivity consumption uses gross absolute exposure. Below 80% is OK, "
            "80% to below 100% is WARNING, and 100% or above is BREACH."
        ),
    }


def evaluate_all_limits():
    """Return one internally consistent V25 limit inventory."""
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
            "consumption_basis": "Gross absolute sensitivity",
            "escalation_status": (
                "Immediate escalation required" if item["status"] == "BREACH"
                else "Owner review required" if item["status"] == "WARNING"
                else "No escalation"
            ),
        })
    return {
        **base,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "limits": rows,
        "usage_note": (
            "V25 uses one consistent sensitivity feed for charts and controls. Limits remain configurable "
            "prototype values; below 80% is OK, 80% to below 100% is WARNING, and 100% or above is BREACH."
        ),
    }


def detect_material_risk_movements(as_of_date=None):
    """Return V24 material findings refreshed with the V25 sensitivity controls."""
    result = v24.detect_material_risk_movements(as_of_date)
    old_sensitivity_limit_names = {
        "Gross IR Delta (DV01)", "IR Gamma", "Gross FX Delta", "Gross Vega"
    }
    findings = [
        item for item in result["findings"]
        if not (item["source"] == "Limits" and item["finding"] in old_sensitivity_limit_names)
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
                "action": (
                    "Immediate escalation required" if row["status"] == "BREACH"
                    else "Owner review required"
                ),
            })
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    findings.sort(key=lambda row: (severity_rank[row["severity"]], row["source"], row["finding"]))
    return {
        **result,
        "finding_count": len(findings),
        "summary": {
            "critical": sum(row["severity"] == "CRITICAL" for row in findings),
            "high": sum(row["severity"] == "HIGH" for row in findings),
            "medium": sum(row["severity"] == "MEDIUM" for row in findings),
        },
        "findings": findings,
        "usage_note": (
            "V25 materiality detection is deterministic and uses the same sensitivity limits as the dashboard. "
            "The LLM may explain findings but cannot change their values or severity."
        ),
    }

def generate_daily_risk_brief(as_of_date=None):
    """Create a deterministic, auditable daily risk brief and action queue."""
    materiality = detect_material_risk_movements(as_of_date)
    current = v8.get_current_risk()
    stress = get_stress_limit_monitor(as_of_date)
    findings = materiality["findings"]
    owner_by_source = {
        "VaR": "Market Risk",
        "P&L": "P&L Control",
        "Stress": "Stress Testing",
        "Limits": "Named limit owner",
        "Sensitivities": "Risk-factor owner",
    }
    actions = [
        {
            "action_id": f"A{index:02d}",
            "priority": item["severity"],
            "source": item["source"],
            "finding": item["finding"],
            "owner": owner_by_source.get(item["source"], "Market Risk"),
            "required_action": item["action"],
            "workflow_status": "OPEN",
            "due": "Today" if item["severity"] in {"CRITICAL", "HIGH"} else "Next review",
        }
        for index, item in enumerate(findings, start=1)
    ]
    if materiality["summary"]["critical"]:
        overall_status = "ESCALATION REQUIRED"
    elif materiality["summary"]["high"]:
        overall_status = "REVIEW REQUIRED"
    elif materiality["summary"]["medium"]:
        overall_status = "MONITOR"
    else:
        overall_status = "CLEAR"
    return {
        "as_of_date": materiality["as_of_date"],
        "overall_status": overall_status,
        "headline": (
            f"{materiality['finding_count']} material finding(s): "
            f"{materiality['summary']['critical']} critical, "
            f"{materiality['summary']['high']} high and "
            f"{materiality['summary']['medium']} medium."
        ),
        "risk_snapshot": {
            "historical_var": float(current["var_hist"]),
            "stressed_var": float(current["stressed_var"]),
            "expected_shortfall": float(current["expected_shortfall"]),
            "stress_breaches": stress.get("summary", {}).get("breaches", 0),
            "stress_warnings": stress.get("summary", {}).get("warnings", 0),
        },
        "actions": actions,
        "sign_off": {
            "status": "PENDING" if actions else "READY",
            "required_role": "Market Risk Manager",
            "open_actions": len(actions),
        },
        "evidence": findings,
        "usage_note": (
            "The V25 daily brief is generated from deterministic controls. It is a workflow aid, "
            "not an approval record; comments and sign-off require an authorised user and persistent store."
        ),
    }


v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Curve sensitivities including sub-one-year tenor buckets."
v8.TOOL_FUNCTIONS["evaluate_all_limits"] = evaluate_all_limits
v8.TOOL_DESCRIPTIONS["evaluate_all_limits"] = "Consistent V25 limit inventory using the same sensitivity feed as the dashboard."
v8.TOOL_FUNCTIONS["detect_material_risk_movements"] = detect_material_risk_movements
v8.TOOL_DESCRIPTIONS["detect_material_risk_movements"] = "Material risk findings refreshed with V25 sensitivity controls."
v8.TOOL_FUNCTIONS["evaluate_sensitivity_limits"] = evaluate_sensitivity_limits
v8.TOOL_DESCRIPTIONS["evaluate_sensitivity_limits"] = "Gross sensitivity limits and consumption by measure."
v8.TOOL_FUNCTIONS["generate_daily_risk_brief"] = generate_daily_risk_brief
v8.TOOL_DESCRIPTIONS["generate_daily_risk_brief"] = "Deterministic daily risk brief with evidence, actions and sign-off status."

v9.SYSTEM_INSTRUCTION += """

V25 daily workflow:
- Use generate_daily_risk_brief for the consolidated daily status, evidence and action queue.
- Use evaluate_sensitivity_limits for governed sensitivity consumption.
- The brief is deterministic and auditable; the LLM may explain it but must not invent closure or sign-off.
- IMA means Internal Models Approach. A PLA result is one desk-level condition and is not, by itself, supervisory IMA approval.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v24.ask_risk_agent