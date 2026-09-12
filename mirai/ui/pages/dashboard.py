"""Render the Dashboard page."""

import plotly.graph_objects as go


def render(context):
    """Render this page from the application-shell context."""
    SVAR_LIMIT_MULTIPLIER = context["SVAR_LIMIT_MULTIPLIER"]
    alert_summary = context["alert_summary"]
    allocation_weight = context["allocation_weight"]
    alt = context["alt"]
    amount = context["amount"]
    pd = context["pd"]
    portfolio_df = context["portfolio_df"]
    risk = context["risk"]
    selected_as_of_date = context["selected_as_of_date"]
    st = context["st"]
    stress_frame = context["stress_frame"]
    stress_numeric = context["stress_numeric"]
    st.header("Dashboard")
    selected_row = portfolio_df.sort_values("cob_date").iloc[-1]
    selected_var = float(selected_row["var_1d_99_hist"])
    selected_svar = float(selected_row["stressed_var_1d_99"])
    selected_es = float(selected_row["expected_shortfall_97_5"])
    selected_apl = float(selected_row["actual_pnl"])

    with st.container(horizontal=True):
        st.metric("Historical VaR", amount(selected_var), border=True)
        st.metric("SVaR", amount(selected_svar), border=True)
        st.metric("Expected shortfall", amount(selected_es), border=True)
        st.metric("Actual P&L", amount(selected_apl), border=True)

    dashboard_chart_row = st.columns(2, gap="large")
    with dashboard_chart_row[0]:
        with st.container(border=True):
            st.subheader("Daily P&L attribution")
            pnl_factors = {
                "Rates": "pnl_driver_ir_dv01", "FX": "pnl_driver_fx_delta",
                "Vega": "pnl_driver_vega", "Gamma": "pnl_driver_gamma",
                "Theta": "pnl_driver_theta", "Credit": "pnl_driver_cs01",
                "Cross-gamma": "pnl_driver_cross_gamma",
            }
            pnl_attribution = pd.DataFrame({"Factor": list(pnl_factors), "P&L": [float(selected_row[column]) for column in pnl_factors.values()]})
            pnl_attribution = pnl_attribution.sort_values("P&L")
            st.altair_chart(
                alt.Chart(pnl_attribution).mark_bar().encode(
                    x=alt.X("P&L:Q", title="Daily P&L (EUR)", axis=alt.Axis(format=",.0f")),
                    y=alt.Y("Factor:N", sort=None, title=None),
                    color=alt.condition(alt.datum["P&L"] < 0, alt.value("#F87171"), alt.value("#34D399")),
                    tooltip=[alt.Tooltip("Factor:N"), alt.Tooltip("P&L:Q", format=",.0f")],
                ).properties(height=300),
                key="dashboard_daily_pnl_attribution",
            )
    with dashboard_chart_row[1]:
        with st.container(border=True):
            st.subheader("VaR and SVaR evolution")
            var_history = portfolio_df[["cob_date", "var_1d_99_hist", "stressed_var_1d_99", "var_limit_amount"]].copy()
            var_history["svar_limit_amount"] = var_history["var_limit_amount"] * SVAR_LIMIT_MULTIPLIER
            var_history = var_history.melt("cob_date", var_name="series", value_name="amount")
            var_history["series"] = var_history["series"].replace({"var_1d_99_hist":"Historical VaR", "stressed_var_1d_99":"SVaR", "var_limit_amount":"VaR limit", "svar_limit_amount":"SVaR limit"})
            st.altair_chart(
                alt.Chart(var_history).mark_line().encode(
                    x=alt.X("cob_date:T", title="Business date", axis=alt.Axis(format="%b", tickCount=12)),
                    y=alt.Y("amount:Q", title="EUR", scale=alt.Scale(zero=False)), color=alt.Color("series:N", title="Series"),
                    tooltip=[alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"), alt.Tooltip("series:N"), alt.Tooltip("amount:Q", title="EUR", format=",.0f")],
                ).properties(height=300), key="dashboard_var_evolution",
            )

    risk_chart_row = st.columns(2, gap="large")
    with risk_chart_row[0]:
        with st.container(border=True):
            st.subheader("EUR IR volatility surface")
            # Keep the Dashboard visual independent of a newly-added agent API.
            # This avoids stale-module errors on managed Streamlit deployments.
            sensitivity_frame = pd.DataFrame(risk.get_market_sensitivities()["sensitivities"])
            eur_vega = allocation_weight * float(
                sensitivity_frame.loc[
                    (sensitivity_frame["measure"] == "Vega")
                    & (sensitivity_frame["currency"] == "EUR"),
                    "value",
                ].abs().sum()
            )
            surface_expiries = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
            surface_tenors = ["1Y", "2Y", "5Y", "10Y", "30Y"]
            surface_rows = [
                {
                    "option_expiry": expiry,
                    "underlying_tenor": tenor,
                    "value": eur_vega * expiry_weight * tenor_weight,
                }
                for expiry, expiry_weight in zip(surface_expiries, [0.08, 0.12, 0.16, 0.20, 0.20, 0.24])
                for tenor, tenor_weight in zip(surface_tenors, [0.08, 0.12, 0.21, 0.29, 0.30])
            ]
            dashboard_surface = {
                "surface": surface_rows,
                "option_expiries": surface_expiries,
                "underlying_tenors": surface_tenors,
            }
            vega_surface = pd.DataFrame(dashboard_surface["surface"])
            expiries, underlyings = dashboard_surface["option_expiries"], dashboard_surface["underlying_tenors"]
            surface_grid = vega_surface.pivot(index="option_expiry", columns="underlying_tenor", values="value").reindex(index=expiries, columns=underlyings).fillna(0.0)
            surface_figure = go.Figure(data=[go.Surface(z=surface_grid.values, x=underlyings, y=expiries, colorscale="Blues", colorbar={"title":"EUR / vol point"}, hovertemplate="Option expiry: %{y}<br>Underlying tenor: %{x}<br>Vega: %{z:,.0f}<extra></extra>")])
            surface_figure.update_layout(height=330, margin={"l":0,"r":0,"t":10,"b":0}, scene={"xaxis_title":"Underlying swap tenor", "yaxis_title":"Option expiry", "zaxis_title":"IR Vega", "bgcolor":"#0F172A", "xaxis":{"backgroundcolor":"#0F172A"}, "yaxis":{"backgroundcolor":"#0F172A"}, "zaxis":{"backgroundcolor":"#0F172A"}}, paper_bgcolor="#0F172A", font={"color":"#E5E7EB"})
            st.plotly_chart(surface_figure, width="stretch", key="dashboard_eur_ir_vol_surface")
    with risk_chart_row[1]:
        with st.container(border=True):
            st.subheader("Largest Stress Loss")
            latest_stress = stress_frame.sort_values("cob_date").iloc[-1]
            stress_summary = pd.DataFrame({"Scenario": stress_numeric, "Stressed P&L": [float(latest_stress[item]) for item in stress_numeric]}).sort_values("Stressed P&L").head(6)
            st.altair_chart(alt.Chart(stress_summary).mark_bar().encode(x=alt.X("Stressed P&L:Q", title="EUR", axis=alt.Axis(format=",.0f")), y=alt.Y("Scenario:N", sort=None, title=None), color=alt.condition(alt.datum["Stressed P&L"] < 0, alt.value("#F87171"), alt.value("#34D399")), tooltip=[alt.Tooltip("Scenario:N"), alt.Tooltip("Stressed P&L:Q", format=",.0f")]).properties(height=300), key="dashboard_stress_losses")

    with st.container(border=True):
        st.subheader("Attention points")
        attention = []
        attention.extend({"Severity": row["severity"], "Source": "Risk alerts", "Finding": f"{row['title']}: {row['summary']}"} for row in alert_summary.get("alerts", []))
        stress_monitor = risk.get_stress_limit_monitor(selected_as_of_date)
        attention.extend({"Severity": row["status"], "Source": "Stress limits", "Finding": f"{row['scenario']}: {row['consumption_pct']:.1f}% consumed"} for row in stress_monitor["scenarios"] if row["status"] in {"WARNING", "BREACH"})
        if attention:
            severity_order = {"BREACH":0,"CRITICAL":0,"WARNING":1,"HIGH":1,"MEDIUM":2,"INFO":3}
            attention_frame = pd.DataFrame(attention)
            attention_frame["_severity_order"] = attention_frame["Severity"].map(severity_order).fillna(9)
            st.dataframe(attention_frame.sort_values(["_severity_order","Source","Finding"]).drop(columns="_severity_order"), hide_index=True, width="stretch")
        else:
            st.success("No current attention points are above configured thresholds.", icon=":material/check_circle:")




