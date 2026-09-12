"""Render the P&L page."""

def render(context):
    """Render this page from the application-shell context."""
    alt = context["alt"]
    amount = context["amount"]
    pd = context["pd"]
    percentage = context["percentage"]
    portfolio_df = context["portfolio_df"]
    risk = context["risk"]
    scope_label = context["scope_label"]
    selected_business_line = context["selected_business_line"]
    st = context["st"]
    st.header("P&L attribution")
    st.caption("Official FRTB terminology: Actual P&L (APL), Hypothetical P&L (HPL), and Risk-theoretical P&L (RTPL).")

    desk_history = portfolio_df.copy()
    desk_history["risk_theoretical_pnl"] = desk_history["clean_pnl"]
    desk_history["apl_hpl_difference"] = desk_history["actual_pnl"] - desk_history["hypothetical_pnl"]
    desk_history["hpl_rtpl_difference"] = desk_history["hypothetical_pnl"] - desk_history["risk_theoretical_pnl"]
    desk_history["Rates"] = desk_history["pnl_driver_ir_dv01"]
    desk_history["FX"] = desk_history["pnl_driver_fx_delta"]
    desk_history["Credit"] = desk_history["pnl_driver_cs01"]
    desk_history["Equity"] = 0.0
    desk_history["Vega"] = desk_history["pnl_driver_vega"]
    desk_history["Theta"] = desk_history["pnl_driver_theta"]
    desk_history["Gamma and cross-gamma"] = desk_history["pnl_driver_gamma"] + desk_history["pnl_driver_cross_gamma"]
    desk_history["New trades"] = desk_history["apl_hpl_difference"] * 0.55
    desk_history["Expired trades"] = desk_history["apl_hpl_difference"] * -0.15
    desk_history["Modified trades"] = desk_history["apl_hpl_difference"] * 0.60
    desk_history["explained_pnl"] = desk_history[risk.DRIVER_COLUMNS].sum(axis=1)
    desk_history["unexplained_pnl"] = desk_history["risk_theoretical_pnl"] - desk_history["explained_pnl"]
    latest_pnl = desk_history.iloc[-1]
    pla_correlation = float(
        desk_history["hypothetical_pnl"].rank(method="average").corr(
            desk_history["risk_theoretical_pnl"].rank(method="average")
        )
    )
    pla_ks = risk._empirical_ks_statistic(
        desk_history["hypothetical_pnl"], desk_history["risk_theoretical_pnl"]
    )
    pla_zone = risk._pla_zone(pla_correlation, pla_ks)
    pla_consequence = {
        "GREEN": "PLA green zone: no PLA surcharge from this test.",
        "AMBER": "PLA amber zone: the desk remains within IMA scope but a capital surcharge applies.",
        "RED": "PLA red zone: the desk is ineligible for IMA and falls back to the Standardised Approach.",
    }[pla_zone]
    desk_pla = {
        "business_line": selected_business_line,
        "trading_desk": scope_label,
        "observations": len(desk_history),
        "spearman_correlation": pla_correlation,
        "ks_statistic": pla_ks,
        "pla_zone": pla_zone,
        "regulatory_consequence": pla_consequence,
        "latest_hpl": float(latest_pnl["hypothetical_pnl"]),
        "latest_rtpl": float(latest_pnl["risk_theoretical_pnl"]),
        "latest_pla_residual": float(latest_pnl["hpl_rtpl_difference"]),
    }
    pla_results = pd.DataFrame([desk_pla])
    unexplained_ratio = (
        0.0
        if float(latest_pnl["actual_pnl"]) == 0
        else abs(float(latest_pnl["unexplained_pnl"])) / abs(float(latest_pnl["actual_pnl"])) * 100.0
    )
    desk_pnl_alert = {
        "unexplained_to_apl_pct": unexplained_ratio,
        "status": "ALERT" if unexplained_ratio > 20.0 else "OK",
    }
    st.caption(f"All P&L and PLA charts follow the top hierarchy perimeter: {scope_label}.")

    with st.container(horizontal=True):
        st.metric("Actual P&L (APL)", amount(latest_pnl["actual_pnl"]), border=True)
        st.metric("Hypothetical P&L (HPL)", amount(latest_pnl["hypothetical_pnl"]), border=True)
        st.metric("Risk-theoretical P&L (RTPL)", amount(latest_pnl["risk_theoretical_pnl"]), border=True)
        st.metric("APL − HPL difference", amount(latest_pnl["apl_hpl_difference"]), border=True)
        st.metric("HPL − RTPL PLA residual", amount(latest_pnl["hpl_rtpl_difference"]), border=True)

    with st.container(border=True):
        st.subheader("P&L levels and residuals")
        recent_window = desk_history.tail(22).copy()
        recent_window["Business date"] = recent_window["cob_date"]

        level_data = recent_window[
            ["Business date", "actual_pnl", "hypothetical_pnl", "risk_theoretical_pnl"]
        ].melt("Business date", var_name="series", value_name="value")
        level_data["series"] = level_data["series"].map({
            "actual_pnl": "APL",
            "hypothetical_pnl": "HPL",
            "risk_theoretical_pnl": "RTPL",
        })
        residual_data = recent_window[
            ["Business date", "apl_hpl_difference", "hpl_rtpl_difference"]
        ].melt("Business date", var_name="series", value_name="value")
        residual_data["series"] = residual_data["series"].map({
            "apl_hpl_difference": "APL − HPL",
            "hpl_rtpl_difference": "HPL − RTPL",
        })
        residual_bars = (
            alt.Chart(residual_data)
            .mark_bar(opacity=0.32, size=9)
            .encode(
                x=alt.X("Business date:T", title="Month", axis=alt.Axis(format="%b", tickCount=12)),
                xOffset=alt.XOffset("series:N", sort=["APL − HPL", "HPL − RTPL"]),
                y=alt.Y("value:Q", title="Residual (EUR)", axis=alt.Axis(orient="right"), scale=alt.Scale(zero=True)),
                color=alt.Color(
                    "series:N",
                    title="Residual bars",
                    scale=alt.Scale(domain=["APL − HPL", "HPL − RTPL"], range=["#E07A5F", "#3D5A80"]),
                ),
                tooltip=[
                    alt.Tooltip("Business date:N", title="Date"),
                    alt.Tooltip("series:N", title="Residual"),
                    alt.Tooltip("value:Q", title="Value", format=",.0f"),
                ],
            )
        )
        pnl_lines = (
            alt.Chart(level_data)
            .mark_line(strokeWidth=2.5)
            .encode(
                x=alt.X("Business date:T", title="Month", axis=alt.Axis(format="%b", tickCount=12)),
                y=alt.Y("value:Q", title="P&L level (EUR)", scale=alt.Scale(zero=False)),
                color=alt.Color(
                    "series:N",
                    title="P&L lines",
                    scale=alt.Scale(domain=["APL", "HPL", "RTPL"], range=["#2F6BFF", "#22A06B", "#8B5CF6"]),
                ),
                tooltip=[
                    alt.Tooltip("Business date:N", title="Date"),
                    alt.Tooltip("series:N", title="P&L"),
                    alt.Tooltip("value:Q", title="Value", format=",.0f"),
                ],
            )
        )
        combined_pnl_chart = (
            alt.layer(residual_bars, pnl_lines)
            .resolve_scale(y="independent", color="independent")
            .properties(height=430)
        )
        st.altair_chart(combined_pnl_chart)
        st.caption(
            "APL, HPL and RTPL are lines on the left axis. APL − HPL and HPL − RTPL are translucent bars "
            "on the right axis. The full 260-business-day history is shown with monthly labels."
        )
    with st.container(border=True):
        st.subheader("Risk-model P&L explain")
        with st.container(horizontal=True):
            st.metric("Explained P&L", amount(latest_pnl["explained_pnl"]), border=True)
            st.metric("Driver unexplained P&L", amount(latest_pnl["unexplained_pnl"]), border=True)
            st.metric("PLA residual (HPL − RTPL)", amount(latest_pnl["hpl_rtpl_difference"]), border=True)
            st.metric("Unexplained / |APL|", percentage(desk_pnl_alert["unexplained_to_apl_pct"]), border=True)
        if desk_pnl_alert["status"] == "ALERT":
            st.error(
                f"Unexplained P&L is {desk_pnl_alert['unexplained_to_apl_pct']:.1f}% of |APL|, above the 20% threshold.",
                icon=":material/error:",
            )
        else:
            st.success("Unexplained P&L is within the 20% of |APL| threshold.", icon=":material/check_circle:")
        explain_rows = pd.DataFrame(
            [{"Factor": column, "P&L": float(latest_pnl[column])} for column in risk.DRIVER_COLUMNS]
            + [{"Factor": "Unexplained P&L", "P&L": float(latest_pnl["unexplained_pnl"])}]
        )
        explain_rows["Factor"] = explain_rows["Factor"].replace({"Gamma and cross-gamma": "Gamma / cross-gamma"})
        explain_rows = explain_rows.sort_values("P&L")
        explain_bars = alt.Chart(explain_rows).mark_bar().encode(
            x=alt.X("P&L:Q", title="P&L contribution (EUR)", axis=alt.Axis(format=",.0f")),
            y=alt.Y("Factor:N", sort=None, title=None),
            color=alt.Color("Factor:N", title="P&L factor", legend=alt.Legend(orient="bottom")),
            tooltip=[alt.Tooltip("Factor:N"), alt.Tooltip("P&L:Q", format=",.0f")],
        )
        explain_labels = explain_bars.mark_text(align="left", dx=4, color="#E5E7EB").encode(text=alt.Text("P&L:Q", format=",.0f"))
        st.altair_chart((explain_bars + explain_labels).properties(height=380), key="risk_model_pnl_explain")
        st.caption("Each driver, including lifecycle effects and unexplained P&L, is shown separately. HPL minus RTPL remains the PLA residual above.")
    with st.container(border=True):
        st.subheader("FRTB P&L Attribution test")
        st.caption(
            "IMA means Internal Models Approach: supervisory permission to use approved internal market-risk models "
            "for regulatory capital. IMA-eligible means a nominated trading desk remains qualified through ongoing "
            "desk-level PLA and backtesting requirements; a green PLA result alone is not supervisory approval."
        )
        with st.container(horizontal=True):
            st.metric("PLA zone", desk_pla["pla_zone"], border=True)
            st.metric("Spearman correlation", f"{desk_pla['spearman_correlation']:.3f}", border=True)
            st.metric("KS statistic", f"{desk_pla['ks_statistic']:.3f}", border=True)
            st.metric("Observations", int(desk_pla["observations"]), border=True)

        if desk_pla["pla_zone"] == "RED":
            st.error(desk_pla["regulatory_consequence"], icon=":material/error:")
        elif desk_pla["pla_zone"] == "AMBER":
            st.warning(desk_pla["regulatory_consequence"], icon=":material/warning:")
        else:
            st.success(desk_pla["regulatory_consequence"], icon=":material/check_circle:")

        st.caption(
            "Green: Spearman > 0.80 and KS < 0.09 · "
            "Red: Spearman < 0.70 or KS > 0.12 · Otherwise amber."
        )
        pla_scatter_data = desk_history[["hypothetical_pnl", "risk_theoretical_pnl", "cob_date"]].copy()
        domain_min = float(pla_scatter_data[["hypothetical_pnl", "risk_theoretical_pnl"]].min().min())
        domain_max = float(pla_scatter_data[["hypothetical_pnl", "risk_theoretical_pnl"]].max().max())
        scatter = (
            alt.Chart(pla_scatter_data)
            .mark_circle(size=45, opacity=0.55)
            .encode(
                x=alt.X("hypothetical_pnl:Q", title="Hypothetical P&L (HPL)", scale=alt.Scale(domain=[domain_min, domain_max])),
                y=alt.Y("risk_theoretical_pnl:Q", title="Risk-theoretical P&L (RTPL)", scale=alt.Scale(domain=[domain_min, domain_max])),
                tooltip=[
                    alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"),
                    alt.Tooltip("hypothetical_pnl:Q", title="HPL", format=",.0f"),
                    alt.Tooltip("risk_theoretical_pnl:Q", title="RTPL", format=",.0f"),
                ],
            )
        )
        diagonal_data = pd.DataFrame({"HPL": [domain_min, domain_max], "RTPL": [domain_min, domain_max]})
        diagonal = alt.Chart(diagonal_data).mark_line(strokeDash=[5, 5], color="#808080").encode(
            x=alt.X("HPL:Q", scale=alt.Scale(domain=[domain_min, domain_max])),
            y=alt.Y("RTPL:Q", scale=alt.Scale(domain=[domain_min, domain_max])),
        )
        st.altair_chart(scatter + diagonal)
        st.caption("Points close to the diagonal indicate close agreement between HPL and RTPL.")

    with st.container(border=True):
        st.subheader("PLA status across trading desks")
        st.dataframe(
            pla_results,
            hide_index=True,
            column_order=[
                "business_line",
                "trading_desk",
                "observations",
                "spearman_correlation",
                "ks_statistic",
                "pla_zone",
                "regulatory_consequence",
                "latest_pla_residual",
            ],
            column_config={
                "business_line": "Business line",
                "trading_desk": "Trading desk",
                "observations": "Observations",
                "spearman_correlation": st.column_config.NumberColumn("Spearman", format="%.3f"),
                "ks_statistic": st.column_config.NumberColumn("KS", format="%.3f"),
                "pla_zone": "PLA zone",
                "regulatory_consequence": "Consequence",
                "latest_pla_residual": st.column_config.NumberColumn("Latest HPL − RTPL", format="%.0f"),
            },
        )

    with st.container(border=True):
        st.subheader("Backtesting")
        st.caption("Backtesting compares VaR with APL and HPL. RTPL is used for PLA, not backtesting.")
        with st.container(horizontal=True):
            st.metric("250-day exceptions", int(desk_history.iloc[-1]["backtest_exception_count_250d"]), border=True)
            st.metric("Hypothetical exception today", bool(desk_history.iloc[-1]["backtest_hypo_exception"]), border=True)
            st.metric("Actual exception today", bool(desk_history.iloc[-1]["backtest_actual_exception"]), border=True)
            st.metric("Traffic-light zone", desk_history.iloc[-1]["basel_traffic_light_zone"], border=True)


