import os
import pandas as pd

from dotenv import load_dotenv
from google import genai


# ==================================================
# 1. Load environment variables
# ==================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY not found in .env"
    )


# ==================================================
# 2. Connect to Gemini
# ==================================================

client = genai.Client(
    api_key=api_key
)


# ==================================================
# 3. Load risk data
# ==================================================

def load_risk_data(file_name):

    data = pd.read_csv(file_name)

    previous = data.iloc[-2]
    current = data.iloc[-1]

    return previous, current


# ==================================================
# 4. Analyse market risk
# ==================================================

def analyse_risk(previous, current):

    # VaR
    var_change = (
        current["var"]
        - previous["var"]
    )

    var_change_pct = (
        var_change
        / previous["var"]
    ) * 100

    # P&L
    pnl_change = (
        current["pnl"]
        - previous["pnl"]
    )

    # VaR limit
    limit_utilisation = (
        current["var"]
        / current["var_limit"]
    ) * 100

    # Risk factors
    risk_factors = {
        "EUR/USD": "EUR_USD",
        "USD/JPY": "USD_JPY",
        "Equity": "Equity",
        "Rates": "Rates"
    }

    changes = {}

    for name, column in risk_factors.items():

        changes[name] = (
            current[column]
            - previous[column]
        )

    # Largest risk increase
    largest_change = max(
        changes,
        key=changes.get
    )

    largest_change_value = (
        changes[largest_change]
    )

    return {
        "date": str(current["date"]),

        "previous_var": float(
            previous["var"]
        ),

        "current_var": float(
            current["var"]
        ),

        "var_change": float(
            var_change
        ),

        "var_change_pct": float(
            var_change_pct
        ),

        "pnl_change": float(
            pnl_change
        ),

        "limit_utilisation": float(
            limit_utilisation
        ),

        "risk_factor_changes": changes,

        "largest_risk_driver": (
            largest_change
        ),

        "largest_risk_driver_change": float(
            largest_change_value
        )
    }


# ==================================================
# 5. Ask Gemini to explain the risk
# ==================================================

def ask_gemini(risk_analysis, question):

    prompt = f"""
You are a senior Market Risk Manager.

You are analysing a portfolio using the risk
information calculated by a deterministic Python
risk engine.

IMPORTANT:
- Do not invent numbers.
- Use only the risk data provided below.
- Distinguish facts from interpretation.
- Be concise and professional.
- Answer like a bank market-risk manager.

RISK DATA:

{risk_analysis}

USER QUESTION:

{question}

Provide a clear risk-manager-style answer.
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    return response.text


# ==================================================
# 6. Main program
# ==================================================

file_name = (
    r"C:\FG\Market Risk AI\risk_data.csv"
)

previous, current = load_risk_data(
    file_name
)

risk_analysis = analyse_risk(
    previous,
    current
)


# ==================================================
# 7. Chat interface
# ==================================================

print()
print("==============================")
print("     MARKET RISK AI ASSISTANT")
print("==============================")
print()
print("Risk data loaded successfully.")
print("Ask a market-risk question.")
print("Type 'exit' to stop.")
print()

while True:

    question = input("You: ")

    if question.lower() == "exit":

        print("Assistant: Goodbye.")
        break

    answer = ask_gemini(
        risk_analysis,
        question
    )

    print()
    print("Assistant:")
    print(answer)
    print()