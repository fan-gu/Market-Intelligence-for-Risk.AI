import os
import pandas as pd

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# MARKET RISK AI ASSISTANT
# VERSION 7
#
# V7.1 = Production-style data validation
# V7.2 = 10-day risk analytics
#
# Gemini will be connected AFTER the analytics layer
# has been validated.
# ============================================================


# ============================================================
# 1. CONFIGURATION
# ============================================================

FILE_NAME = r"C:\FG\Market Risk AI\market_risk_attribution_wide.csv"

#Expanded Wide Matrix Schema (agg_portfolio_daily_risk_wide)
# 1. Context & Top-Line VaR Metrics
# cob_date (DATE): Close of business date (T-1, T-2, etc.)
# portfolio_id (VARCHAR(50)): Global desk identifier (e.g., DESK_MACRO_FX_RATES)
# reporting_currency (VARCHAR(3)): Base reporting currency (EUR, USD)
# var_1d_99_hist (NUMERIC(18,2)): 1-Day 99% Historical VaR
# var_1d_99_param (NUMERIC(18,2)): 1-Day 99% Parametric / Delta-Normal VaR
# var_1d_99_mc (NUMERIC(18,2)): 1-Day 99% Monte Carlo VaR
# var_10d_99_reg (NUMERIC(18,2)): Regulatory 10-Day 99% VaR
# stressed_var_1d_99 (NUMERIC(18,2)): 1-Day Stressed VaR (sVaR)
# expected_shortfall_97_5 (NUMERIC(18,2)): FRTB Expected Shortfall (ES 97.5%)
# var_limit_amount (NUMERIC(18,2)): Board-level approved VaR limit
# var_limit_utilization_pct (NUMERIC(5,2)): Percent of VaR limit consumed
# 2. Risk Factor VaR Contributions (Component VaR)
# contrib_var_fx_spot (NUMERIC(18,2)): G10 & EM FX Spot move contribution
# contrib_var_fx_vol_implied (NUMERIC(18,2)): FX Implied Volatility surface shift
# contrib_var_fx_basis (NUMERIC(18,2)): Cross‑currency swap basis spread move
# contrib_var_ir_sofr_curve (NUMERIC(18,2)): USD SOFR yield curve shift (Delta)
# contrib_var_ir_estr_curve (NUMERIC(18,2)): EUR €STR yield curve shift (Delta)
# contrib_var_ir_sonia_curve (NUMERIC(18,2)): GBP SONIA yield curve shift (Delta)
# contrib_var_ir_swaption_vol (NUMERIC(18,2)): Interest rate option volatility grid (Vega)
# contrib_var_ir_basis_tenor (NUMERIC(18,2)): Tenor basis (e.g., 3M vs 6M floating leg spreads)
# contrib_var_ir_convexity (NUMERIC(18,2)): Non‑linear rate curvature (Gamma)
# contrib_var_credit_ig_spread (NUMERIC(18,2)): Investment Grade credit spreads (CS01)
# contrib_var_credit_hy_spread (NUMERIC(18,2)): High Yield credit spreads
# contrib_var_credit_cds_basis (NUMERIC(18,2)): Single‑name vs Index CDS basis
# contrib_var_equity_spot (NUMERIC(18,2)): Equity index and single‑stock price shifts
# contrib_var_equity_vol (NUMERIC(18,2)): Equity volatility skew and ATM shifts
# contrib_var_commodity_energy (NUMERIC(18,2)): Brent/WTI Crude and Gas curve shifts
# contrib_var_commodity_metals (NUMERIC(18,2)): Precious and base metals price shifts
# contrib_var_inflation_breakeven (NUMERIC(18,2)): Inflation swap & breakeven rate shifts
# diversification_effect (NUMERIC(18,2)): Portfolio diversification benefit (Undiversified VaR - Total VaR)
# 3. P&L & Greeks Attribution Drivers
# actual_pnl (NUMERIC(18,2)): Total daily accounting P&L
# hypothetical_pnl (NUMERIC(18,2)): Hypo P&L (fixed T‑1 portfolio under T‑1 to T market move)
# clean_pnl (NUMERIC(18,2)): Clean P&L (excluding fees, intraday trading, and reserves)
# unexplained_pnl (NUMERIC(18,2)): Unexplained P&L (residual driving backtesting exceptions)
# pnl_driver_fx_delta (NUMERIC(18,2)): P&L from linear FX exposure
# pnl_driver_ir_dv01 (NUMERIC(18,2)): P&L from interest rate DV01 shifts
# pnl_driver_vega (NUMERIC(18,2)): P&L from implied volatility changes across FX/Rates
# pnl_driver_gamma (NUMERIC(18,2)): 2nd‑order non‑linear P&L from large underlying moves
# pnl_driver_theta (NUMERIC(18,2)): Time decay P&L
# pnl_driver_cs01 (NUMERIC(18,2)): P&L from credit spread shifts
# pnl_driver_cross_gamma (NUMERIC(18,2)): Cross‑asset second‑order effects (e.g., FX x IR)
# 4. Backtesting & Model Validation
# backtest_hypo_exception (BOOLEAN): True if Hypo loss exceeds 1D 99% VaR
# backtest_actual_exception (BOOLEAN): True if Actual loss exceeds 1D 99% VaR
# backtest_exception_count_250d (INT): Rolling 250‑day exception count (Basel Traffic Light system)
# basel_traffic_light_zone (VARCHAR(10)): Regulatory zone (GREEN, YELLOW, RED)
# 5. Stress Scenario Outcomes (Hypothetical & Historical P&L Impact)
# stress_2008_lehman_crisis (NUMERIC(18,2)): P&L impact under 2008 Lehman collapse replay
# stress_2011_us_downgrade (NUMERIC(18,2)): P&L impact under US debt downgrade
# stress_2020_covid_liquidity (NUMERIC(18,2)): P&L impact under March 2020 market crash
# stress_2022_rate_hikes (NUMERIC(18,2)): P&L impact under aggressive central bank tightening
# stress_ir_up_100bp (NUMERIC(18,2)): Parallel +100bps yield curve shock
# stress_ir_down_100bp (NUMERIC(18,2)): Parallel -100bps yield curve shock
# stress_ir_steepener_50bp (NUMERIC(18,2)): 2Y/10Y yield curve steepening (+50bps)
# stress_ir_flattener_50bp (NUMERIC(18,2)): 2Y/10Y yield curve flattening (-50bps)
# stress_fx_usd_up_10pct (NUMERIC(18,2)): +10% USD appreciation vs G10 currencies
# stress_vol_up_50pct (NUMERIC(18,2)): +50% spike across all volatility surfaces


