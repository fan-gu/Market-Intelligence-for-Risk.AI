"""V30 consolidated runtime API; archived versions are not imported by the dashboard."""
from __future__ import annotations
import sys, json, os, hashlib, contextlib, io
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ---- V8 implementation ----
import json
import os
from pathlib import Path

import pandas as pd
# ============================================================
# MARKET RISK AI ASSISTANT — VERSION 8
#
# V8 keeps V7's deterministic analytics tools, but makes the
# investigation process explicit:
#     PLAN -> EXECUTION -> OBSERVATION -> SYNTHESIS
# ============================================================

_DATA_FILE_NAME = "market_risk_attribution_wide.csv"
_configured_data_file = os.getenv("RISK_DATA_FILE")
if _configured_data_file:
    FILE_NAME = _configured_data_file
else:
    _source_path = Path(__file__).resolve()
    _repo_root = _source_path.parents[2] if _source_path.parent.name == "versions" else _source_path.parent
    FILE_NAME = str(_repo_root / "data" / _DATA_FILE_NAME)
MODEL_NAME = "gemini-3.6-flash"


# ============================================================
# 1. CONFIGURATION AND DATA
# ============================================================

load_dotenv()
client = None

def get_gemini_client():
    global client
    if client is not None:
        return client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            api_key = None
    if not api_key:
        raise RuntimeError("Gemini is not configured. Add GEMINI_API_KEY under Streamlit Cloud → App settings → Secrets.")
    client = genai.Client(api_key=api_key)
    return client

GEMINI_AVAILABLE = bool(os.getenv("GEMINI_API_KEY"))


def load_data():
    risk_data = pd.read_csv(FILE_NAME)
    risk_data["cob_date"] = pd.to_datetime(risk_data["cob_date"])
    return risk_data.sort_values("cob_date").reset_index(drop=True)


df = load_data()


# ============================================================
# 2. V7 ANALYTICS TOOLS (UNCHANGED IN PURPOSE)
# ============================================================

def get_current_risk():
    current = df.iloc[-1]
    return {
        "date": str(current["cob_date"].date()),
        "var_hist": float(current["var_1d_99_hist"]),
        "var_parametric": float(current["var_1d_99_param"]),
        "var_monte_carlo": float(current["var_1d_99_mc"]),
        "var_10d_regulatory": float(current["var_10d_99_reg"]),
        "stressed_var": float(current["stressed_var_1d_99"]),
        "expected_shortfall": float(current["expected_shortfall_97_5"]),
        "var_limit": float(current["var_limit_amount"]),
        "limit_utilisation": float(current["var_limit_utilization_pct"]),
    }


def get_var_trend():
    current = df.iloc[-1]
    previous = df.iloc[-2]
    current_var = float(current["var_1d_99_hist"])
    previous_var = float(previous["var_1d_99_hist"])
    change = current_var - previous_var
    average_10d = float(df["var_1d_99_hist"].mean())
    return {
        "current_var": current_var,
        "previous_var": previous_var,
        "change": change,
        "change_pct": (change / previous_var) * 100,
        "10_day_average": average_10d,
        "vs_10_day_average_pct": ((current_var - average_10d) / average_10d) * 100,
    }


def get_var_attribution():
    current = df.iloc[-1]
    columns = {
        "FX Spot": "contrib_var_fx_spot",
        "FX Implied Vol": "contrib_var_fx_vol_implied",
        "FX Basis": "contrib_var_fx_basis",
        "SOFR Curve": "contrib_var_ir_sofr_curve",
        "€STR Curve": "contrib_var_ir_estr_curve",
        "SONIA Curve": "contrib_var_ir_sonia_curve",
        "Swaption Vol": "contrib_var_ir_swaption_vol",
        "IR Basis": "contrib_var_ir_basis_tenor",
        "IR Convexity": "contrib_var_ir_convexity",
        "IG Credit Spread": "contrib_var_credit_ig_spread",
        "HY Credit Spread": "contrib_var_credit_hy_spread",
        "CDS Basis": "contrib_var_credit_cds_basis",
        "Equity Spot": "contrib_var_equity_spot",
        "Equity Vol": "contrib_var_equity_vol",
        "Energy": "contrib_var_commodity_energy",
        "Metals": "contrib_var_commodity_metals",
        "Inflation Breakeven": "contrib_var_inflation_breakeven",
    }
    result = {name: float(current[column]) for name, column in columns.items()}
    return dict(sorted(result.items(), key=lambda item: item[1], reverse=True))


def get_limit_analysis():
    current = df.iloc[-1]
    utilisation = float(current["var_limit_utilization_pct"])
    status = "CRITICAL" if utilisation >= 90 else "HIGH" if utilisation >= 80 else "MODERATE" if utilisation >= 60 else "LOW"
    return {
        "current_var": float(current["var_1d_99_hist"]),
        "var_limit": float(current["var_limit_amount"]),
        "utilisation_pct": utilisation,
        "status": status,
    }


def get_pnl_analysis():
    current = df.iloc[-1]
    return {
        "actual_pnl": float(current["actual_pnl"]),
        "hypothetical_pnl": float(current["hypothetical_pnl"]),
        "clean_pnl": float(current["clean_pnl"]),
        "unexplained_pnl": float(current["unexplained_pnl"]),
    }


def get_backtesting_analysis():
    current = df.iloc[-1]
    return {
        "hypothetical_exception": int(current["backtest_hypo_exception"]),
        "actual_exception": int(current["backtest_actual_exception"]),
        "exception_count_250d": int(current["backtest_exception_count_250d"]),
        "basel_traffic_light_zone": str(current["basel_traffic_light_zone"]),
    }


def get_stress_analysis():
    current = df.iloc[-1]
    scenarios = {
        "2008 Lehman Crisis": "stress_2008_lehman_crisis",
        "2011 US Downgrade": "stress_2011_us_downgrade",
        "2020 COVID Liquidity": "stress_2020_covid_liquidity",
        "2022 Rate Hikes": "stress_2022_rate_hikes",
        "IR +100bp": "stress_ir_up_100bp",
        "IR -100bp": "stress_ir_down_100bp",
        "IR Steepener": "stress_ir_steepener_50bp",
        "IR Flattener": "stress_ir_flattener_50bp",
        "USD +10%": "stress_fx_usd_up_10pct",
        "Volatility +50%": "stress_vol_up_50pct",
    }
    return {name: float(current[column]) for name, column in scenarios.items()}


def get_ten_day_summary():
    return {
        "var_average": float(df["var_1d_99_hist"].mean()),
        "var_min": float(df["var_1d_99_hist"].min()),
        "var_max": float(df["var_1d_99_hist"].max()),
        "var_standard_deviation": float(df["var_1d_99_hist"].std()),
        "average_limit_utilisation": float(df["var_limit_utilization_pct"].mean()),
        "maximum_limit_utilisation": float(df["var_limit_utilization_pct"].max()),
        "cumulative_actual_pnl": float(df["actual_pnl"].sum()),
        "best_pnl_day": float(df["actual_pnl"].max()),
        "worst_pnl_day": float(df["actual_pnl"].min()),
    }


def validate_data():
    date_diffs = df["cob_date"].diff().dropna().dt.days
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_dates": int(df["cob_date"].duplicated().sum()),
        "date_sequence_ok": bool((date_diffs == 1).all()),
    }


TOOL_FUNCTIONS = {
    "get_current_risk": get_current_risk,
    "get_var_trend": get_var_trend,
    "get_var_attribution": get_var_attribution,
    "get_limit_analysis": get_limit_analysis,
    "get_pnl_analysis": get_pnl_analysis,
    "get_backtesting_analysis": get_backtesting_analysis,
    "get_stress_analysis": get_stress_analysis,
    "get_ten_day_summary": get_ten_day_summary,
    "validate_data": validate_data,
}


def execute_tool(function_name):
    function = TOOL_FUNCTIONS.get(function_name)
    if function is None:
        return {"error": f"Unknown tool: {function_name}"}
    return function()


# ============================================================
# 3. GEMINI FUNCTION DEFINITIONS
# ============================================================

TOOL_DESCRIPTIONS = {
    "get_current_risk": "Latest VaR, stressed VaR, expected shortfall, and limit utilisation.",
    "get_var_trend": "Latest historical VaR change versus yesterday and 10-day average.",
    "get_var_attribution": "Current VaR contribution by risk factor.",
    "get_limit_analysis": "VaR limit utilisation and risk classification.",
    "get_pnl_analysis": "Actual, hypothetical, clean, and unexplained P&L.",
    "get_backtesting_analysis": "VaR exceptions and Basel traffic-light status.",
    "get_stress_analysis": "Historical and hypothetical stress-scenario P&L impacts.",
    "get_ten_day_summary": "10-day VaR, limit-utilisation, and P&L statistics.",
    "validate_data": "Basic data-quality checks.",
}

tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=name, description=description)
            for name, description in TOOL_DESCRIPTIONS.items()
        ]
    )
]


# ============================================================
# 4. EXPLICIT PLANNING STAGE
# ============================================================

def parse_plan(response_text):
    """Parse Gemini's JSON plan and safely discard unknown tool names."""
    try:
        plan = json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "steps": ["Assess the requested market-risk question."],
            "tools": [],
        }

    steps = plan.get("steps", [])
    tool_names = plan.get("tools", [])
    if not isinstance(steps, list) or not isinstance(tool_names, list):
        return {"steps": ["Assess the requested market-risk question."], "tools": []}

    return {
        "steps": [str(step) for step in steps if str(step).strip()],
        "tools": [name for name in tool_names if name in TOOL_FUNCTIONS],
    }


def create_investigation_plan(question):
    if client is None:
        raise RuntimeError("Gemini is not configured. Add GEMINI_API_KEY under Streamlit Cloud → App settings → Secrets.")
    available_tools = "\n".join(
        f"- {name}: {description}" for name, description in TOOL_DESCRIPTIONS.items()
    )
    planning_instruction = f"""
You are the planning stage of a market-risk investigation.
Create a concise, evidence-led investigation plan for the user's question.

Available deterministic analytics tools:
{available_tools}

Return JSON only, using exactly this structure:
{{
  "steps": ["short investigation step", "..."],
  "tools": ["exact_tool_name", "..."]
}}

Rules:
- Plan before any data is examined.
- Use only the exact tool names listed above.
- Include only tools necessary to answer the question.
- For a broad portfolio risk assessment, cover current risk, trend, attribution,
  limits, and stress testing.
- Put tools in the execution order that best supports the investigation.
"""
    response = get_gemini_client().models.generate_content(
        model=MODEL_NAME,
        contents=f"{planning_instruction}\n\nUser question: {question}",
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return parse_plan(response.text)


def print_plan(plan):
    print("\n[AGENT PLAN]\n")
    for number, step in enumerate(plan["steps"], start=1):
        print(f"{number}. {step}")


def execute_plan(plan):
    results = {}
    print("\n[AGENT EXECUTION]\n")
    if not plan["tools"]:
        print("No deterministic tools were selected by the plan.")
    for function_name in plan["tools"]:
        print(f"→ {function_name}()")
        results[function_name] = execute_tool(function_name)
    return results


# ============================================================
# 5. OBSERVATION AND SYNTHESIS STAGE
# ============================================================

SYSTEM_INSTRUCTION = """
You are a Senior Market Risk Manager at a large international bank.
You receive an explicit investigation plan and deterministic Python tool results.

Use only the supplied tool results for financial facts. Do not invent numbers,
recalculate metrics already supplied by a tool, or claim causality that the
data cannot establish. Clearly distinguish facts from interpretation. If a
material issue cannot be assessed with the available results, say so.

Before the final answer, decide whether another deterministic tool is needed.
If it is, request it. Otherwise provide a concise, professional risk-manager
assessment.
"""


def ask_risk_agent(question):
    if client is None:
        raise RuntimeError("Gemini is not configured. Add GEMINI_API_KEY under Streamlit Cloud → App settings → Secrets.")
    plan = create_investigation_plan(question)
    print_plan(plan)
    results = execute_plan(plan)

    chat = get_gemini_client().chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools,
        ),
    )
    evidence = json.dumps(results, indent=2)
    response = chat.send_message(
        f"User question: {question}\n\n"
        f"Approved investigation plan: {json.dumps(plan)}\n\n"
        f"Observed deterministic tool results:\n{evidence}\n\n"
        "Review the observed results. Request another tool only if it is needed "
        "to complete the requested assessment."
    )

    additional_results = {}
    while response.function_calls:
        print("\n[ADDITIONAL INVESTIGATION]\n")
        function_responses = []
        for function_call in response.function_calls:
            function_name = function_call.name
            print(f"→ {function_name}()")
            result = execute_tool(function_name)
            additional_results[function_name] = result
            function_responses.append(
                types.Part.from_function_response(
                    name=function_name,
                    response={"result": result},
                )
            )
        response = chat.send_message(function_responses)

    print("\n[AGENT SYNTHESIS]\n")
    return response.text


# ============================================================
# 6. USER INTERFACE
# ============================================================

def main():
    print("\n" + "=" * 70)
    print("             MARKET RISK AI ASSISTANT")
    print("                         V8")
    print("=" * 70)
    print("\n10-day / 54-column dataset loaded.")
    print("Gemini planning agent is ready.")
    print("Each investigation shows PLAN, EXECUTION, and SYNTHESIS.")
    print("Type 'exit' to stop.\n")

    while True:
        question = input("You: ")
        if question.lower().strip() == "exit":
            print("Assistant: Goodbye.")
            break

        try:
            answer = ask_risk_agent(question)
            print("Assistant:")
            print(answer)
            print()
        except Exception as error:
            print("\nERROR:")
            print(error)
            print()


if __name__ == "__main__":
    main()

