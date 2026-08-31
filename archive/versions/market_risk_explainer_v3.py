import pandas as pd


# ==================================================
# 1. Load risk data
# ==================================================

def load_risk_data(file_name):

    data = pd.read_csv(file_name)

    previous = data.iloc[-2]
    current = data.iloc[-1]

    return previous, current


# ==================================================
# 2. Analyse risk
# ==================================================

def analyse_risk(previous, current):

    # VaR change
    var_change = current["var"] - previous["var"]

    var_change_pct = (
        var_change / previous["var"]
    ) * 100

    # P&L change
    pnl_change = current["pnl"] - previous["pnl"]

    # Limit utilisation
    limit_utilisation = (
        current["var"] / current["var_limit"]
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

    # Largest change
    largest_change = max(
        changes,
        key=changes.get
    )

    largest_change_value = changes[
        largest_change
    ]

    return {
        "var_change": var_change,
        "var_change_pct": var_change_pct,
        "pnl_change": pnl_change,
        "limit_utilisation": limit_utilisation,
        "changes": changes,
        "largest_change": largest_change,
        "largest_change_value": largest_change_value
    }


# ==================================================
# 3. Answer user's question
# ==================================================

def ask_risk_question(question, analysis):

    question = question.lower()

    # ----------------------------------------------
    # Question 1: Why did VaR increase?
    # ----------------------------------------------

    if "why" in question and "var" in question:

        return (
            f"VaR increased by "
            f"{analysis['var_change_pct']:.1f}%. "
            f"The largest increase in risk contribution "
            f"came from {analysis['largest_change']}, "
            f"which increased by "
            f"€{analysis['largest_change_value']:.1f}m."
        )

    # ----------------------------------------------
    # Question 2: VaR limit
    # ----------------------------------------------

    elif "limit" in question:

        return (
            f"Current VaR limit utilisation is "
            f"{analysis['limit_utilisation']:.1f}%."
        )

    # ----------------------------------------------
    # Question 3: Biggest risk driver
    # ----------------------------------------------

    elif (
        "biggest" in question
        or "largest" in question
        or "driver" in question
    ):

        return (
            f"The largest increase in risk "
            f"contribution came from "
            f"{analysis['largest_change']}, "
            f"at €{analysis['largest_change_value']:.1f}m."
        )

    # ----------------------------------------------
    # Unknown question
    # ----------------------------------------------

    else:

        return (
            "I don't know how to answer that question yet."
        )


# ==================================================
# 4. Main program
# ==================================================

file_name = r"C:\FG\Market Risk AI\risk_data.csv"

previous, current = load_risk_data(file_name)

analysis = analyse_risk(previous, current)


# ==================================================
# 5. Simple conversational interface
# ==================================================

print()
print("MARKET RISK AI ASSISTANT")
print("========================")
print("Ask me a risk question.")
print("Type 'exit' to stop.")
print()

while True:

    question = input("You: ")

    if question.lower() == "exit":
        print("Assistant: Goodbye.")
        break

    answer = ask_risk_question(
        question,
        analysis
    )

    print()
    print("Assistant:", answer)
    print()
