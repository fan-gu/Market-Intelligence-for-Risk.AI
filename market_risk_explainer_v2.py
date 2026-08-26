import pandas as pd


def explain_risk(file_name):

    # ------------------------------------------------
    # 1. Read the risk data
    # ------------------------------------------------

    data = pd.read_csv(file_name)

    # Previous and current day
    previous = data.iloc[-2]
    current = data.iloc[-1]

    # ------------------------------------------------
    # 2. Calculate VaR change
    # ------------------------------------------------

    var_change = current["var"] - previous["var"]

    var_change_pct = (
        var_change / previous["var"]
    ) * 100

    # ------------------------------------------------
    # 3. Calculate P&L change
    # ------------------------------------------------

    pnl_change = current["pnl"] - previous["pnl"]

    # ------------------------------------------------
    # 4. Calculate VaR limit utilisation
    # ------------------------------------------------

    limit_utilisation = (
        current["var"] / current["var_limit"]
    ) * 100

    # ------------------------------------------------
    # 5. Compare risk-factor changes
    # ------------------------------------------------

    risk_factors = {
        "EUR/USD": "EUR_USD",
        "USD/JPY": "USD_JPY",
        "Equity": "Equity",
        "Rates": "Rates"
    }

    changes = {}

    for name, column in risk_factors.items():

        change = (
            current[column]
            - previous[column]
        )

        changes[name] = change

    # ------------------------------------------------
    # 6. Find the largest increase
    # ------------------------------------------------

    largest_change = max(
        changes,
        key=changes.get
    )

    largest_change_value = changes[
        largest_change
    ]

    # ------------------------------------------------
    # 7. Display results
    # ------------------------------------------------

    print()
    print("MARKET RISK SUMMARY")
    print("-------------------")

    print(
        f"Date: {current['date']}"
    )

    print(
        f"VaR: €{previous['var']:.1f}m → "
        f"€{current['var']:.1f}m"
    )

    print(
        f"VaR change: {var_change_pct:.1f}%"
    )

    print(
        f"P&L change: €{pnl_change:.1f}m"
    )

    print(
        f"VaR limit utilisation: "
        f"{limit_utilisation:.1f}%"
    )

    print()
    print("RISK FACTOR CHANGES")
    print("-------------------")

    for name, change in changes.items():

        print(
            f"{name}: "
            f"{'+' if change >= 0 else ''}"
            f"€{change:.1f}m"
        )

    # ------------------------------------------------
    # 8. Risk interpretation
    # ------------------------------------------------

    print()
    print("RISK INTERPRETATION")
    print("-------------------")

    print(
        f"VaR increased by "
        f"{var_change_pct:.1f}%."
    )

    print(
        f"The largest increase in risk "
        f"contribution came from "
        f"{largest_change}, "
        f"which increased by "
        f"€{largest_change_value:.1f}m."
    )

    print(
        f"Current VaR limit utilisation is "
        f"{limit_utilisation:.1f}%."
    )


# ------------------------------------------------
# Run the Market Risk Assistant
# ------------------------------------------------

explain_risk(
    r"C:\FG\Market Risk AI\risk_data.csv"
)