# ============================================================
# 2. GEMINI API
# ============================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY not found in .env"
    )

client = genai.Client(
    api_key=api_key
)

print("Gemini client initialized successfully.")


# ============================================================
# 3. LOAD RISK DATA
# ============================================================

def load_data():

    df = pd.read_csv(FILE_NAME)

    df["cob_date"] = pd.to_datetime(
        df["cob_date"]
    )

    df = df.sort_values(
        "cob_date"
    ).reset_index(drop=True)

    return df


df = load_data()

print(
    f"Loaded {len(df)} days "
    f"and {len(df.columns)} columns."
)


# ============================================================
# 4. TOOL 1 — CURRENT RISK
# ============================================================

def get_current_risk():

    current = df.iloc[-1]

    return {
        "date": str(
            current["cob_date"].date()
        ),

        "var_hist": float(
            current["var_1d_99_hist"]
        ),

        "var_parametric": float(
            current["var_1d_99_param"]
        ),

        "var_monte_carlo": float(
            current["var_1d_99_mc"]
        ),

        "var_10d_regulatory": float(
            current["var_10d_99_reg"]
        ),

        "stressed_var": float(
            current["stressed_var_1d_99"]
        ),

        "expected_shortfall": float(
            current["expected_shortfall_97_5"]
        ),

        "var_limit": float(
            current["var_limit_amount"]
        ),

        "limit_utilisation": float(
            current["var_limit_utilization_pct"]
        )
    }