# Snapshot this version.
v8 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V9 implementation ----
"""Market Risk AI Assistant V9: investigation memory and audit logging.

V9 retains V8's deterministic analytics and adds one agent-visible function:
get_recent_investigation_context().  Each completed investigation is stored in
an append-only local JSONL audit log, so relevant follow-up context can be
retrieved without treating a prior answer as current market-risk evidence.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

VERSION = "V9"
AUDIT_LOG_PATH = Path(__file__).with_name("market_risk_investigation_audit.jsonl")
MAX_CONTEXT_RECORDS = 3
MAX_ANSWER_CHARS = 4_000


def get_dataset_context():
    """Return immutable identifiers that tie an investigation to its input data."""
    data_path = Path(v8.FILE_NAME)
    try:
        digest = hashlib.sha256(data_path.read_bytes()).hexdigest()[:16]
    except OSError:
        digest = "unavailable"

    return {
        "source_file": data_path.name,
        "as_of_date": str(v8.df.iloc[-1]["cob_date"].date()),
        "row_count": len(v8.df),
        "data_fingerprint": digest,
    }


def read_audit_log():
    """Read valid entries only; a damaged historical line must not stop the agent."""
    if not AUDIT_LOG_PATH.exists():
        return []

    records = []
    try:
        with AUDIT_LOG_PATH.open("r", encoding="utf-8") as audit_file:
            for line in audit_file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError:
        return []
    return records


def get_recent_investigation_context():
    """Retrieve recent investigations for the current risk-engine data snapshot."""
    dataset_context = get_dataset_context()
    matching_records = [
        record
        for record in read_audit_log()
        if record.get("dataset", {}).get("data_fingerprint")
        == dataset_context["data_fingerprint"]
    ]
    recent_records = matching_records[-MAX_CONTEXT_RECORDS:]

    return {
        "dataset": dataset_context,
        "matching_investigation_count": len(matching_records),
        "recent_investigations": [
            {
                "timestamp_utc": record.get("timestamp_utc"),
                "question": record.get("question"),
                "tools_used": record.get("tools_used", []),
                "answer": record.get("answer"),
            }
            for record in recent_records
        ],
        "usage_note": (
            "This is prior investigation context, not current financial evidence. "
            "Use deterministic analytics tools to support all current risk facts."
        ),
    }


def write_audit_record(question, plan, results, additional_results, answer):
    """Append a traceable record after a completed investigation."""
    record = {
        "version": VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": get_dataset_context(),
        "question": question,
        "plan": plan,
        "tools_used": list(results) + list(additional_results),
        "observed_results": results,
        "additional_results": additional_results,
        "answer": answer[:MAX_ANSWER_CHARS],
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(record, ensure_ascii=False) + "\n")


# Register V9's single new agent function alongside V8's analytics tools.
v8.TOOL_FUNCTIONS["get_recent_investigation_context"] = get_recent_investigation_context
v8.TOOL_DESCRIPTIONS["get_recent_investigation_context"] = (
    "Recent completed investigations for the same risk-engine data snapshot. "
    "Use for follow-up questions; current financial claims still require analytics tools."
)

tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=name, description=description)
            for name, description in v8.TOOL_DESCRIPTIONS.items()
        ]
    )
]

SYSTEM_INSTRUCTION = v8.SYSTEM_INSTRUCTION + """

V9 memory control:
- get_recent_investigation_context provides auditable prior conversation context
  only for the identical input-data fingerprint.
- Do not present a previous answer or remembered number as current evidence.
- For every current financial fact, use a deterministic analytics tool result
  from this investigation.
"""


def ask_risk_agent(question):
    plan = v8.create_investigation_plan(question)
    v8.print_plan(plan)
    results = v8.execute_plan(plan)

    chat = get_gemini_client().chats.create(
        model=v8.MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools,
        ),
    )
    evidence = json.dumps(results, indent=2)
    response = chat.send_message(
        f"User question: {question}\n\n"
        f"Approved investigation plan: {json.dumps(plan)}\n\n"
        f"Observed deterministic tool results:\n{evidence}\n\n"
        "Review the observed results. Request another tool only if it is needed "
        "to complete the requested assessment."
    )

    additional_results = {}
    while response.function_calls:
        print("\n[ADDITIONAL INVESTIGATION]\n")
        function_responses = []
        for function_call in response.function_calls:
            function_name = function_call.name
            print(f"→ {function_name}()")
            result = v8.execute_tool(function_name)
            additional_results[function_name] = result
            function_responses.append(
                types.Part.from_function_response(
                    name=function_name,
                    response={"result": result},
                )
            )
        response = chat.send_message(function_responses)

    answer = response.text
    write_audit_record(question, plan, results, additional_results, answer)
    print("\n[AGENT SYNTHESIS]\n")
    return answer


def main():
    print("\n" + "=" * 70)
    print("             MARKET RISK AI ASSISTANT")
    print("                         V9")
    print("=" * 70)
    print("\n10-day / 54-column dataset loaded.")
    print("Gemini planning agent with investigation memory is ready.")
    print("Completed investigations are written to a local audit log.")
    print("Type 'exit' to stop.\n")

    while True:
        question = input("You: ")
        if question.lower().strip() == "exit":
            print("Assistant: Goodbye.")
            break

        try:
            answer = ask_risk_agent(question)
            print("Assistant:")
            print(answer)
            print()
        except Exception as error:
            print("\nERROR:")
            print(error)
            print()


if __name__ == "__main__":
    main()

# Snapshot this version.
v9 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V11 implementation ----
"""Market Risk AI Assistant V11: deterministic risk alerts."""

VERSION = "V11"
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}


def get_risk_alerts():
    """Return transparent, rules-based alerts from the current data snapshot."""
    alerts = []
    limit = v8.get_limit_analysis()
    trend = v8.get_var_trend()
    backtesting = v8.get_backtesting_analysis()
    quality = v8.validate_data()
    stresses = v8.get_stress_analysis()

    if limit["utilisation_pct"] >= 90:
        alerts.append({
            "severity": "CRITICAL",
            "title": "VaR limit utilisation is critical",
            "summary": f"Utilisation is {limit['utilisation_pct']:.1f}%, above the 90% critical threshold.",
        })
    elif limit["utilisation_pct"] >= 80:
        alerts.append({
            "severity": "HIGH",
            "title": "VaR limit utilisation is high",
            "summary": f"Utilisation is {limit['utilisation_pct']:.1f}%, above the 80% high threshold.",
        })
    elif limit["utilisation_pct"] >= 60:
        alerts.append({
            "severity": "MEDIUM",
            "title": "VaR limit utilisation requires monitoring",
            "summary": f"Utilisation is {limit['utilisation_pct']:.1f}%, above the 60% monitoring threshold.",
        })

    movement = abs(trend["change_pct"])
    if movement >= 20:
        alerts.append({
            "severity": "HIGH",
            "title": "Material day-on-day VaR movement",
            "summary": f"Historical VaR moved {trend['change_pct']:.1f}% versus the prior observation.",
        })
    elif movement >= 10:
        alerts.append({
            "severity": "MEDIUM",
            "title": "Notable day-on-day VaR movement",
            "summary": f"Historical VaR moved {trend['change_pct']:.1f}% versus the prior observation.",
        })

    exception_types = []
    if backtesting["hypothetical_exception"]:
        exception_types.append("hypothetical")
    if backtesting["actual_exception"]:
        exception_types.append("actual")
    if exception_types:
        alerts.append({
            "severity": "HIGH",
            "title": "New VaR backtesting exception",
            "summary": f"Today's {', '.join(exception_types)} P&L breached the VaR backtest.",
        })

    data_issues = []
    if quality["missing_values"]:
        data_issues.append(f"{quality['missing_values']} missing values")
    if quality["duplicate_dates"]:
        data_issues.append(f"{quality['duplicate_dates']} duplicate dates")
    calendar_review_needed = not quality["date_sequence_ok"]
    if data_issues:
        alerts.append({
            "severity": "CRITICAL",
            "title": "Risk data-quality issue",
            "summary": "; ".join(data_issues) + ".",
        })

    if calendar_review_needed:
        alerts.append({
            "severity": "INFO",
            "title": "Data-calendar coverage review",
            "summary": "The observations are not consecutive calendar days; confirm the risk-engine calendar covers weekends and holidays as intended.",
        })
    worst_scenario, worst_impact = min(stresses.items(), key=lambda item: item[1])
    if worst_impact < 0:
        alerts.append({
            "severity": "INFO",
            "title": "Most adverse stress scenario",
            "summary": f"{worst_scenario} produces the lowest reported impact: {worst_impact:,.0f}.",
        })

    if not alerts:
        alerts.append({
            "severity": "INFO",
            "title": "No rule-based alerts",
            "summary": "All monitored metrics are within the configured V11 thresholds.",
        })

    alerts.sort(key=lambda alert: SEVERITY_ORDER[alert["severity"]])
    action_required = sum(alert["severity"] != "INFO" for alert in alerts)
    return {
        "as_of_date": v8.get_current_risk()["date"],
        "action_required_count": action_required,
        "alerts": alerts,
        "thresholds": {
            "limit_utilisation_monitoring_pct": 60,
            "limit_utilisation_high_pct": 80,
            "limit_utilisation_critical_pct": 90,
            "var_movement_notable_pct": 10,
            "var_movement_material_pct": 20,
        },
    }


# Register exactly one new deterministic V11 agent function.
v8.TOOL_FUNCTIONS["get_risk_alerts"] = get_risk_alerts
v8.TOOL_DESCRIPTIONS["get_risk_alerts"] = (
    "Rule-based current alerts for VaR limits, material VaR movements, "
    "backtesting exceptions, data quality, and the most adverse stress scenario."
)
v9.VERSION = VERSION
v9.SYSTEM_INSTRUCTION += """

V11 alert control:
- get_risk_alerts reports transparent rules-based monitoring alerts.
- State the alert thresholds when they are material to your conclusion.
- Treat alerts as prompts for review, not proof of causality.
"""
v9.tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=name, description=description)
            for name, description in v8.TOOL_DESCRIPTIONS.items()
        ]
    )
]

ask_risk_agent = v9.ask_risk_agent


def main():
    print("\nMARKET RISK AI ASSISTANT — V11")
    print("Rule-based risk alerts and investigation memory are ready.")
    print("Type 'exit' to stop.\n")
    while True:
        question = input("You: ")
        if question.lower().strip() == "exit":
            print("Assistant: Goodbye.")
            break
        try:
            print("Assistant:")
            print(ask_risk_agent(question))
            print()
        except Exception as error:
            print(f"\nERROR:\n{error}\n")


if __name__ == "__main__":
    main()

# Snapshot this version.
v11 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- ingestion helper ----
"""V12 risk-run ingestion and validation for the Market Risk AI demo.

This module deliberately models a generic downstream interface.  It does not
represent any bank's internal architecture or data contract.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "cob_date",
    "portfolio_id",
    "reporting_currency",
    "var_1d_99_hist",
    "stressed_var_1d_99",
    "expected_shortfall_97_5",
    "var_limit_amount",
    "var_limit_utilization_pct",
    "actual_pnl",
    "hypothetical_pnl",
    "backtest_exception_count_250d",
}

NUMERIC_COLUMNS = REQUIRED_COLUMNS - {
    "cob_date",
    "portfolio_id",
    "reporting_currency",
}


def _fingerprint(source_path: Path) -> str:
    """Return a short, content-based identifier for traceable demo runs."""
    return hashlib.sha256(source_path.read_bytes()).hexdigest()[:16]


def ingest_and_validate_risk_run(source_path: str | Path) -> dict:
    """Validate a risk-engine CSV and return curated data plus safe lineage.

    A real production adapter would receive an explicit run ID, source-system
    name, model version and approval status.  The existing demo CSV has none of
    these fields, so V12 generates only a deterministic *demo* run ID and calls
    the result ``VALIDATED`` rather than ``APPROVED``.
    """
    path = Path(source_path)
    if not path.exists():
        return {
            "validation_status": "REJECTED",
            "errors": [f"Risk-run file was not found: {path.name}"],
            "warnings": [],
            "data": pd.DataFrame(),
            "lineage": {"source_file": path.name},
        }

    try:
        raw_data = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as error:
        return {
            "validation_status": "REJECTED",
            "errors": [f"Risk-run file could not be read: {error}"],
            "warnings": [],
            "data": pd.DataFrame(),
            "lineage": {"source_file": path.name},
        }

    errors = []
    warnings = []
    missing_columns = sorted(REQUIRED_COLUMNS - set(raw_data.columns))
    if missing_columns:
        errors.append("Missing required columns: " + ", ".join(missing_columns))

    data = raw_data.copy()
    if "cob_date" in data:
        data["cob_date"] = pd.to_datetime(data["cob_date"], errors="coerce")
        invalid_dates = int(data["cob_date"].isna().sum())
        if invalid_dates:
            errors.append(f"{invalid_dates} invalid or missing COB date(s).")
    else:
        invalid_dates = 0

    invalid_numeric_values = 0
    for column in NUMERIC_COLUMNS & set(data.columns):
        converted = pd.to_numeric(data[column], errors="coerce")
        invalid_numeric_values += int(converted.isna().sum() - data[column].isna().sum())
        data[column] = converted
    if invalid_numeric_values:
        errors.append(f"{invalid_numeric_values} invalid numeric value(s).")

    missing_values = int(data.isna().sum().sum())
    duplicate_dates = int(data["cob_date"].duplicated().sum()) if "cob_date" in data else 0
    if duplicate_dates:
        warnings.append(f"{duplicate_dates} duplicate COB date(s) retained for review.")
    if data.empty:
        errors.append("Risk run contains no data rows.")

    fingerprint = _fingerprint(path)
    latest_date = None
    earliest_date = None
    if "cob_date" in data and data["cob_date"].notna().any():
        earliest_date = str(data["cob_date"].min().date())
        latest_date = str(data["cob_date"].max().date())

    validation_status = "VALIDATED" if not errors else "REJECTED"
    lineage = {
        "run_id": f"DEMO-RUN-{latest_date or 'UNKNOWN'}-{fingerprint[:8]}",
        "run_id_note": "Generated by the V12 demo adapter because the source CSV has no supplied run ID.",
        "source_file": path.name,
        "source_type": "CSV risk-engine export",
        "data_fingerprint": fingerprint,
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_status": validation_status,
        "approval_note": "Validation is a demo control and does not represent business approval.",
        "as_of_date": latest_date,
        "first_observation_date": earliest_date,
        "portfolio_count": int(data["portfolio_id"].nunique()) if "portfolio_id" in data else 0,
        "reporting_currencies": sorted(data["reporting_currency"].dropna().astype(str).unique().tolist())
        if "reporting_currency" in data
        else [],
        "row_count": int(len(data)),
        "column_count": int(len(data.columns)),
        "missing_value_count": missing_values,
        "duplicate_date_count": duplicate_dates,
        "invalid_date_count": invalid_dates,
    }
    return {
        "validation_status": validation_status,
        "errors": errors,
        "warnings": warnings,
        "data": data.sort_values("cob_date").reset_index(drop=True) if "cob_date" in data else data,
        "lineage": lineage,
    }

# ---- V12 implementation ----
"""Market Risk AI Assistant V12: validated risk-run lineage."""



