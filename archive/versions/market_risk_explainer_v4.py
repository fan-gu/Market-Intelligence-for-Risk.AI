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

    # VaR
    var_change = current["var"] - previous["var"]

    var_change_pct = (
        var_change / previous["var"]
    ) * 100

    # P&L
    pnl_change = current["pnl"] - previous["pnl"]

    # Limit
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

    # Largest increase
    largest_change = max(
        changes,
        key=changes.get
    )

    largest_change_value = changes[
        largest_change
    ]

    return {
        "previous_var": previous["var"],
        "current_var": current["var"],
        "var_change": var_change,
        "var_change_pct": var_change_pct,

        "pnl_change": pnl_change,

        "limit_utilisation": limit_utilisation,

        "changes": changes,

        "largest_change": largest_change,
        "largest_change_value": largest_change_value
    }


# ==================================================
# 3. Risk question engine
# ==================================================

def ask_risk_question(question, analysis):

    question = question.lower()

    # ----------------------------------------------
    # VaR increase
    # ----------------------------------------------

    if (
        "why" in question
        and "var" in question
    ):

        return (
            f"VaR increased by "
            f"{analysis['var_change_pct']:.1f}%. "
            f"The largest increase came from "
            f"{analysis['largest_change']}, "
            f"which increased by "
            f"€{analysis['largest_change_value']:.1f}m."
        )

    # ----------------------------------------------
    # VaR change
    # ----------------------------------------------

    elif (
        "var" in question
        and (
            "change" in question
            or "increase" in question
            or "decrease" in question
        )
    ):

        direction = (
            "increased"
            if analysis["var_change"] > 0
            else "decreased"
        )

        return (
            f"VaR {direction} by "
            f"€{abs(analysis['var_change']):.1f}m "
            f"({abs(analysis['var_change_pct']):.1f}%)."
        )

    # ----------------------------------------------
    # Limit
    # ----------------------------------------------

    elif "limit" in question:

        utilisation = analysis["limit_utilisation"]

        if utilisation >= 80:
            status = "HIGH"
        elif utilisation >= 60:
            status = "MODERATE"
        else:
            status = "LOW"

        return (
            f"VaR limit utilisation is "
            f"{utilisation:.1f}%. "
            f"Risk level: {status}."
        )

    # ----------------------------------------------
    # P&L
    # ----------------------------------------------

    elif "p&l" in question or "pnl" in question:

        pnl = analysis["pnl_change"]

        if pnl > 0:
            direction = "positive"
        elif pnl < 0:
            direction = "negative"
        else:
            direction = "flat"

        return (
            f"Today's P&L change is "
            f"€{pnl:.1f}m. "
            f"The P&L impact is {direction}."
        )

    # ----------------------------------------------
    # Biggest risk factor
    # ----------------------------------------------

    elif (
        "biggest" in question
        or "largest" in question
        or "driver" in question
    ):

        return (
            f"The largest increase in risk "
            f"came from {analysis['largest_change']}, "
            f"which increased by "
            f"€{analysis['largest_change_value']:.1f}m."
        )

    # ----------------------------------------------
    # Show risk factors
    # ----------------------------------------------

    elif (
        "risk factor" in question
        or "risk factors" in question
        or "breakdown" in question
    ):

        result = "Risk-factor changes:\n"

        for name, change in analysis["changes"].items():

            result += (
                f"- {name}: "
                f"{'+' if change >= 0 else ''}"
                f"€{change:.1f}m\n"
            )

        return result

    # ----------------------------------------------
    # Unknown
    # ----------------------------------------------

    else:

        return (
            "I don't know how to answer that yet. "
            "Try asking about VaR, P&L, limits, "
            "or risk factors."
        )


# ==================================================
# 4. Main program
# ==================================================

file_name = r"C:\FG\Market Risk AI\risk_data.csv"

previous, current = load_risk_data(file_name)

analysis = analyse_risk(
    previous,
    current
)


# ==================================================
# 5. Chat interface
# ==================================================

print()
print("MARKET RISK AI ASSISTANT")
print("========================")
print("Ask me about today's market risk.")
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