# ============================================================
# 5. TOOL 2 — VAR TREND
# ============================================================

def get_var_trend():

    current = df.iloc[-1]
    previous = df.iloc[-2]

    current_var = float(
        current["var_1d_99_hist"]
    )

    previous_var = float(
        previous["var_1d_99_hist"]
    )

    change = (
        current_var
        - previous_var
    )

    change_pct = (
        change
        / previous_var
    ) * 100

    average_10d = float(
        df["var_1d_99_hist"].mean()
    )

    vs_average_pct = (
        (current_var - average_10d)
        / average_10d
    ) * 100

    return {
        "current_var": current_var,
        "previous_var": previous_var,
        "change": float(change),
        "change_pct": float(change_pct),
        "10_day_average": average_10d,
        "vs_10_day_average_pct": float(
            vs_average_pct
        )
    }


# ============================================================
# 6. TOOL 3 — VAR ATTRIBUTION
# ============================================================

def get_var_attribution():

    current = df.iloc[-1]

    columns = {

        "FX Spot":
            "contrib_var_fx_spot",

        "FX Implied Vol":
            "contrib_var_fx_vol_implied",

        "FX Basis":
            "contrib_var_fx_basis",

        "SOFR Curve":
            "contrib_var_ir_sofr_curve",

        "€STR Curve":
            "contrib_var_ir_estr_curve",

        "SONIA Curve":
            "contrib_var_ir_sonia_curve",

        "Swaption Vol":
            "contrib_var_ir_swaption_vol",

        "IR Basis":
            "contrib_var_ir_basis_tenor",

        "IR Convexity":
            "contrib_var_ir_convexity",

        "IG Credit Spread":
            "contrib_var_credit_ig_spread",

        "HY Credit Spread":
            "contrib_var_credit_hy_spread",

        "CDS Basis":
            "contrib_var_credit_cds_basis",

        "Equity Spot":
            "contrib_var_equity_spot",

        "Equity Vol":
            "contrib_var_equity_vol",

        "Energy":
            "contrib_var_commodity_energy",

        "Metals":
            "contrib_var_commodity_metals",

        "Inflation Breakeven":
            "contrib_var_inflation_breakeven"
    }

    result = {}

    for name, column in columns.items():

        result[name] = float(
            current[column]
        )

    return dict(
        sorted(
            result.items(),
            key=lambda item: item[1],
            reverse=True
        )
    )


# ============================================================
# 7. TOOL 4 — LIMIT ANALYSIS
# ============================================================

def get_limit_analysis():

    current = df.iloc[-1]

    utilisation = float(
        current[
            "var_limit_utilization_pct"
        ]
    )

    if utilisation >= 90:
        status = "CRITICAL"

    elif utilisation >= 80:
        status = "HIGH"

    elif utilisation >= 60:
        status = "MODERATE"

    else:
        status = "LOW"

    return {
        "current_var": float(
            current["var_1d_99_hist"]
        ),

        "var_limit": float(
            current["var_limit_amount"]
        ),

        "utilisation_pct": utilisation,

        "status": status
    }


# ============================================================
# 8. TOOL 5 — P&L ANALYSIS
# ============================================================

def get_pnl_analysis():

    current = df.iloc[-1]

    return {

        "actual_pnl": float(
            current["actual_pnl"]
        ),

        "hypothetical_pnl": float(
            current["hypothetical_pnl"]
        ),

        "clean_pnl": float(
            current["clean_pnl"]
        ),

        "unexplained_pnl": float(
            current["unexplained_pnl"]
        )
    }


# ============================================================
# 9. TOOL 6 — BACKTESTING
# ============================================================

def get_backtesting_analysis():

    current = df.iloc[-1]

    return {

        "hypothetical_exception": int(
            current[
                "backtest_hypo_exception"
            ]
        ),

        "actual_exception": int(
            current[
                "backtest_actual_exception"
            ]
        ),

        "exception_count_250d": int(
            current[
                "backtest_exception_count_250d"
            ]
        ),

        "basel_traffic_light_zone":
            str(
                current[
                    "basel_traffic_light_zone"
                ]
            )
    }