VERSION = "V12"
def get_risk_run_lineage():
    """Return validation status and data lineage for the current demo risk run."""
    result = ingest_and_validate_risk_run(v8.FILE_NAME)
    return {
        "validation_status": result["validation_status"],
        "lineage": result["lineage"],
        "errors": result["errors"],
        "warnings": result["warnings"],
    }


# Register exactly one V12 agent-visible deterministic function.
v8.TOOL_FUNCTIONS["get_risk_run_lineage"] = get_risk_run_lineage
v8.TOOL_DESCRIPTIONS["get_risk_run_lineage"] = (
    "Validation status and lineage of the current demo risk-engine run, including "
    "its generated demo run ID, source file, data fingerprint, dates and scope."
)
v9.VERSION = VERSION
v9.SYSTEM_INSTRUCTION += """

V12 data-lineage control:
- get_risk_run_lineage is the source for run status and lineage facts.
- The run ID is generated by the demo adapter when the source file supplies no run ID.
- VALIDATED means the demo schema checks passed; it is not a business approval.
"""
v9.tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=name, description=description)
            for name, description in v8.TOOL_DESCRIPTIONS.items()
        ]
    )
]

ask_risk_agent = v9.ask_risk_agent


def main():
    print("\nMARKET RISK AI ASSISTANT — V12")
    print("Validated demo risk-run lineage is ready.")
    print("Type 'exit' to stop.\n")
    while True:
        question = input("You: ")
        if question.lower().strip() == "exit":
            print("Assistant: Goodbye.")
            break
        try:
            print("Assistant:")
            print(ask_risk_agent(question))
            print()
        except Exception as error:
            print(f"\nERROR:\n{error}\n")


if __name__ == "__main__":
    main()

# Snapshot this version.
v12 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V13 implementation ----
"""Market Risk AI Assistant V13: stress-scenario evolution."""

VERSION = "V13"
SUPPLIED_SCENARIOS = {
    "2008 Lehman crisis": "stress_2008_lehman_crisis",
    "2011 US downgrade": "stress_2011_us_downgrade",
    "2020 COVID liquidity": "stress_2020_covid_liquidity",
    "2022 rate hikes": "stress_2022_rate_hikes",
    "IR +100 bp": "stress_ir_up_100bp",
    "IR -100 bp": "stress_ir_down_100bp",
    "IR steepener": "stress_ir_steepener_50bp",
    "IR flattener": "stress_ir_flattener_50bp",
    "USD +10%": "stress_fx_usd_up_10pct",
    "Volatility +50%": "stress_vol_up_50pct",
}

# These are transparent combinations of supplied stress results, not repriced
# positions and not regulatory calibrations.  They exist solely as V13 demo
# scenarios inspired by published macro-financial risk themes.
ILLUSTRATIVE_SCENARIOS = {
    "Illustrative — geopolitical and trade fragmentation": {
        "weights": {"stress_2022_rate_hikes": 0.45, "stress_fx_usd_up_10pct": 0.30, "stress_vol_up_50pct": 0.25},
        "theme": "Geopolitical escalation, trade fragmentation and supply-chain disruption.",
    },
    "Illustrative — energy and commodity supply shock": {
        "weights": {"stress_2022_rate_hikes": 0.65, "stress_vol_up_50pct": 0.35},
        "theme": "Energy and commodity price shock with higher volatility.",
    },
    "Illustrative — sovereign spread and rate shock": {
        "weights": {"stress_2011_us_downgrade": 0.45, "stress_ir_up_100bp": 0.35, "stress_ir_steepener_50bp": 0.20},
        "theme": "Sovereign-risk repricing and adverse curve movement.",
    },
    "Illustrative — global liquidity and volatility shock": {
        "weights": {"stress_2020_covid_liquidity": 0.60, "stress_vol_up_50pct": 0.40},
        "theme": "Abrupt liquidity deterioration and volatility spike.",
    },
    "Illustrative — risk-assets correlation sell-off": {
        "weights": {"stress_2008_lehman_crisis": 0.60, "stress_2011_us_downgrade": 0.40},
        "theme": "Correlated equity and credit-risk sell-off.",
    },
    "Illustrative — USD funding and FX dislocation": {
        "weights": {"stress_fx_usd_up_10pct": 0.70, "stress_vol_up_50pct": 0.30},
        "theme": "USD funding pressure with FX and volatility dislocation.",
    },
}


def build_stress_evolution_frame():
    """Return the complete stress time series used by the V13 dashboard."""
    frame = v8.df[["cob_date"]].copy()
    metadata = {}
    for name, column in SUPPLIED_SCENARIOS.items():
        frame[name] = v8.df[column].astype(float)
        metadata[name] = {"source": "Risk-engine supplied", "theme": "Supplied stress scenario."}
    for name, definition in ILLUSTRATIVE_SCENARIOS.items():
        frame[name] = sum(v8.df[column].astype(float) * weight for column, weight in definition["weights"].items())
        metadata[name] = {"source": "Illustrative V13 proxy", "theme": definition["theme"]}
    return frame, metadata


def get_stress_evolution():
    """Return risk-engine and labelled illustrative stress paths through time."""
    frame, metadata = build_stress_evolution_frame()
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "observation_count": len(frame),
        "scenario_metadata": metadata,
        "series": {
            scenario: [
                {"date": str(row["cob_date"].date()), "impact": float(row[scenario])}
                for _, row in frame[["cob_date", scenario]].iterrows()
            ]
            for scenario in frame.columns
            if scenario != "cob_date"
        },
        "usage_note": (
            "Risk-engine supplied scenarios are deterministic inputs. Illustrative V13 scenarios are transparent "
            "weighted proxies of supplied stress results, not independent pricing-engine calculations or regulatory scenarios."
        ),
    }


# Register exactly one new V13 agent-visible deterministic function.
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = (
    "Stress-scenario time series, separating risk-engine supplied scenarios from labelled V13 illustrative proxies."
)
v9.VERSION = VERSION
v9.SYSTEM_INSTRUCTION += """

V13 stress control:
- get_stress_evolution is the source for stress paths over time.
- Clearly distinguish risk-engine supplied scenarios from illustrative V13 proxy scenarios.
- Do not call an illustrative proxy a regulatory scenario or pricing-engine result.
"""
v9.tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(name=name, description=description)
        for name, description in v8.TOOL_DESCRIPTIONS.items()
    ])
]

ask_risk_agent = v9.ask_risk_agent

# Snapshot this version.
v13 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V14 implementation ----
"""Market Risk AI Assistant V14: portfolio scope awareness."""

VERSION = "V14"
def get_portfolio_scope():
    """Return the portfolios present in the current risk-run extract."""
    scope = (
        v8.df.groupby("portfolio_id", dropna=False)
        .agg(observation_count=("cob_date", "size"), reporting_currency=("reporting_currency", "first"))
        .reset_index()
    )
    return {
        "portfolio_count": int(len(scope)),
        "portfolios": scope.to_dict(orient="records"),
        "usage_note": "Portfolio scope comes from the current risk-run extract; it is not a portfolio hierarchy service.",
    }


# Register exactly one new V14 agent-visible deterministic function.
v8.TOOL_FUNCTIONS["get_portfolio_scope"] = get_portfolio_scope
v8.TOOL_DESCRIPTIONS["get_portfolio_scope"] = (
    "Portfolio IDs, reporting currencies and observation counts present in the current risk-run extract."
)
v9.VERSION = VERSION
v9.SYSTEM_INSTRUCTION += """

V14 portfolio control:
- get_portfolio_scope reports only the portfolios present in the supplied risk-run extract.
- Do not infer a missing hierarchy, legal entity or booking structure.
"""
v9.tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(name=name, description=description)
        for name, description in v8.TOOL_DESCRIPTIONS.items()
    ])
]

ask_risk_agent = v9.ask_risk_agent

# Streamlit has no need for console diagnostics; redirecting them also avoids Windows code-page errors.
import contextlib
import io

def ask_risk_agent(question):
    with contextlib.redirect_stdout(io.StringIO()):
        return v13.ask_risk_agent(question)

# Snapshot this version.
v14 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- hierarchy helper ----
"""Synthetic trade hierarchy for V15.

This is a demo allocation structure, not trade-level pricing or a bank hierarchy.
"""

import pandas as pd


HIERARCHY = [
    ("Cross-asset", "Macro solutions", "XAS_MACRO", 0.18),
    ("Cross-asset", "Structured solutions", "XAS_STRUCT", 0.12),
    ("FX options", "G10 FX options", "FXO_G10", 0.16),
    ("FX options", "Emerging-market FX options", "FXO_EM", 0.08),
    ("IR linear", "EUR rates", "IRL_EUR", 0.14),
    ("IR linear", "USD rates", "IRL_USD", 0.10),
    ("IR non-linear", "Swaptions", "IRN_SWAPTION", 0.10),
    ("IR non-linear", "Exotics", "IRN_EXOTIC", 0.05),
    ("Equity", "Equity derivatives", "EQD_INDEX", 0.04),
    ("Equity", "Equity volatility", "EQD_VOL", 0.03),
]


def build_hierarchy():
    """Create business lines, desks, books and synthetic trade inventory."""
    rows = []
    trade_rows = []
    for business_line, desk, book_prefix, desk_weight in HIERARCHY:
        for book_number, book_share in enumerate((0.58, 0.42), start=1):
            book_id = f"{book_prefix}_BOOK_{book_number:02d}"
            book_weight = desk_weight * book_share
            rows.append({
                "business_line": business_line,
                "trading_desk": desk,
                "book_id": book_id,
                "allocation_weight": book_weight,
            })
            for trade_number, trade_share in enumerate((0.50, 0.30, 0.20), start=1):
                trade_rows.append({
                    "trade_id": f"{book_id}_T{trade_number:03d}",
                    "book_id": book_id,
                    "trading_desk": desk,
                    "business_line": business_line,
                    "product": f"{business_line} synthetic instrument {trade_number}",
                    "reporting_currency": "EUR",
                    "notional_eur": round(20_000_000 * book_weight * trade_share, 0),
                    "allocation_weight": book_weight * trade_share,
                })
    return pd.DataFrame(rows), pd.DataFrame(trade_rows)


def allocated_hierarchy_summary(current_risk: dict):
    """Allocate aggregate demo risk to hierarchy nodes for visual exploration."""
    books, _ = build_hierarchy()
    allocation_columns = {
        "allocated_historical_var": current_risk["var_hist"],
        "allocated_stressed_var": current_risk["stressed_var"],
        "allocated_expected_shortfall": current_risk["expected_shortfall"],
    }
    for column, total in allocation_columns.items():
        books[column] = books["allocation_weight"] * total
    return books

# ---- V15 implementation ----
"""Market Risk AI Assistant V15: trade-to-business-line hierarchy."""



VERSION = "V15"
v14.v9.VERSION = VERSION
def get_risk_hierarchy():
    """Return the synthetic V15 hierarchy and allocated risk summary."""
    books, trades = build_hierarchy()
    summary = allocated_hierarchy_summary(v8.get_current_risk())
    business_lines = summary.groupby("business_line", as_index=False).agg(
        trading_desks=("trading_desk", "nunique"),
        books=("book_id", "nunique"),
        allocated_historical_var=("allocated_historical_var", "sum"),
        allocated_stressed_var=("allocated_stressed_var", "sum"),
    )
    return {
        "business_lines": business_lines.to_dict(orient="records"),
        "trading_desk_count": int(books["trading_desk"].nunique()),
        "book_count": int(len(books)),
        "trade_count": int(len(trades)),
        "usage_note": (
            "V15 hierarchy and trade inventory are synthetic demo data. Risk amounts are transparent allocations "
            "of the aggregate risk-engine result, not trade-level revaluation or a VaR aggregation method."
        ),
    }


v8.TOOL_FUNCTIONS["get_risk_hierarchy"] = get_risk_hierarchy
v8.TOOL_DESCRIPTIONS["get_risk_hierarchy"] = (
    "Synthetic V15 trade-to-book-to-trading-desk-to-business-line hierarchy and allocated aggregate-risk summary."
)
v9.SYSTEM_INSTRUCTION += """

V15 hierarchy control:
- get_risk_hierarchy returns synthetic demo hierarchy and allocation data.
- Never state allocated amounts are trade-level revaluation or an additive VaR calculation.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v14.ask_risk_agent

# Snapshot this version.
v15 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V16 implementation ----
"""Market Risk AI Assistant V16: Greek sensitivity proxies."""

VERSION = "V16"
v15.v9.VERSION = VERSION
def get_greek_sensitivities():
    """Return current Greek-labelled P&L-driver proxies from the demo extract."""
    current = v8.df.iloc[-1]
    values = {
        "Delta": float(current["pnl_driver_fx_delta"]),
        "Gamma": float(current["pnl_driver_gamma"]),
        "Vega": float(current["pnl_driver_vega"]),
        "Theta": float(current["pnl_driver_theta"]),
    }
    return {
        "as_of_date": str(current["cob_date"].date()),
        "sensitivities": values,
        "usage_note": "These are P&L-driver proxies from the demo input, not independently calculated risk-engine Greek exposures.",
    }


v8.TOOL_FUNCTIONS["get_greek_sensitivities"] = get_greek_sensitivities
v8.TOOL_DESCRIPTIONS["get_greek_sensitivities"] = "Current Delta, Gamma, Vega and Theta P&L-driver proxies from the demo extract."
v9.SYSTEM_INSTRUCTION += """

V16 sensitivity control:
- get_greek_sensitivities returns demo P&L-driver proxies, not calibrated Greek exposures.
- State this limitation whenever discussing these values.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]
ask_risk_agent = v15.ask_risk_agent

# Snapshot this version.
v16 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V17 implementation ----
"""Market Risk AI Assistant V17: governed limits and corrected risk semantics."""

import pandas as pd

