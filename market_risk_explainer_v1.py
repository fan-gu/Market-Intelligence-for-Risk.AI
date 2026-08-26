import pandas as pd


def explain_risk(file_name):

    # Read the risk data
    data = pd.read_csv(file_name)

    # Previous and current day
    previous = data.iloc[-2]
    current = data.iloc[-1]

    # VaR change
    var_change = current["var"] - previous["var"]
    var_change_pct = (var_change / previous["var"]) * 100

    # P&L change
    pnl_change = current["pnl"] - previous["pnl"]

    # Limit utilisation
    limit_utilisation = (
        current["var"] / current["var_limit"]
    ) * 100

    # Risk contributors
    contributors = {
        "EUR/USD": current["EUR_USD"],
        "USD/JPY": current["USD_JPY"],
        "Equity": current["Equity"],
        "Rates": current["Rates"]
    }

    biggest_driver = max(
        contributors,
        key=contributors.get
    )

    # Generate explanation
    print("\nMARKET RISK SUMMARY")
    print("-------------------")

    print(f"VaR: €{previous['var']:.1f}m → €{current['var']:.1f}m")
    print(f"VaR change: {var_change_pct:.1f}%")
    print(f"P&L change: €{pnl_change:.1f}m")
    print(f"Limit utilisation: {limit_utilisation:.1f}%")
    print(f"Main risk driver: {biggest_driver}")

    print("\nRisk interpretation:")
    print(
        f"VaR increased by {var_change_pct:.1f}%. "
        f"The largest risk contributor is {biggest_driver}. "
        f"VaR limit utilisation is {limit_utilisation:.1f}%."
    )


# Run
explain_risk("C:\FG\Market Risk AI/risk_data.csv")