# ============================================================
# 10. TOOL 7 — STRESS ANALYSIS
# ============================================================

def get_stress_analysis():

    current = df.iloc[-1]

    scenarios = {

        "2008 Lehman Crisis":
            "stress_2008_lehman_crisis",

        "2011 US Downgrade":
            "stress_2011_us_downgrade",

        "2020 COVID Liquidity":
            "stress_2020_covid_liquidity",

        "2022 Rate Hikes":
            "stress_2022_rate_hikes",

        "IR +100bp":
            "stress_ir_up_100bp",

        "IR -100bp":
            "stress_ir_down_100bp",

        "IR Steepener":
            "stress_ir_steepener_50bp",

        "IR Flattener":
            "stress_ir_flattener_50bp",

        "USD +10%":
            "stress_fx_usd_up_10pct",

        "Volatility +50%":
            "stress_vol_up_50pct"
    }

    result = {}

    for name, column in scenarios.items():

        result[name] = float(
            current[column]
        )

    return result


# ============================================================
# 11. TOOL 8 — 10-DAY SUMMARY
# ============================================================

def get_ten_day_summary():

    return {

        "var_average": float(
            df["var_1d_99_hist"].mean()
        ),

        "var_min": float(
            df["var_1d_99_hist"].min()
        ),

        "var_max": float(
            df["var_1d_99_hist"].max()
        ),

        "var_standard_deviation": float(
            df["var_1d_99_hist"].std()
        ),

        "average_limit_utilisation": float(
            df[
                "var_limit_utilization_pct"
            ].mean()
        ),

        "maximum_limit_utilisation": float(
            df[
                "var_limit_utilization_pct"
            ].max()
        ),

        "cumulative_actual_pnl": float(
            df["actual_pnl"].sum()
        ),

        "best_pnl_day": float(
            df["actual_pnl"].max()
        ),

        "worst_pnl_day": float(
            df["actual_pnl"].min()
        )
    }


# ============================================================
# 12. TOOL 9 — DATA QUALITY
# ============================================================

def validate_data():

    missing = int(
        df.isna().sum().sum()
    )

    duplicate_dates = int(
        df["cob_date"].duplicated().sum()
    )

    date_diffs = (
        df["cob_date"]
        .diff()
        .dropna()
        .dt.days
    )

    date_sequence_ok = bool(
        (date_diffs == 1).all()
    )

    return {

        "rows": len(df),

        "columns": len(df.columns),

        "missing_values": missing,

        "duplicate_dates":
            duplicate_dates,

        "date_sequence_ok":
            date_sequence_ok
    }


# ============================================================
# 13. TOOL DISPATCHER
#
# Gemini chooses the function.
# Python executes it.
# ============================================================

def execute_tool(function_name):

    if function_name == "get_current_risk":
        return get_current_risk()

    elif function_name == "get_var_trend":
        return get_var_trend()

    elif function_name == "get_var_attribution":
        return get_var_attribution()

    elif function_name == "get_limit_analysis":
        return get_limit_analysis()

    elif function_name == "get_pnl_analysis":
        return get_pnl_analysis()

    elif function_name == "get_backtesting_analysis":
        return get_backtesting_analysis()

    elif function_name == "get_stress_analysis":
        return get_stress_analysis()

    elif function_name == "get_ten_day_summary":
        return get_ten_day_summary()

    elif function_name == "validate_data":
        return validate_data()

    else:
        return {
            "error":
                f"Unknown tool: {function_name}"
        }


# ============================================================
# 14. GEMINI TOOL DEFINITIONS
# ============================================================