VERSION = "V17"
v16.v9.VERSION = VERSION
STRESS_SCENARIO_DEFINITIONS = {
    "2008 Lehman crisis": {"column": "stress_2008_lehman_crisis", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2008 Lehman market-shock set."},
    "2011 US downgrade": {"column": "stress_2011_us_downgrade", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2011 US downgrade market-shock set."},
    "2020 COVID liquidity": {"column": "stress_2020_covid_liquidity", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2020 COVID liquidity market-shock set."},
    "2022 rate hikes": {"column": "stress_2022_rate_hikes", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2022 rate-hike market-shock set."},
    "IR +100 bp": {"column": "stress_ir_up_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel +100 basis-point interest-rate shock."},
    "IR -100 bp": {"column": "stress_ir_down_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel -100 basis-point interest-rate shock."},
    "IR steepener 50 bp": {"column": "stress_ir_steepener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-steepening shock."},
    "IR flattener 50 bp": {"column": "stress_ir_flattener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-flattening shock."},
    "USD +10%": {"column": "stress_fx_usd_up_10pct", "type": "Hypothetical", "definition": "Portfolio revaluation after a supplied 10% strengthening shock to USD."},
    "Volatility +50%": {"column": "stress_vol_up_50pct", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50% volatility shock."},
}


def build_supplied_stress_frame(as_of_date=None):
    """Return only stress scenarios present in the supplied risk-engine extract."""
    source = v8.df
    if as_of_date is not None:
        source = source.loc[source["cob_date"] <= pd.Timestamp(as_of_date)]
    frame = source[["cob_date"]].copy()
    metadata = {}
    for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items():
        frame[scenario] = source[definition["column"]].astype(float)
        metadata[scenario] = {
            "source": "Risk-engine supplied",
            "type": definition["type"],
            "definition": definition["definition"],
        }
    return frame.reset_index(drop=True), metadata


def get_stress_evolution():
    """Return risk-engine-supplied stress P&L paths, excluding illustrative proxies."""
    frame, metadata = build_supplied_stress_frame()
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "observation_count": len(frame),
        "scenario_metadata": metadata,
        "series": {
            scenario: [
                {"date": str(row["cob_date"].date()), "impact": float(row[scenario])}
                for _, row in frame[["cob_date", scenario]].iterrows()
            ]
            for scenario in metadata
        },
        "usage_note": (
            "Stress values are risk-engine-supplied scenario revaluation P&L impacts in the reporting currency. "
            "Negative values are losses versus the base valuation. They are not first-order sensitivities."
        ),
    }


def get_market_sensitivities():
    """Return unit-aware synthetic sensitivities for the V17 demo feed."""
    current = v8.df.iloc[-1]
    rows = [
        ("IR Delta (DV01)", "EUR OIS curve", -128_000, "EUR / bp", "P&L change for a +1 bp parallel move in the named rate curve."),
        ("IR Delta (DV01)", "USD SOFR curve", 94_000, "EUR / bp", "P&L change for a +1 bp parallel move in the named rate curve."),
        ("IR Gamma", "EUR OIS curve", 1_850, "EUR / bp²", "Change in DV01 for a +1 bp move in the named rate curve."),
        ("FX Delta", "EUR/USD spot", 410_000, "EUR / 1% spot", "P&L change for a +1% move in the named FX spot rate."),
        ("Vega", "EUR swaption volatility", -63_000, "EUR / vol point", "P&L change for a +1 percentage-point move in implied volatility."),
        ("Vega", "EUR/USD implied volatility", 48_000, "EUR / vol point", "P&L change for a +1 percentage-point move in implied volatility."),
        ("Theta", "Whole portfolio", -19_000, "EUR / day", "Expected one-business-day P&L from time decay, holding market inputs constant."),
    ]
    return {
        "as_of_date": str(current["cob_date"].date()),
        "sensitivities": [
            {"measure": measure, "underlying": underlying, "value": float(value), "unit": unit, "definition": definition}
            for measure, underlying, value, unit, definition in rows
        ],
        "usage_note": (
            "Unit-aware synthetic sensitivity feed for the V17 prototype. These values are separate from "
            "P&L-explain drivers and must be replaced by risk-engine sensitivity records in production."
        ),
    }


def evaluate_limit_breaches():
    """Evaluate the configured VaR limit and return governance status."""
    current = v8.get_current_risk()
    utilization = float(current["limit_utilisation"])
    if utilization >= 100:
        status = "CRITICAL"
        escalation = "Immediate escalation required"
    elif utilization >= 80:
        status = "WARNING"
        escalation = "Owner review required"
    else:
        status = "OK"
        escalation = "No escalation"
    return {
        "as_of_date": current["date"],
        "limits": [{
            "limit_name": "Historical VaR (1 day, 99%)",
            "exposure": current["var_hist"],
            "limit": current["var_limit"],
            "utilization_pct": utilization,
            "warning_threshold_pct": 80.0,
            "critical_threshold_pct": 100.0,
            "status": status,
            "owner": "Market Risk",
            "escalation_status": escalation,
        }],
    }


v8.TOOL_FUNCTIONS.pop("get_greek_sensitivities", None)
v8.TOOL_DESCRIPTIONS.pop("get_greek_sensitivities", None)
v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Unit-aware market sensitivities from the separate V17 demo sensitivity feed."
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = "Risk-engine-supplied stress scenario revaluation P&L paths only."
v8.TOOL_FUNCTIONS["evaluate_limit_breaches"] = evaluate_limit_breaches
v8.TOOL_DESCRIPTIONS["evaluate_limit_breaches"] = "Configured VaR limit status, thresholds, owner and escalation state."

v9.SYSTEM_INSTRUCTION += """

V17 risk semantics and governance:
- Stress results are scenario revaluation P&L impacts; negative values are losses. Never describe them as sensitivities.
- Use get_market_sensitivities for unit-aware Greeks. IR Delta is DV01 in reporting currency per 1 bp.
- The V17 sensitivity values are synthetic demo-feed records and are separate from P&L-explain drivers.
- Use evaluate_limit_breaches for limit status, ownership and escalation.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v16.ask_risk_agent

# Snapshot this version.
v17 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V18 implementation ----
"""M.R. AI Agent V18: multi-metric limit governance."""

VERSION = "V18"
v17.v9.VERSION = VERSION
build_supplied_stress_frame = v17.build_supplied_stress_frame
get_market_sensitivities = v17.get_market_sensitivities
get_stress_evolution = v17.get_stress_evolution

WARNING_THRESHOLD_PCT = 80.0
BREACH_THRESHOLD_PCT = 100.0


def _limit_record(family, metric, exposure, limit, unit, owner, basis):
    consumption = 0.0 if limit == 0 else float(exposure) / float(limit) * 100.0
    if consumption >= BREACH_THRESHOLD_PCT:
        status = "BREACH"
        escalation = "Immediate escalation required"
    elif consumption >= WARNING_THRESHOLD_PCT:
        status = "WARNING"
        escalation = "Owner review required"
    else:
        status = "OK"
        escalation = "No escalation"
    return {
        "family": family,
        "metric": metric,
        "exposure": float(exposure),
        "limit": float(limit),
        "unit": unit,
        "consumption_pct": consumption,
        "warning_threshold_pct": WARNING_THRESHOLD_PCT,
        "breach_threshold_pct": BREACH_THRESHOLD_PCT,
        "status": status,
        "owner": owner,
        "consumption_basis": basis,
        "escalation_status": escalation,
    }


def evaluate_all_limits():
    """Evaluate the principal V18 market-risk limit families."""
    current = v8.get_current_risk()
    row = v8.df.iloc[-1]
    stress_frame, _ = v17.build_supplied_stress_frame()
    worst_stress_loss = abs(min(0.0, float(stress_frame.iloc[-1].drop(labels="cob_date").min())))

    sensitivity_rows = v17.get_market_sensitivities()["sensitivities"]
    gross_ir_dv01 = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "IR Delta (DV01)")
    ir_gamma = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "IR Gamma")
    fx_delta = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "FX Delta")
    gross_vega = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "Vega")

    limits = [
        _limit_record("VaR", "Historical VaR (1 day, 99%)", current["var_hist"], current["var_limit"], "EUR", "Market Risk", "Current exposure"),
        _limit_record("VaR", "Stressed VaR (1 day, 99%)", current["stressed_var"], 10_000_000, "EUR", "Market Risk", "Current exposure"),
        _limit_record("Stress", "Worst supplied scenario loss", worst_stress_loss, 15_000_000, "EUR loss", "Stress Testing", "Absolute loss"),
        _limit_record("Sensitivity", "Gross IR Delta (DV01)", gross_ir_dv01, 250_000, "EUR / bp", "Rates Risk", "Gross absolute sensitivity"),
        _limit_record("Sensitivity", "IR Gamma", ir_gamma, 5_000, "EUR / bp²", "Rates Risk", "Absolute sensitivity"),
        _limit_record("Sensitivity", "Gross FX Delta", fx_delta, 500_000, "EUR / 1% spot", "FX Risk", "Gross absolute sensitivity"),
        _limit_record("Sensitivity", "Gross Vega", gross_vega, 150_000, "EUR / vol point", "Volatility Risk", "Gross absolute sensitivity"),
        _limit_record("P&L", "Daily actual loss", max(0.0, -float(row["actual_pnl"])), 1_000_000, "EUR loss", "P&L Control", "Loss only"),
        _limit_record("P&L", "Absolute unexplained P&L", abs(float(row["unexplained_pnl"])), 250_000, "EUR", "P&L Control", "Absolute amount"),
        _limit_record("Backtesting", "250-day exceptions", float(row["backtest_exception_count_250d"]), 4.0, "Exceptions", "Market Risk", "Exception count"),
    ]
    return {
        "as_of_date": current["date"],
        "warning_threshold_pct": WARNING_THRESHOLD_PCT,
        "breach_threshold_pct": BREACH_THRESHOLD_PCT,
        "summary": {
            "breaches": sum(item["status"] == "BREACH" for item in limits),
            "warnings": sum(item["status"] == "WARNING" for item in limits),
            "ok": sum(item["status"] == "OK" for item in limits),
        },
        "limits": limits,
        "usage_note": (
            "V18 demo limits cover the principal supplied metrics. Limits and owners are configurable prototype values, "
            "not approved production mandates."
        ),
    }


v8.TOOL_FUNCTIONS.pop("evaluate_limit_breaches", None)
v8.TOOL_DESCRIPTIONS.pop("evaluate_limit_breaches", None)
v8.TOOL_FUNCTIONS["evaluate_all_limits"] = evaluate_all_limits
v8.TOOL_DESCRIPTIONS["evaluate_all_limits"] = (
    "Multi-metric market-risk limits with 80% warning, 100% breach, owners and escalation status."
)
v9.SYSTEM_INSTRUCTION += """

V18 limit governance:
- Use evaluate_all_limits for VaR, SVaR, stress, sensitivity, P&L and backtesting controls.
- Consumption below 80% is OK; 80% to below 100% is WARNING; 100% or above is BREACH.
- State that V18 thresholds and owners are configurable demo values, not approved production mandates.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v17.ask_risk_agent

# Snapshot this version.
v18 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V19 implementation ----
"""M.R. AI Agent V19: FRTB P&L attribution and desk-level PLA testing."""

import numpy as np
import pandas as pd

VERSION = "V19"
v18.v9.VERSION = VERSION
build_supplied_stress_frame = v18.build_supplied_stress_frame
get_market_sensitivities = v18.get_market_sensitivities
get_stress_evolution = v18.get_stress_evolution
evaluate_all_limits = v18.evaluate_all_limits

PLA_OBSERVATIONS = 250
PLA_GREEN_CORRELATION = 0.80
PLA_RED_CORRELATION = 0.70
PLA_GREEN_KS = 0.09
PLA_RED_KS = 0.12
DRIVER_COLUMNS = [
    "Rates",
    "FX",
    "Credit",
    "Equity",
    "Vega",
    "Theta",
    "Gamma and cross-gamma",
]


def _empirical_ks_statistic(first, second):
    """Return the two-sample empirical Kolmogorov-Smirnov distance."""
    first_sorted = np.sort(np.asarray(first, dtype=float))
    second_sorted = np.sort(np.asarray(second, dtype=float))
    combined = np.sort(np.concatenate([first_sorted, second_sorted]))
    first_cdf = np.searchsorted(first_sorted, combined, side="right") / len(first_sorted)
    second_cdf = np.searchsorted(second_sorted, combined, side="right") / len(second_sorted)
    return float(np.max(np.abs(first_cdf - second_cdf)))


def _pla_zone(correlation, ks_statistic):
    if correlation > PLA_GREEN_CORRELATION and ks_statistic < PLA_GREEN_KS:
        return "GREEN"
    if correlation < PLA_RED_CORRELATION or ks_statistic > PLA_RED_KS:
        return "RED"
    return "AMBER"


def _zone_consequence(zone):
    return {
        "GREEN": "IMA eligible",
        "AMBER": "IMA eligible with capital surcharge",
        "RED": "IMA ineligible; Standardised Approach required",
    }[zone]


def build_pla_demo_history():
    """Build a deterministic, synthetic 250-business-day desk-level PLA feed."""
    books, _ = v15.build_hierarchy()
    desks = (
        books.groupby(["business_line", "trading_desk"], as_index=False)["allocation_weight"]
        .sum()
        .sort_values(["business_line", "trading_desk"])
        .reset_index(drop=True)
    )
    end_date = v8.df["cob_date"].max()
    dates = pd.bdate_range(end=end_date, periods=PLA_OBSERVATIONS)
    rng = np.random.default_rng(19019)
    current = v8.df.iloc[-1]
    rows = []

    for desk_index, desk in desks.iterrows():
        weight = float(desk["allocation_weight"])
        scale = 1_700_000 * max(weight, 0.04)
        market_component = rng.normal(0, scale, PLA_OBSERVATIONS)
        desk_component = rng.normal(0, scale * 0.35, PLA_OBSERVATIONS)
        hpl = market_component + desk_component

        if desk_index < 6:
            rtpl = hpl * rng.normal(1.0, 0.015, PLA_OBSERVATIONS) + rng.normal(0, scale * 0.09, PLA_OBSERVATIONS)
        elif desk_index < 9:
            rtpl = hpl * 0.82 + rng.normal(0, scale * 0.32, PLA_OBSERVATIONS) + scale * 0.08
        else:
            rtpl = hpl * 0.45 + rng.normal(0, scale * 0.85, PLA_OBSERVATIONS) + scale * 0.18

        apl = hpl + rng.normal(0, scale * 0.22, PLA_OBSERVATIONS)

        hpl[-1] = float(current["hypothetical_pnl"]) * weight
        apl[-1] = float(current["actual_pnl"]) * weight
        latest_model_gap = (0.025 + desk_index * 0.006) * scale
        rtpl[-1] = hpl[-1] - latest_model_gap

        driver_weights = np.array([0.28, 0.23, 0.10, 0.08, 0.14, 0.07, 0.10])
        if "FX" in desk["business_line"]:
            driver_weights = np.array([0.10, 0.44, 0.06, 0.04, 0.20, 0.06, 0.10])
        elif "IR" in desk["business_line"]:
            driver_weights = np.array([0.49, 0.08, 0.06, 0.02, 0.19, 0.07, 0.09])
        elif "Equity" in desk["business_line"]:
            driver_weights = np.array([0.06, 0.08, 0.05, 0.43, 0.23, 0.05, 0.10])

        driver_weights = driver_weights * 0.94

        for observation, cob_date in enumerate(dates):
            driver_values = rtpl[observation] * driver_weights
            row = {
                "cob_date": cob_date,
                "business_line": desk["business_line"],
                "trading_desk": desk["trading_desk"],
                "actual_pnl": float(apl[observation]),
                "hypothetical_pnl": float(hpl[observation]),
                "risk_theoretical_pnl": float(rtpl[observation]),
                "apl_hpl_difference": float(apl[observation] - hpl[observation]),
                "hpl_rtpl_difference": float(hpl[observation] - rtpl[observation]),
                "explained_pnl": float(driver_values.sum()),
                "unexplained_pnl": float(rtpl[observation] - driver_values.sum()),
                "data_classification": "Deterministic synthetic V19 PLA demo",
            }
            row.update({name: float(value) for name, value in zip(DRIVER_COLUMNS, driver_values)})
            rows.append(row)

    return pd.DataFrame(rows)


def evaluate_pla_test():
    """Evaluate Basel PLA statistics for every synthetic demo trading desk."""
    history = build_pla_demo_history()
    results = []
    for desk_name, desk_history in history.groupby("trading_desk", sort=True):
        correlation = float(
            desk_history["hypothetical_pnl"].rank(method="average").corr(
                desk_history["risk_theoretical_pnl"].rank(method="average")
            )
        )
        ks_statistic = _empirical_ks_statistic(
            desk_history["hypothetical_pnl"],
            desk_history["risk_theoretical_pnl"],
        )
        zone = _pla_zone(correlation, ks_statistic)
        latest = desk_history.iloc[-1]
        results.append({
            "business_line": latest["business_line"],
            "trading_desk": desk_name,
            "observations": len(desk_history),
            "spearman_correlation": correlation,
            "ks_statistic": ks_statistic,
            "pla_zone": zone,
            "regulatory_consequence": _zone_consequence(zone),
            "latest_hpl": float(latest["hypothetical_pnl"]),
            "latest_rtpl": float(latest["risk_theoretical_pnl"]),
            "latest_pla_residual": float(latest["hpl_rtpl_difference"]),
        })
    return {
        "as_of_date": str(history["cob_date"].max().date()),
        "required_observations": PLA_OBSERVATIONS,
        "thresholds": {
            "green": {"spearman_above": PLA_GREEN_CORRELATION, "ks_below": PLA_GREEN_KS},
            "red": {"spearman_below": PLA_RED_CORRELATION, "ks_above": PLA_RED_KS},
            "otherwise": "AMBER",
        },
        "desk_results": results,
        "usage_note": (
            "The PLA methodology and thresholds follow the Basel framework. The 250-day desk history is "
            "deterministic synthetic V19 demo data, not a regulatory submission or IMA eligibility decision."
        ),
    }


v8.TOOL_FUNCTIONS["evaluate_pla_test"] = evaluate_pla_test
v8.TOOL_DESCRIPTIONS["evaluate_pla_test"] = (
    "Basel-style 250-day desk-level HPL-versus-RTPL PLA results, zones and consequences using labelled synthetic demo history."
)
v9.SYSTEM_INSTRUCTION += """

V19 P&L attribution control:
- Use official terminology: Actual P&L (APL), Hypothetical P&L (HPL), and Risk-theoretical P&L (RTPL).
- PLA compares HPL with RTPL over 250 trading days using Spearman rank correlation and the empirical KS statistic.
- Do not use APL in the PLA test; APL and HPL are used for backtesting.
- Keep the HPL-minus-RTPL PLA residual separate from internal driver-level unexplained P&L.
- Always state that the V19 desk history is deterministic synthetic demo data and does not establish regulatory eligibility.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v18.ask_risk_agent

# Snapshot this version.
v19 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V20 implementation ----
"""M.R. AI Agent V20: richer sensitivities, P&L flags, and consolidated controls."""

import pandas as pd

VERSION = "V20"
v19.v9.VERSION = VERSION
DRIVER_COLUMNS = v19.DRIVER_COLUMNS
build_pla_demo_history = v19.build_pla_demo_history
evaluate_pla_test = v19.evaluate_pla_test
evaluate_all_limits = v19.evaluate_all_limits

UNEXPLAINED_APL_ALERT_THRESHOLD_PCT = 20.0

STRESS_SCENARIO_DEFINITIONS = {
    "2008 Lehman": {"column": "stress_2008_lehman_crisis", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2008 Lehman market-shock set."},
    "2011 US downgrade": {"column": "stress_2011_us_downgrade", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2011 US downgrade market-shock set."},
    "2020 COVID": {"column": "stress_2020_covid_liquidity", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2020 COVID liquidity market-shock set."},
    "2022 rate hikes": {"column": "stress_2022_rate_hikes", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2022 rate-hike market-shock set."},
    "IR +100 bp": {"column": "stress_ir_up_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel +100 basis-point interest-rate shock."},
    "IR -100 bp": {"column": "stress_ir_down_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel -100 basis-point interest-rate shock."},
    "IR steepener": {"column": "stress_ir_steepener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-steepening shock."},
    "IR flattener": {"column": "stress_ir_flattener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-flattening shock."},
    "USD +10%": {"column": "stress_fx_usd_up_10pct", "type": "Hypothetical", "definition": "Portfolio revaluation after a supplied 10% strengthening shock to USD."},
    "Vol +50%": {"column": "stress_vol_up_50pct", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50% volatility shock."},
}

RATE_CURVES = [
    ("EUR", "OIS", "€STR OIS", -85_000, 1_350, -28_000),
    ("EUR", "BOR", "Euribor 3M", -28_000, 420, -15_000),
    ("EUR", "BOR", "Euribor 6M", -15_000, 260, -9_000),
    ("USD", "OIS", "SOFR OIS", 72_000, 1_050, 21_000),
    ("USD", "BOR", "USD 3M projection", 22_000, 380, 12_000),
    ("USD", "BOR", "USD 6M projection", 12_000, 210, 7_000),
    ("JPY", "OIS", "TONAR OIS", -24_000, 310, -6_000),
    ("JPY", "BOR", "TIBOR 3M", -11_000, 170, -4_000),
    ("JPY", "BOR", "TIBOR 6M", -7_000, 110, -2_000),
    ("GBP", "OIS", "SONIA OIS", 31_000, 460, 9_000),
    ("GBP", "BOR", "GBP 3M projection", 13_000, 190, 5_000),
    ("GBP", "BOR", "GBP 6M projection", 8_000, 120, 3_000),
]

FX_DELTAS = [
    ("EUR/USD", 410_000),
    ("USD/JPY", -180_000),
    ("GBP/USD", 215_000),
]


def build_pla_demo_history():
    """Return V19 PLA history with varied synthetic driver-coverage quality."""
    history = v19.build_pla_demo_history().copy()
    coverage_targets = {
        "Exotics": 0.48,
        "Swaptions": 0.50,
        "Equity volatility": 0.76,
    }
    for desk, target_coverage in coverage_targets.items():
        mask = history["trading_desk"] == desk
        current_explained = history.loc[mask, DRIVER_COLUMNS].sum(axis=1)
        current_coverage = current_explained / history.loc[mask, "risk_theoretical_pnl"].replace(0, pd.NA)
        scaling = (target_coverage / current_coverage).fillna(1.0)
        history.loc[mask, DRIVER_COLUMNS] = history.loc[mask, DRIVER_COLUMNS].mul(scaling, axis=0)
    history["explained_pnl"] = history[DRIVER_COLUMNS].sum(axis=1)
    history["unexplained_pnl"] = history["risk_theoretical_pnl"] - history["explained_pnl"]
    return history

def build_supplied_stress_frame(as_of_date=None):
    """Return the unchanged supplied scenarios with shorter V20 display names."""
    source = v8.df
    if as_of_date is not None:
        source = source.loc[source["cob_date"] <= pd.Timestamp(as_of_date)]
    frame = source[["cob_date"]].copy()
    metadata = {}
    for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items():
        frame[scenario] = source[definition["column"]].astype(float)
        metadata[scenario] = {
            "source": "Risk-engine supplied",
            "type": definition["type"],
            "definition": definition["definition"],
        }
    return frame.reset_index(drop=True), metadata


def get_stress_evolution():
    """Return unchanged risk-engine-supplied stress values with shorter labels."""
    frame, metadata = build_supplied_stress_frame()
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "observation_count": len(frame),
        "scenario_metadata": metadata,
        "series": {
            scenario: [
                {"date": str(row["cob_date"].date()), "impact": float(row[scenario])}
                for _, row in frame[["cob_date", scenario]].iterrows()
            ]
            for scenario in metadata
        },
        "usage_note": (
            "Stress values and scenario shocks are unchanged from V19; V20 shortens display names only. "
            "Values are supplied scenario revaluation P&L in the reporting currency."
        ),
    }


def get_market_sensitivities():
    """Return unit-aware synthetic rates and FX sensitivities by currency and curve."""
    current = v8.df.iloc[-1]
    rows = []
    for currency, curve_type, curve, dv01, gamma, vega in RATE_CURVES:
        rows.extend([
            {
                "risk_class": "Rates",
                "measure": "IR Delta (DV01)",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(dv01),
                "unit": "EUR / bp",
                "definition": "P&L change for a +1 bp move in the named curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "IR Gamma",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(gamma),
                "unit": "EUR / bp²",
                "definition": "Change in curve DV01 for a +1 bp move in the named curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "Vega",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(vega),
                "unit": "EUR / vol point",
                "definition": "P&L change for a +1 percentage-point move in implied volatility.",
            },
        ])
    for pair, delta in FX_DELTAS:
        rows.append({
            "risk_class": "FX",
            "measure": "FX Delta",
            "currency": pair,
            "curve_type": "Spot",
            "curve": pair,
            "value": float(delta),
            "unit": "EUR / 1% spot",
            "definition": "P&L change for a +1% move in the quoted FX pair.",
        })
    rows.append({
        "risk_class": "Time",
        "measure": "Theta",
        "currency": "All",
        "curve_type": "Portfolio",
        "curve": "Whole portfolio",
        "value": -19_000.0,
        "unit": "EUR / day",
        "definition": "Expected one-business-day P&L from time decay, holding market inputs constant.",
    })
    return {
        "as_of_date": str(current["cob_date"].date()),
        "currencies": ["EUR", "USD", "JPY", "GBP"],
        "sensitivities": rows,
        "usage_note": (
            "Unit-aware deterministic synthetic V20 sensitivity feed. Rates are split by EUR, USD, JPY and GBP "
            "OIS/BOR curves; FX Delta covers each non-USD currency versus USD. Replace with risk-engine records in production."
        ),
    }


def evaluate_pnl_explain_alerts():
    """Flag desks where absolute driver-unexplained P&L exceeds 20% of absolute APL."""
    history = build_pla_demo_history()
    latest = history.sort_values("cob_date").groupby("trading_desk", as_index=False).tail(1)
    alerts = []
    for _, row in latest.iterrows():
        apl_magnitude = abs(float(row["actual_pnl"]))
        unexplained_magnitude = abs(float(row["unexplained_pnl"]))
        ratio = float("inf") if apl_magnitude == 0 and unexplained_magnitude > 0 else (
            0.0 if apl_magnitude == 0 else unexplained_magnitude / apl_magnitude * 100.0
        )
        flagged = ratio > UNEXPLAINED_APL_ALERT_THRESHOLD_PCT
        alerts.append({
            "business_line": row["business_line"],
            "trading_desk": row["trading_desk"],
            "actual_pnl": float(row["actual_pnl"]),
            "unexplained_pnl": float(row["unexplained_pnl"]),
            "unexplained_to_apl_pct": ratio,
            "threshold_pct": UNEXPLAINED_APL_ALERT_THRESHOLD_PCT,
            "status": "ALERT" if flagged else "OK",
        })
    return {
        "as_of_date": str(latest["cob_date"].max().date()),
        "threshold_pct": UNEXPLAINED_APL_ALERT_THRESHOLD_PCT,
        "flagged_count": sum(item["status"] == "ALERT" for item in alerts),
        "desk_results": alerts,
        "usage_note": (
            "V20 demo control flags |driver-unexplained P&L| / |APL| above 20%. "
            "The threshold and desk history are synthetic prototype governance inputs."
        ),
    }


v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Rates sensitivities by EUR, USD, JPY and GBP OIS/BOR curves plus FX Delta for USD pairs."
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = "Unchanged supplied stress scenario values with shorter V20 display labels."
v8.TOOL_FUNCTIONS["evaluate_pnl_explain_alerts"] = evaluate_pnl_explain_alerts
v8.TOOL_DESCRIPTIONS["evaluate_pnl_explain_alerts"] = "Desk flags where absolute unexplained P&L exceeds 20% of absolute APL."

v9.SYSTEM_INSTRUCTION += """

V20 dashboard controls:
- Use evaluate_pnl_explain_alerts for the 20% unexplained-to-APL control.
- Sensitivities are split by currency and OIS/BOR curve and remain deterministic synthetic demo values.
- Stress scenario values and shocks are unchanged; only display names are shortened.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v19.ask_risk_agent

# Snapshot this version.
v20 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V21 implementation ----
"""M.R. AI Agent V21: material stress selection and dedicated sensitivity views."""

import pandas as pd


VERSION = "V21"
v20.v9.VERSION = VERSION
DRIVER_COLUMNS = v20.DRIVER_COLUMNS
build_pla_demo_history = v20.build_pla_demo_history
evaluate_pla_test = v20.evaluate_pla_test
evaluate_all_limits = v20.evaluate_all_limits
evaluate_pnl_explain_alerts = v20.evaluate_pnl_explain_alerts

STRESS_SCENARIO_DEFINITIONS = {
    "2008 Lehman": {"column": "stress_2008_lehman_crisis", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2008 Lehman market-shock set."},
    "2011 US downgrade": {"column": "stress_2011_us_downgrade", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2011 US downgrade market-shock set."},
    "2020 COVID": {"column": "stress_2020_covid_liquidity", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2020 COVID liquidity market-shock set."},
    "2022 rate hikes": {"column": "stress_2022_rate_hikes", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2022 rate-hike market-shock set."},
    "IR steepener": {"column": "stress_ir_steepener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-steepening shock."},
    "IR flattener": {"column": "stress_ir_flattener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-flattening shock."},
    "IR +100 bp": {"column": "stress_ir_up_100bp", "type": "Adverse", "definition": "Portfolio revaluation after a parallel +100 basis-point interest-rate shock."},
    "IR -100 bp": {"column": "stress_ir_down_100bp", "type": "Adverse", "definition": "Portfolio revaluation after a parallel -100 basis-point interest-rate shock."},
    "USD +10%": {"column": "stress_fx_usd_up_10pct", "type": "Adverse", "definition": "Portfolio revaluation after a supplied 10% strengthening shock to USD."},
    "Vol +50%": {"column": "stress_vol_up_50pct", "type": "Adverse", "definition": "Portfolio revaluation under the supplied 50% volatility shock."},
}

EXTREME_SCENARIO_CONFIGURATIONS = [
    {"scenario": "IR +200 bp", "category": "Extreme", "shock": "+200 bp parallel rates", "derived_from": "IR +100 bp"},
    {"scenario": "IR -200 bp", "category": "Extreme", "shock": "-200 bp parallel rates", "derived_from": "IR -100 bp"},
    {"scenario": "USD +20%", "category": "Extreme", "shock": "+20% USD", "derived_from": "USD +10%"},
    {"scenario": "Vol +100%", "category": "Extreme", "shock": "+100% volatility", "derived_from": "Vol +50%"},
]

THETA_BY_CURRENCY = {"EUR": -8_000.0, "USD": -6_000.0, "JPY": -2_000.0, "GBP": -3_000.0}


def build_supplied_stress_frame(as_of_date=None):
    """Return unchanged priced scenarios with V21 governance categories."""
    source = v8.df
    if as_of_date is not None:
        source = source.loc[source["cob_date"] <= pd.Timestamp(as_of_date)]
    frame = source[["cob_date"]].copy()
    metadata = {}
    for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items():
        frame[scenario] = source[definition["column"]].astype(float)
        metadata[scenario] = {
            "source": "Risk-engine supplied",
            "type": definition["type"],
            "definition": definition["definition"],
        }
    return frame.reset_index(drop=True), metadata


def get_stress_scenario_catalog():
    """Return governed definitions without manufacturing extreme P&L."""
    rows = [
        {
            "scenario": scenario,
            "category": definition["type"],
            "shock": definition["definition"],
            "pricing_status": "Priced by supplied risk-engine feed",
            "derived_from": "",
        }
        for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items()
    ]
    rows.extend(
        {**configuration, "pricing_status": "Awaiting risk-engine revaluation"}
        for configuration in EXTREME_SCENARIO_CONFIGURATIONS
    )
    return rows


def get_stress_evolution():
    """Return supplied stress values and the governed V21 taxonomy."""
    frame, metadata = build_supplied_stress_frame()
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "observation_count": len(frame),
        "scenario_metadata": metadata,
        "series": {
            scenario: [
                {"date": str(row["cob_date"].date()), "impact": float(row[scenario])}
                for _, row in frame[["cob_date", scenario]].iterrows()
            ]
            for scenario in metadata
        },
        "usage_note": (
            "Curves show risk-engine-supplied revaluation P&L only. Historical scenarios replay observed periods; "
            "hypothetical scenarios reshape selected factors; adverse scenarios are severe calibrated shocks. "
            "Extreme shock parameters are twice their adverse counterparts and remain unpriced until revaluation."
        ),
    }


def get_material_stress_scenarios(as_of_date=None, maximum_scenarios=6):
    """Select material priced curves from latest magnitude and latest jump."""
    frame, metadata = build_supplied_stress_frame(as_of_date)
    if frame.empty:
        return {"selected_scenarios": [], "scenario_metrics": [], "rule": "No observations available."}
    latest = frame.iloc[-1].drop(labels="cob_date").astype(float)
    previous = frame.iloc[-2].drop(labels="cob_date").astype(float) if len(frame) > 1 else latest
    metrics = pd.DataFrame({
        "scenario": latest.index,
        "latest_impact": latest.values,
        "latest_jump": (latest - previous).values,
    })
    max_magnitude = max(float(metrics["latest_impact"].abs().max()), 1.0)
    max_jump = max(float(metrics["latest_jump"].abs().max()), 1.0)
    metrics["magnitude_score"] = metrics["latest_impact"].abs() / max_magnitude
    metrics["jump_score"] = metrics["latest_jump"].abs() / max_jump
    metrics["materiality_score"] = metrics[["magnitude_score", "jump_score"]].max(axis=1)
    metrics["category"] = metrics["scenario"].map(lambda name: metadata[name]["type"])
    metrics["selection_reason"] = metrics.apply(
        lambda row: "Large magnitude and jump"
        if row["magnitude_score"] >= 0.60 and row["jump_score"] >= 0.60
        else ("Large current magnitude" if row["magnitude_score"] >= row["jump_score"] else "Large latest jump"),
        axis=1,
    )
    material = metrics.loc[
        (metrics["magnitude_score"] >= 0.60) | (metrics["jump_score"] >= 0.60)
    ].sort_values("materiality_score", ascending=False)
    minimum = min(3, len(metrics))
    if len(material) < minimum:
        material = metrics.nlargest(minimum, "materiality_score")
    material = material.head(maximum_scenarios)
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "selected_scenarios": material["scenario"].tolist(),
        "scenario_metrics": material.to_dict("records"),
        "rule": "Select curves at or above 60% of the largest current absolute impact or latest absolute jump; show at least three and at most six.",
    }


def get_market_sensitivities():
    """Return the V20 feed with Theta split across major currencies."""
    result = v20.get_market_sensitivities()
    rows = [row for row in result["sensitivities"] if row["measure"] != "Theta"]
    for currency, theta in THETA_BY_CURRENCY.items():
        rows.append({
            "risk_class": "Time",
            "measure": "Theta",
            "currency": currency,
            "curve_type": "Portfolio",
            "curve": f"{currency} portfolio",
            "value": theta,
            "unit": "EUR / day",
            "definition": "Expected one-business-day P&L from time decay, holding market inputs constant.",
        })
    return {
        **result,
        "sensitivities": rows,
        "usage_note": (
            "Unit-aware deterministic synthetic V21 sensitivity feed. Rates are split by EUR, USD, JPY and GBP "
            "OIS/BOR curves; FX Delta covers each non-USD currency versus USD. Replace with risk-engine records in production."
        ),
    }


v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "IR Delta, IR Gamma, IR Vega, FX Delta and Theta by major currency and curve family."
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = "Priced stress evolution with governed Historical, Hypothetical, Adverse and Extreme categories."
v8.TOOL_FUNCTIONS["get_material_stress_scenarios"] = get_material_stress_scenarios
v8.TOOL_DESCRIPTIONS["get_material_stress_scenarios"] = "Material priced stress curves selected by current magnitude and latest jump."
v8.TOOL_FUNCTIONS["evaluate_pnl_explain_alerts"] = evaluate_pnl_explain_alerts
v8.TOOL_DESCRIPTIONS["evaluate_pnl_explain_alerts"] = "Desk flags where absolute unexplained P&L exceeds 20% of absolute APL."

v9.SYSTEM_INSTRUCTION += """

V21 dashboard controls:
- Use evaluate_pnl_explain_alerts for the 20% unexplained-to-APL control.
- Use get_material_stress_scenarios to focus the chart on large current impacts or latest jumps.
- Sensitivities use five distinct views: IR Delta, IR Gamma, IR Vega, FX Delta and Theta.
- Extreme shock parameters are twice the corresponding adverse shock, but have no P&L until risk-engine revaluation. Never double adverse P&L as a proxy.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v20.ask_risk_agent

# Snapshot this version.
v21 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V22 implementation ----
"""M.R. AI Agent V22: deterministic run comparison and expanded governed risk sets."""

import re

import pandas as pd


VERSION = "V22"
v21.v9.VERSION = VERSION
DRIVER_COLUMNS = v21.DRIVER_COLUMNS
build_pla_demo_history = v21.build_pla_demo_history
evaluate_pla_test = v21.evaluate_pla_test
evaluate_all_limits = v21.evaluate_all_limits
evaluate_pnl_explain_alerts = v21.evaluate_pnl_explain_alerts
build_supplied_stress_frame = v21.build_supplied_stress_frame
get_stress_evolution = v21.get_stress_evolution
get_material_stress_scenarios = v21.get_material_stress_scenarios

INFLATION_CURVES = [
    ("EUR", "EUR HICPxT", -12_000, 155, -4_200),
    ("USD", "USD CPI", 9_500, 130, 3_600),
    ("JPY", "JPY CPI", -3_800, 55, -1_100),
    ("GBP", "GBP RPI", 7_200, 95, 2_500),
]

ADDITIONAL_STRESS_CONFIGURATIONS = [
    {"scenario": "Credit +150 bp", "category": "Adverse", "shock": "+150 bp parallel credit-spread widening", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Equity -30%", "category": "Adverse", "shock": "-30% global equity spot", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "EUR/USD -15%", "category": "Adverse", "shock": "-15% EUR/USD spot", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Basis +50 bp", "category": "Adverse", "shock": "+50 bp cross-currency basis widening", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Credit +300 bp", "category": "Extreme", "shock": "+300 bp parallel credit-spread widening", "derived_from": "Credit +150 bp", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Equity -60%", "category": "Extreme", "shock": "-60% global equity spot", "derived_from": "Equity -30%", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "EUR/USD -30%", "category": "Extreme", "shock": "-30% EUR/USD spot", "derived_from": "EUR/USD -15%", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Basis +100 bp", "category": "Extreme", "shock": "+100 bp cross-currency basis widening", "derived_from": "Basis +50 bp", "pricing_status": "Awaiting risk-engine revaluation"},
]


def get_market_sensitivities():
    """Return V21 sensitivities plus one governed Inflation curve family."""
    result = v21.get_market_sensitivities()
    rows = list(result["sensitivities"])
    for currency, curve, delta, gamma, vega in INFLATION_CURVES:
        rows.extend([
            {
                "risk_class": "Rates",
                "measure": "IR Delta (DV01)",
                "currency": currency,
                "curve_type": "Inflation",
                "curve": curve,
                "value": float(delta),
                "unit": "EUR / bp",
                "definition": "P&L change for a +1 bp move in the named inflation curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "IR Gamma",
                "currency": currency,
                "curve_type": "Inflation",
                "curve": curve,
                "value": float(gamma),
                "unit": "EUR / bp²",
                "definition": "Change in inflation-curve DV01 for a +1 bp move.",
            },
            {
                "risk_class": "Rates",
                "measure": "Vega",
                "currency": currency,
                "curve_type": "Inflation",
                "curve": curve,
                "value": float(vega),
                "unit": "EUR / vol point",
                "definition": "P&L change for a +1 percentage-point move in inflation-option volatility.",
            },
        ])
    return {
        **result,
        "sensitivities": rows,
        "curve_families": ["OIS", "BOR", "Inflation"],
        "usage_note": (
            "Deterministic synthetic V22 sensitivity feed across EUR, USD, JPY and GBP. "
            "Rates are grouped into OIS, BOR and Inflation curve families; replace with governed risk-engine records in production."
        ),
    }


def get_stress_scenario_catalog():
    """Return priced and configured scenarios across the four governance categories."""
    return v21.get_stress_scenario_catalog() + ADDITIONAL_STRESS_CONFIGURATIONS


def get_var_change_summary(as_of_date=None):
    """Return Historical VaR changes over daily, weekly and monthly horizons."""
    frame = v8.df[["cob_date", "var_1d_99_hist"]].sort_values("cob_date").reset_index(drop=True)
    if frame.empty:
        return {"status": "NO_DATA", "comparisons": []}

    requested_date = pd.Timestamp(as_of_date) if as_of_date is not None else frame.iloc[-1]["cob_date"]
    eligible = frame.index[frame["cob_date"] <= requested_date].tolist()
    if not eligible:
        return {"status": "NO_DATA_ON_OR_BEFORE_DATE", "comparisons": []}

    current_position = eligible[-1]
    current = frame.iloc[current_position]
    current_date = pd.Timestamp(current["cob_date"])
    current_value = float(current["var_1d_99_hist"])

    horizons = [
        ("Daily", None),
        ("Weekly", current_date - pd.Timedelta(days=7)),
        ("Monthly", current_date - pd.DateOffset(months=1)),
    ]
    comparisons = []
    for period, target_date in horizons:
        if period == "Daily":
            reference_position = current_position - 1
            reference = frame.iloc[reference_position] if reference_position >= 0 else None
        else:
            candidates = frame.loc[frame["cob_date"] <= target_date]
            reference = candidates.iloc[-1] if not candidates.empty else None

        if reference is None:
            comparisons.append({
                "period": period,
                "available": False,
                "reference_date": None,
                "reference_value": None,
                "change": None,
                "change_pct": None,
                "reason": f"Insufficient history for a {period.lower()} comparison.",
            })
            continue

        reference_value = float(reference["var_1d_99_hist"])
        change = current_value - reference_value
        comparisons.append({
            "period": period,
            "available": True,
            "reference_date": str(pd.Timestamp(reference["cob_date"]).date()),
            "reference_value": reference_value,
            "change": change,
            "change_pct": None if reference_value == 0 else change / abs(reference_value) * 100.0,
            "reason": "",
        })

    return {
        "status": "AVAILABLE",
        "as_of_date": str(current_date.date()),
        "current_var": current_value,
        "comparisons": comparisons,
        "usage_note": (
            "Daily uses the preceding business-day observation. Weekly and monthly use the latest available "
            "business-day observation on or before the target calendar date."
        ),
    }

v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "IR Delta, Gamma and Vega across OIS, BOR and Inflation curves, plus FX Delta and Theta."
v8.TOOL_FUNCTIONS["get_stress_scenario_catalog"] = get_stress_scenario_catalog
v8.TOOL_DESCRIPTIONS["get_stress_scenario_catalog"] = "Governed Historical, Hypothetical, Adverse and Extreme scenario catalogue, including unpriced configurations."
v8.TOOL_FUNCTIONS.pop("compare_risk_runs", None)
v8.TOOL_DESCRIPTIONS.pop("compare_risk_runs", None)
v8.TOOL_FUNCTIONS["get_var_change_summary"] = get_var_change_summary
v8.TOOL_DESCRIPTIONS["get_var_change_summary"] = "Historical VaR changes over daily, weekly and monthly horizons for the selected as-of date."

v9.SYSTEM_INSTRUCTION += """

V22 controls:
- Use get_var_change_summary for deterministic Historical VaR changes over daily, weekly and monthly horizons.
- The additional Adverse and Extreme configurations are unpriced until risk-engine revaluation; never infer their P&L by scaling another result.
- The Inflation sensitivity family is deterministic synthetic demo data and must be labelled as such.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v21.ask_risk_agent

# Snapshot this version.
v22 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V23 implementation ----
"""M.R. AI Agent V23: tenor sensitivities and VaR movement attribution."""

import pandas as pd


VERSION = "V23"
v22.v9.VERSION = VERSION
DRIVER_COLUMNS = v22.DRIVER_COLUMNS
build_pla_demo_history = v22.build_pla_demo_history
evaluate_pla_test = v22.evaluate_pla_test
evaluate_all_limits = v22.evaluate_all_limits
evaluate_pnl_explain_alerts = v22.evaluate_pnl_explain_alerts
build_supplied_stress_frame = v22.build_supplied_stress_frame
get_stress_evolution = v22.get_stress_evolution
get_material_stress_scenarios = v22.get_material_stress_scenarios
get_stress_scenario_catalog = v22.get_stress_scenario_catalog
get_var_change_summary = v22.get_var_change_summary

TENOR_WEIGHTS = {
    "1Y": 0.12,
    "2Y": 0.18,
    "5Y": 0.30,
    "10Y": 0.25,
    "30Y": 0.15,
}

HKD_RATE_CURVES = [
    ("OIS", "HONIA OIS", 18_000, 240, 4_800),
    ("BOR", "HIBOR 3M", 9_000, 125, 2_600),
    ("BOR", "HIBOR 6M", 5_500, 75, 1_500),
    ("Inflation", "HK CPI", 2_800, 40, 900),
]

VAR_ATTRIBUTION_GROUPS = {
    "FX": ["contrib_var_fx_spot", "contrib_var_fx_vol_implied", "contrib_var_fx_basis"],
    "Rates": [
        "contrib_var_ir_sofr_curve",
        "contrib_var_ir_estr_curve",
        "contrib_var_ir_sonia_curve",
        "contrib_var_ir_swaption_vol",
        "contrib_var_ir_basis_tenor",
        "contrib_var_ir_convexity",
    ],
    "Credit": ["contrib_var_credit_ig_spread", "contrib_var_credit_hy_spread", "contrib_var_credit_cds_basis"],
    "Equity": ["contrib_var_equity_spot", "contrib_var_equity_vol"],
    "Commodity": ["contrib_var_commodity_energy", "contrib_var_commodity_metals"],
    "Inflation": ["contrib_var_inflation_breakeven"],
    "Diversification": ["diversification_effect"],
}


def get_market_sensitivities():
    """Return V22 sensitivities split by tenor and expanded to HKD."""
    source = v22.get_market_sensitivities()
    source_rows = list(source["sensitivities"])

    for curve_type, curve, delta, gamma, vega in HKD_RATE_CURVES:
        source_rows.extend([
            {
                "risk_class": "Rates",
                "measure": "IR Delta (DV01)",
                "currency": "HKD",
                "curve_type": curve_type,
                "curve": curve,
                "value": float(delta),
                "unit": "EUR / bp",
                "definition": "P&L change for a +1 bp move in the named HKD curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "IR Gamma",
                "currency": "HKD",
                "curve_type": curve_type,
                "curve": curve,
                "value": float(gamma),
                "unit": "EUR / bp²",
                "definition": "Change in HKD curve DV01 for a +1 bp move.",
            },
            {
                "risk_class": "Rates",
                "measure": "Vega",
                "currency": "HKD",
                "curve_type": curve_type,
                "curve": curve,
                "value": float(vega),
                "unit": "EUR / vol point",
                "definition": "P&L change for a +1 percentage-point volatility move.",
            },
        ])

    expanded_rows = []
    for row in source_rows:
        if row["risk_class"] != "Rates":
            expanded_rows.append({**row, "tenor": "N/A"})
            continue
        for tenor, weight in TENOR_WEIGHTS.items():
            expanded_rows.append({
                **row,
                "tenor": tenor,
                "value": float(row["value"]) * weight,
                "definition": f"{row['definition']} Allocated to the {tenor} tenor bucket.",
            })

    expanded_rows.extend([
        {
            "risk_class": "FX",
            "measure": "FX Delta",
            "currency": "USD/HKD",
            "curve_type": "Spot",
            "curve": "USD/HKD",
            "tenor": "N/A",
            "value": 145_000.0,
            "unit": "EUR / 1% spot",
            "definition": "P&L change for a +1% move in USD/HKD.",
        },
        {
            "risk_class": "Time",
            "measure": "Theta",
            "currency": "HKD",
            "curve_type": "Portfolio",
            "curve": "HKD portfolio",
            "tenor": "N/A",
            "value": -1_500.0,
            "unit": "EUR / day",
            "definition": "Expected one-business-day P&L from HKD time decay.",
        },
    ])

    return {
        **source,
        "currencies": ["EUR", "USD", "JPY", "GBP", "HKD"],
        "tenors": list(TENOR_WEIGHTS),
        "sensitivities": expanded_rows,
        "usage_note": (
            "Deterministic synthetic V23 feed across EUR, USD, JPY, GBP and HKD. "
            "OIS, BOR and Inflation sensitivities are split into 1Y, 2Y, 5Y, 10Y and 30Y buckets. "
            "Tenor allocation preserves each curve-level total."
        ),
    }


def _reference_row(frame, current_position, current_date, horizon):
    if horizon == "Daily":
        return None if current_position == 0 else frame.iloc[current_position - 1]
    target = current_date - (
        pd.Timedelta(days=7) if horizon == "Weekly" else pd.DateOffset(months=1)
    )
    candidates = frame.loc[frame["cob_date"] <= target]
    return None if candidates.empty else candidates.iloc[-1]


def get_var_change_attribution(as_of_date=None, horizon="Daily", hierarchy_level="Portfolio"):
    """Explain a Historical VaR movement over the selected horizon."""
    if horizon not in {"Daily", "Weekly", "Monthly"}:
        raise ValueError("horizon must be Daily, Weekly or Monthly")

    frame = v8.df.sort_values("cob_date").reset_index(drop=True)
    requested_date = pd.Timestamp(as_of_date) if as_of_date is not None else frame.iloc[-1]["cob_date"]
    eligible = frame.index[frame["cob_date"] <= requested_date].tolist()
    if not eligible:
        return {"status": "NO_DATA", "factor_changes": []}

    current_position = eligible[-1]
    current = frame.iloc[current_position]
    current_date = pd.Timestamp(current["cob_date"])
    reference = _reference_row(frame, current_position, current_date, horizon)
    if reference is None:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "horizon": horizon,
            "as_of_date": str(current_date.date()),
            "factor_changes": [],
        }

    factor_changes = []
    for factor, columns in VAR_ATTRIBUTION_GROUPS.items():
        sign = -1.0 if factor == "Diversification" else 1.0
        current_value = sign * float(current[columns].sum())
        reference_value = sign * float(reference[columns].sum())
        factor_changes.append({
            "factor": factor,
            "current_contribution": current_value,
            "reference_contribution": reference_value,
            "change": current_value - reference_value,
        })

    total_change = float(current["var_1d_99_hist"] - reference["var_1d_99_hist"])
    attributed_change = sum(item["change"] for item in factor_changes)
    reconciliation = total_change - attributed_change
    return {
        "status": "AVAILABLE",
        "horizon": horizon,
        "hierarchy_level": hierarchy_level,
        "as_of_date": str(current_date.date()),
        "reference_date": str(pd.Timestamp(reference["cob_date"]).date()),
        "current_var": float(current["var_1d_99_hist"]),
        "reference_var": float(reference["var_1d_99_hist"]),
        "total_change": total_change,
        "attributed_change": attributed_change,
        "reconciliation": reconciliation,
        "factor_changes": factor_changes,
        "usage_note": (
            "Movement attribution is calculated from changes in supplied VaR contributions. "
            "Reconciliation is total Historical VaR change minus the sum of attributed factor changes."
        ),
    }


v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Tenor-split OIS, BOR and Inflation sensitivities across EUR, USD, JPY, GBP and HKD, plus FX Delta and Theta."
v8.TOOL_FUNCTIONS["get_var_change_attribution"] = get_var_change_attribution
v8.TOOL_DESCRIPTIONS["get_var_change_attribution"] = "Historical VaR movement attribution by risk factor for a Daily, Weekly or Monthly horizon."

v9.SYSTEM_INSTRUCTION += """

V23 controls:
- Use get_var_change_attribution to explain Historical VaR movements by risk factor.
- Report the reconciliation item separately from risk factors; it is not a risk-factor exposure.
- Tenor sensitivities are deterministic synthetic allocations that preserve the curve-level totals.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v22.ask_risk_agent

# Snapshot this version.
v23 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V24 implementation ----
"""M.R. AI Agent V24: material-movement detection and stress-limit monitoring."""

import pandas as pd


VERSION = "V24"
v23.v9.VERSION = VERSION
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

# Snapshot this version.
v24 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V25 implementation ----
"""M.R. AI Agent V25: short-tenor limits and an auditable daily risk brief."""

import pandas as pd


VERSION = "V25"
v24.v9.VERSION = VERSION
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

# Snapshot this version.
v25 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V26 implementation ----
"""M.R. AI Agent V26: governed Delta aggregation and surface-based IR Vega."""

import pandas as pd


VERSION = "V26"
v25.v9.VERSION = VERSION

# Preserve the public version chain used by the dashboard.
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
            "V26 separates governed Net and Gross Delta. IR Gamma remains an informational "
            "second-order sensitivity without a limit in this prototype."
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

# Snapshot this version.
v26 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V27 implementation ----
"""M.R. AI Agent V27: curve-level Delta reporting and currency Vega surfaces."""

import pandas as pd



VERSION = "V27"
v26.v9.VERSION = VERSION


def get_delta_curve_tenor_summary(currencies=None):
    """Return curve rows plus a governed subtotal for each selected currency."""
    source = v26.get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    tenor_order = source["tenors"]
    frame = pd.DataFrame(source["sensitivities"])
    delta = frame.loc[
        (frame["measure"] == "IR Delta (DV01)")
        & frame["currency"].isin(selected)
    ].copy()

    detail = delta.pivot_table(
        index=["currency", "curve_type", "curve"],
        columns="tenor",
        values="value",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    for tenor in tenor_order:
        if tenor not in detail:
            detail[tenor] = 0.0

    rows = []
    for currency in selected:
        currency_detail = detail.loc[detail["currency"] == currency].sort_values(
            ["curve_type", "curve"]
        )
        for item in currency_detail.to_dict("records"):
            tenor_values = [float(item[tenor]) for tenor in tenor_order]
            rows.append({
                "currency": currency,
                "curve_type": item["curve_type"],
                "curve": item["curve"],
                **{tenor: float(item[tenor]) for tenor in tenor_order},
                "net_delta": sum(tenor_values),
                "net_limit": None,
                "net_pct": None,
                "gross_delta": sum(abs(value) for value in tenor_values),
                "gross_limit": None,
                "gross_pct": None,
                "row_type": "Curve",
            })

        currency_nodes = delta.loc[delta["currency"] == currency]
        net_delta = float(currency_nodes["value"].sum())
        gross_delta = float(currency_nodes["value"].abs().sum())
        limits = v26.DELTA_LIMITS[currency]
        tenor_totals = currency_nodes.groupby("tenor")["value"].sum()
        rows.append({
            "currency": currency,
            "curve_type": "Subtotal",
            "curve": f"{currency} total",
            **{tenor: float(tenor_totals.get(tenor, 0.0)) for tenor in tenor_order},
            "net_delta": net_delta,
            "net_limit": limits["net"],
            "net_pct": abs(net_delta) / limits["net"] * 100.0,
            "gross_delta": gross_delta,
            "gross_limit": limits["gross"],
            "gross_pct": gross_delta / limits["gross"] * 100.0,
            "row_type": "Currency subtotal",
        })

    return {
        "currencies": selected,
        "tenors": tenor_order,
        "rows": rows,
        "usage_note": (
            "Curve rows preserve the signed V25 tenor buckets. Each currency has its own subtotal, "
            "Net Delta limit and Gross Delta limit; there is no cross-currency total."
        ),
    }


v8.TOOL_FUNCTIONS["get_delta_curve_tenor_summary"] = get_delta_curve_tenor_summary
v8.TOOL_DESCRIPTIONS["get_delta_curve_tenor_summary"] = (
    "Curve and tenor IR Delta rows with governed subtotals by currency."
)

v9.SYSTEM_INSTRUCTION += """

V27 sensitivity reporting:
- Use get_delta_curve_tenor_summary when explaining curve-level or tenor-level IR Delta.
- Delta limits are evaluated separately for each currency; do not invent an all-currency subtotal.
- IR Vega is presented as a separate expiry-by-underlying-tenor surface for each currency.
"""

v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v26.ask_risk_agent

# Snapshot this version.
v27 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V28 implementation ----
"""M.R. AI Agent V28: curve limits and compact sensitivity presentation."""

import pandas as pd


VERSION = "V28"
v27.v9.VERSION = VERSION
DRIVER_COLUMNS = v27.v26.v25.DRIVER_COLUMNS

DISPLAY_TENORS = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y+"]
CURVE_FAMILY_LIMIT_SHARES = {"OIS": 0.55, "BOR": 0.30, "Inflation": 0.15}


def get_delta_curve_tenor_summary(currencies=None):
    """Return curve-level Delta limits and one subtotal per currency."""
    source = v27.get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    frame = pd.DataFrame(source["sensitivities"])
    delta = frame.loc[
        (frame["measure"] == "IR Delta (DV01)")
        & frame["currency"].isin(selected)
    ].copy()

    detail = delta.pivot_table(
        index=["currency", "curve_type", "curve"],
        columns="tenor",
        values="value",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    for tenor in ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"]:
        if tenor not in detail:
            detail[tenor] = 0.0
    detail["10Y+"] = detail["10Y"] + detail["30Y"]

    rows = []
    for currency in selected:
        currency_detail = detail.loc[detail["currency"] == currency].sort_values(
            ["curve_type", "curve"]
        )
        family_counts = currency_detail.groupby("curve_type")["curve"].nunique().to_dict()
        currency_limits = v27.v26.DELTA_LIMITS[currency]

        for item in currency_detail.to_dict("records"):
            tenor_values = [float(item[tenor]) for tenor in DISPLAY_TENORS]
            family_share = CURVE_FAMILY_LIMIT_SHARES.get(item["curve_type"], 0.0)
            curve_count = max(int(family_counts.get(item["curve_type"], 1)), 1)
            curve_share = family_share / curve_count
            net_limit = float(currency_limits["net"]) * curve_share
            gross_limit = float(currency_limits["gross"]) * curve_share
            net_delta = sum(tenor_values)
            gross_delta = sum(abs(value) for value in tenor_values)
            rows.append({
                "currency": currency,
                "curve_type": item["curve_type"],
                "curve": str(item["curve"]).replace("\ufffdSTR", "ESTR"),
                **{tenor: float(item[tenor]) for tenor in DISPLAY_TENORS},
                "net_delta": net_delta,
                "net_limit": net_limit,
                "net_pct": abs(net_delta) / net_limit * 100.0 if net_limit else 0.0,
                "gross_delta": gross_delta,
                "gross_limit": gross_limit,
                "gross_pct": gross_delta / gross_limit * 100.0 if gross_limit else 0.0,
                "row_type": "Curve",
            })

        currency_nodes = delta.loc[delta["currency"] == currency].copy()
        tenor_totals = currency_nodes.groupby("tenor")["value"].sum()
        display_totals = {
            tenor: float(tenor_totals.get(tenor, 0.0))
            for tenor in DISPLAY_TENORS
            if tenor != "10Y+"
        }
        display_totals["10Y+"] = float(
            tenor_totals.get("10Y", 0.0) + tenor_totals.get("30Y", 0.0)
        )
        net_delta = sum(display_totals.values())
        gross_delta = sum(
            row["gross_delta"]
            for row in rows
            if row["currency"] == currency and row["row_type"] == "Curve"
        )
        rows.append({
            "currency": currency,
            "curve_type": "Subtotal",
            "curve": f"{currency} total",
            **display_totals,
            "net_delta": net_delta,
            "net_limit": float(currency_limits["net"]),
            "net_pct": abs(net_delta) / float(currency_limits["net"]) * 100.0,
            "gross_delta": gross_delta,
            "gross_limit": float(currency_limits["gross"]),
            "gross_pct": gross_delta / float(currency_limits["gross"]) * 100.0,
            "row_type": "Currency subtotal",
        })

    return {
        "currencies": selected,
        "tenors": DISPLAY_TENORS,
        "rows": rows,
        "usage_note": (
            "10Y+ combines the 10Y and 30Y source nodes so no Delta is discarded. Curve limits are "
            "fixed prototype allocations of each currency limit: 55% OIS, 30% BOR and 15% Inflation, "
            "split equally between curves in a family."
        ),
    }


v8.TOOL_FUNCTIONS["get_delta_curve_tenor_summary"] = get_delta_curve_tenor_summary
v8.TOOL_DESCRIPTIONS["get_delta_curve_tenor_summary"] = (
    "Curve-level IR Delta, 10Y+ bucket, limits, consumption and currency subtotals."
)

v9.SYSTEM_INSTRUCTION += """

V28 sensitivity conventions:
- Net/Gross terminology is reserved for IR Delta.
- The displayed 10Y+ Delta bucket combines the 10Y and 30Y source nodes.
- Curve-level limits are prototype allocations and must not be represented as approved bank limits.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v27.ask_risk_agent

# Snapshot this version.
v28 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})

# ---- V29 implementation ----
"""M.R. AI Agent V29: interactive sensitivity-based Scenario Lab."""

import hashlib
import json

import pandas as pd


VERSION = "V29"
v28.v9.VERSION = VERSION

DRIVER_COLUMNS = v28.DRIVER_COLUMNS

BASE_SCENARIO_LOSS_LIMIT = 15_000_000.0
SCENARIO_WARNING_THRESHOLD_PCT = 80.0
SCENARIO_BREACH_THRESHOLD_PCT = 100.0

TENOR_YEARS = {
    "1M": 1 / 12,
    "3M": 0.25,
    "6M": 0.5,
    "1Y": 1.0,
    "2Y": 2.0,
    "5Y": 5.0,
    "10Y": 10.0,
    "30Y": 30.0,
}


def _twist_loading(tenor: str) -> float:
    """Map curve tenor to a -1 (front end) to +1 (long end) twist loading."""
    years = TENOR_YEARS.get(str(tenor), 5.0)
    minimum = min(TENOR_YEARS.values())
    maximum = max(TENOR_YEARS.values())
    return -1.0 + 2.0 * (years - minimum) / (maximum - minimum)


def get_scenario_lab_specification():
    """Return available shock dimensions and the V29 approximation methodology."""
    frame = pd.DataFrame(v28.get_market_sensitivities()["sensitivities"])
    rate_rows = frame.loc[frame["risk_class"] == "Rates"]
    fx_rows = frame.loc[frame["measure"] == "FX Delta"]
    return {
        "rate_currencies": sorted(rate_rows["currency"].dropna().unique().tolist()),
        "curve_families": sorted(rate_rows["curve_type"].dropna().unique().tolist()),
        "fx_pairs": sorted(fx_rows["curve"].dropna().unique().tolist()),
        "severity_options": {"Adverse (1x)": 1.0, "Extreme (2x)": 2.0},
        "methodology": (
            "Estimated scenario P&L = Delta x shock + 0.5 x Gamma x shock^2 + "
            "Vega x volatility change + FX Delta x spot move + Theta x horizon."
        ),
        "governance_note": (
            "Sensitivity-based what-if estimate. It is not an official full-revaluation "
            "risk-engine result and does not recalculate official VaR or Expected Shortfall."
        ),
    }


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
):
    """Estimate a custom scenario from the supplied Delta/Gamma/Vega/Theta feed.

    Rate and market shocks are multiplied by ``severity_multiplier``. Theta uses
    the explicitly selected horizon and is not doubled for an extreme scenario.
    Negative total P&L represents a loss and consumes the illustrative scenario
    loss limit.
    """
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

    frame = pd.DataFrame(v28.get_market_sensitivities()["sensitivities"]).copy()
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
        selected = frame.loc[rate_filter & frame["measure"].eq(measure)]
        for row in selected.to_dict("records"):
            node_shock = effective_parallel + effective_twist * _twist_loading(row["tenor"])
            if component == "IR Delta":
                contribution = float(row["value"]) * node_shock
            else:
                contribution = 0.5 * float(row["value"]) * node_shock**2
            detail_rows.append({
                "component": component,
                "currency": row["currency"],
                "curve_family": row["curve_type"],
                "curve": str(row["curve"]).replace("\ufffdSTR", "ESTR"),
                "tenor": row["tenor"],
                "applied_shock": f"{node_shock:+.1f} bp",
                "estimated_pnl": float(contribution),
            })

    vega_filter = frame["measure"].eq("Vega")
    if rate_currency != "All currencies":
        vega_filter &= frame["currency"].eq(rate_currency)
    if curve_family != "All curve families":
        vega_filter &= frame["curve_type"].eq(curve_family)
    effective_volatility_shift = float(volatility_shift_points) * severity_multiplier
    for row in frame.loc[vega_filter].to_dict("records"):
        contribution = float(row["value"]) * effective_volatility_shift
        detail_rows.append({
            "component": "IR Vega",
            "currency": row["currency"],
            "curve_family": row["curve_type"],
            "curve": str(row["curve"]).replace("\ufffdSTR", "ESTR"),
            "tenor": row.get("surface_node", row["tenor"]),
            "applied_shock": f"{effective_volatility_shift:+.1f} vol points",
            "estimated_pnl": float(contribution),
        })

    fx_filter = frame["measure"].eq("FX Delta")
    if fx_pair != "All FX pairs":
        fx_filter &= frame["curve"].eq(fx_pair)
    effective_fx_move = float(fx_spot_move_pct) * severity_multiplier
    for row in frame.loc[fx_filter].to_dict("records"):
        contribution = float(row["value"]) * effective_fx_move
        detail_rows.append({
            "component": "FX Delta",
            "currency": row["currency"],
            "curve_family": row["curve_type"],
            "curve": row["curve"],
            "tenor": "Spot",
            "applied_shock": f"{effective_fx_move:+.1f}%",
            "estimated_pnl": float(contribution),
        })

    theta_filter = frame["measure"].eq("Theta")
    if rate_currency != "All currencies":
        theta_filter &= frame["currency"].eq(rate_currency)
    for row in frame.loc[theta_filter].to_dict("records"):
        contribution = float(row["value"]) * int(horizon_days)
        detail_rows.append({
            "component": "Theta",
            "currency": row["currency"],
            "curve_family": row["curve_type"],
            "curve": row["curve"],
            "tenor": "Time",
            "applied_shock": f"{int(horizon_days)} days",
            "estimated_pnl": float(contribution),
        })

    detail = pd.DataFrame(detail_rows)
    component_order = ["IR Delta", "IR Gamma", "IR Vega", "FX Delta", "Theta"]
    component_values = (
        detail.groupby("component")["estimated_pnl"].sum().to_dict()
        if not detail.empty
        else {}
    )
    components = [
        {"component": component, "estimated_pnl": float(component_values.get(component, 0.0))}
        for component in component_order
    ]
    estimated_pnl = float(sum(row["estimated_pnl"] for row in components))
    if abs(estimated_pnl) < 1e-9:
        estimated_pnl = 0.0
    scenario_limit = float(BASE_SCENARIO_LOSS_LIMIT * allocation_weight)
    loss_amount = max(-estimated_pnl, 0.0)
    if abs(loss_amount) < 1e-9:
        loss_amount = 0.0
    consumption_pct = loss_amount / scenario_limit * 100.0 if scenario_limit else 0.0
    if consumption_pct >= SCENARIO_BREACH_THRESHOLD_PCT:
        status = "BREACH"
    elif consumption_pct >= SCENARIO_WARNING_THRESHOLD_PCT:
        status = "WARNING"
    else:
        status = "OK"

    if detail.empty:
        top_contributors = []
        currency_contributions = []
        curve_contributions = []
    else:
        ranked = detail.assign(abs_pnl=detail["estimated_pnl"].abs()).sort_values(
            "abs_pnl", ascending=False
        )
        top_contributors = ranked.drop(columns="abs_pnl").head(15).to_dict("records")
        currency_contributions = (
            detail.groupby(["currency", "component"], as_index=False)["estimated_pnl"]
            .sum()
            .to_dict("records")
        )
        curve_contributions = (
            detail.groupby(["currency", "curve", "component"], as_index=False)["estimated_pnl"]
            .sum()
            .assign(abs_pnl=lambda data: data["estimated_pnl"].abs())
            .sort_values("abs_pnl", ascending=False)
            .drop(columns="abs_pnl")
            .head(20)
            .to_dict("records")
        )

    parameters = {
        "rate_currency": rate_currency,
        "curve_family": curve_family,
        "parallel_shift_bp": float(parallel_shift_bp),
        "curve_twist_bp": float(curve_twist_bp),
        "fx_pair": fx_pair,
        "fx_spot_move_pct": float(fx_spot_move_pct),
        "volatility_shift_points": float(volatility_shift_points),
        "horizon_days": int(horizon_days),
        "severity_multiplier": float(severity_multiplier),
    }
    scenario_hash = hashlib.sha256(
        json.dumps({"parameters": parameters, "scope": scope_label, "as_of": as_of_date}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:10].upper()

    return {
        "scenario_id": f"SCN-V29-{scenario_hash}",
        "version": VERSION,
        "as_of_date": as_of_date,
        "scope": scope_label,
        "allocation_weight": float(allocation_weight),
        "calculation_mode": "Sensitivity approximation",
        "parameters": parameters,
        "effective_shocks": {
            "parallel_shift_bp": effective_parallel,
            "curve_twist_bp": effective_twist,
            "fx_spot_move_pct": effective_fx_move,
            "volatility_shift_points": effective_volatility_shift,
            "horizon_days": int(horizon_days),
        },
        "baseline": {"estimated_pnl": 0.0, "limit_consumption_pct": 0.0, "status": "OK"},
        "scenario": {
            "estimated_pnl": estimated_pnl,
            "loss_amount": loss_amount,
            "loss_limit": scenario_limit,
            "limit_consumption_pct": float(consumption_pct),
            "status": status,
            "new_limit_event": status in {"WARNING", "BREACH"},
        },
        "component_contributions": components,
        "currency_contributions": currency_contributions,
        "curve_contributions": curve_contributions,
        "top_contributors": top_contributors,
        "methodology": specification["methodology"],
        "governance_note": specification["governance_note"],
        "assumptions": [
            "Delta and Vega contributions are linear in their respective shocks.",
            "IR Gamma uses 0.5 x Gamma x rate-shock squared at each curve-tenor node.",
            "Curve twist loading runs from -1 at the shortest tenor to +1 at the longest tenor.",
            "Cross-gamma, smile dynamics, basis interactions and trade-level full revaluation are not modelled.",
            "The scenario loss limit is an illustrative V29 control, not an approved bank limit.",
        ],
    }


def ask_scenario_agent(question: str, scenario_context: dict) -> str:
    """Explain one deterministic V29 Scenario Lab result with Gemini."""
    system_instruction = v9.SYSTEM_INSTRUCTION + """

V29 Scenario Lab control:
- The supplied scenario context is deterministic evidence from run_interactive_scenario.
- Always call it a sensitivity approximation, never an official risk-engine revaluation.
- Do not claim that official VaR, Expected Shortfall or regulatory capital was recalculated.
- Highlight the largest contributions, loss-limit impact, scope, as-of date and omitted effects.
"""
    chat = get_gemini_client().chats.create(
        model=v8.MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    response = chat.send_message(
        f"User question: {question}\n\n"
        "Deterministic Scenario Lab result:\n"
        f"{json.dumps(scenario_context, indent=2, default=str)}\n\n"
        "Provide a concise market-risk-manager assessment grounded only in this result."
    )
    answer = response.text
    v9.write_audit_record(
        question,
        {"steps": ["Assess the saved sensitivity-based scenario."], "tools": ["run_interactive_scenario"]},
        {"run_interactive_scenario": scenario_context},
        {},
        answer,
    )
    return answer


v8.TOOL_FUNCTIONS["get_scenario_lab_specification"] = get_scenario_lab_specification
v8.TOOL_DESCRIPTIONS["get_scenario_lab_specification"] = (
    "V29 interactive scenario dimensions, sensitivity approximation formula and governance caveat."
)

v9.SYSTEM_INSTRUCTION += """

V29 Scenario Lab conventions:
- Interactive scenario results are sensitivity approximations, not official risk-engine revaluations.
- Do not state or imply that Scenario Lab recalculates official VaR, ES or regulatory capital.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v28.ask_risk_agent

# Snapshot this version.
v29 = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith('__')})


