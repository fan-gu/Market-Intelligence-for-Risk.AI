import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types


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

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    try:
        import streamlit as st
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None
GEMINI_AVAILABLE = bool(api_key)
client = genai.Client(api_key=api_key) if api_key else None


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
    response = client.models.generate_content(
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

    chat = client.chats.create(
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