tools = [
    types.Tool(
        function_declarations=[

            types.FunctionDeclaration(
                name="get_current_risk",
                description=(
                    "Get the latest market risk "
                    "snapshot including VaR, "
                    "stressed VaR, expected "
                    "shortfall and limit utilisation."
                )
            ),

            types.FunctionDeclaration(
                name="get_var_trend",
                description=(
                    "Analyse the latest VaR change "
                    "versus yesterday and versus "
                    "the 10-day average."
                )
            ),

            types.FunctionDeclaration(
                name="get_var_attribution",
                description=(
                    "Identify the major risk-factor "
                    "contributions to current VaR."
                )
            ),

            types.FunctionDeclaration(
                name="get_limit_analysis",
                description=(
                    "Analyse current VaR limit "
                    "utilisation and classify "
                    "the risk level."
                )
            ),

            types.FunctionDeclaration(
                name="get_pnl_analysis",
                description=(
                    "Analyse actual, hypothetical, "
                    "clean and unexplained P&L."
                )
            ),

            types.FunctionDeclaration(
                name="get_backtesting_analysis",
                description=(
                    "Analyse VaR backtesting "
                    "exceptions and Basel "
                    "traffic-light status."
                )
            ),

            types.FunctionDeclaration(
                name="get_stress_analysis",
                description=(
                    "Analyse historical and "
                    "hypothetical stress scenarios."
                )
            ),

            types.FunctionDeclaration(
                name="get_ten_day_summary",
                description=(
                    "Analyse 10-day VaR, limit "
                    "utilisation and P&L statistics."
                )
            ),

            types.FunctionDeclaration(
                name="validate_data",
                description=(
                    "Check the risk dataset for "
                    "basic data-quality issues."
                )
            )
        ]
    )
]


# ============================================================
# 15. THE MARKET RISK AGENT
# ============================================================

def ask_risk_agent(question):

    system_instruction = """
You are a Senior Market Risk Manager at a
large international bank.

You have access to a deterministic Python
market-risk analytics engine through tools.

Your job is to investigate market-risk
questions using these tools and then
provide a professional risk-manager
interpretation.

IMPORTANT RULES:

1. YOU are the agent.

2. Decide yourself which tools are needed.

3. You may call multiple tools.

4. You may call another tool after seeing
   the result of an earlier tool.

5. Do not invent financial numbers.

6. Do not perform calculations when a
   Python tool can provide the calculation.

7. Clearly distinguish facts from
   interpretation.

8. Do not claim causality unless the
   available data supports it.

9. For escalation questions consider:
   VaR,
   VaR trend,
   attribution,
   limits,
   P&L,
   stress,
   backtesting,
   and data quality.

10. If the data is insufficient, say so.

11. Answer concisely in professional
    Market Risk language.
    """

    chat = client.chats.create(

        model="gemini-3.6-flash",

        config=types.GenerateContentConfig(

            system_instruction=(
                system_instruction
            ),

            tools=tools
        )
    )

    # --------------------------------------------------------
    # First message
    # --------------------------------------------------------

    response = chat.send_message(
        question
    )

    # --------------------------------------------------------
    # AGENTIC LOOP
    # --------------------------------------------------------

    while response.function_calls:

        for function_call in response.function_calls:

            function_name = (
                function_call.name
            )

            print()
            print(
                f"[AGENT → {function_name}]"
            )

            result = execute_tool(
                function_name
            )

            print(
                "[TOOL RESULT → AGENT]"
            )

            response = chat.send_message(

                types.Part.from_function_response(

                    name=function_name,

                    response={
                        "result": result
                    }
                )
            )

    return response.text


# ============================================================
# 16. USER INTERFACE
# ============================================================

print()
print("=" * 70)
print("             MARKET RISK AI ASSISTANT")
print("                         V7")
print("=" * 70)
print()

print(
    "10-day / 54-column dataset loaded."
)

print(
    "Gemini agent is ready."
)

print(
    "The AI decides which risk tools to call."
)

print(
    "Type 'exit' to stop."
)

print()


while True:

    question = input("You: ")

    if question.lower().strip() == "exit":

        print(
            "Assistant: Goodbye."
        )

        break

    try:

        answer = ask_risk_agent(
            question
        )

        print()
        print("Assistant:")
        print(answer)
        print()

    except Exception as e:

        print()
        print("ERROR:")
        print(e)
        print()
