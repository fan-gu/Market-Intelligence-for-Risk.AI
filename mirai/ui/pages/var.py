# ruff: noqa: E701
"""Render the VaR page."""

def render(context):
    """Render this page from the application-shell context."""
    SVAR_LIMIT_MULTIPLIER = context["SVAR_LIMIT_MULTIPLIER"]
    alt = context["alt"]
    amount = context["amount"]
    build_horizontal_waterfall_chart = context["build_horizontal_waterfall_chart"]
    pd = context["pd"]
    percentage = context["percentage"]
    portfolio_df = context["portfolio_df"]
    risk = context["risk"]
    st = context["st"]
    st.header("VaR")
    selected_raw_risk = portfolio_df.sort_values("cob_date").iloc[-1]
    selected_hist_var = float(selected_raw_risk["var_1d_99_hist"])
    selected_stressed_var = float(selected_raw_risk["stressed_var_1d_99"])
    selected_var_limit = float(selected_raw_risk["var_limit_amount"])
    selected_svar_limit = selected_var_limit * SVAR_LIMIT_MULTIPLIER
    # Six compact native metric cards preserve the complete risk summary on one row.
    with st.container(key="var_summary_cards"):
        var_metrics = st.columns(6, gap="small")
        metric_values = [
            ("HVaR", amount(selected_hist_var)),
            ("HVaR limit", amount(selected_var_limit)),
            ("HVaR consumption", percentage(0 if selected_var_limit == 0 else selected_hist_var / selected_var_limit * 100)),
            ("SVaR", amount(selected_stressed_var)),
            ("SVaR limit", amount(selected_svar_limit)),
            ("SVaR consumption", percentage(0 if selected_svar_limit == 0 else selected_stressed_var / selected_svar_limit * 100)),
        ]
        for block, (label, value) in zip(var_metrics, metric_values):
            with block:
                st.metric(label, value, border=True)

    history = portfolio_df.sort_values("cob_date").copy()
    def movement(column, days):
        latest = history.iloc[-1]
        prior = history.loc[history["cob_date"] <= latest["cob_date"] - pd.Timedelta(days=days)]
        if prior.empty: return None
        reference = prior.iloc[-1]
        value = 0.0 if float(reference[column]) == 0 else (float(latest[column]) / float(reference[column]) - 1.0) * 100.0
        return value, pd.Timestamp(reference["cob_date"]).strftime("%d/%m")
    with st.container(border=True):
        st.subheader("VaR movement")
        movement_blocks = st.columns(2, gap="large")
        for block, label, column, periods in [(movement_blocks[0], "HVaR change", "var_1d_99_hist", [("Daily",1),("Weekly",7),("Monthly",30)]), (movement_blocks[1], "SVaR change", "stressed_var_1d_99", [("Weekly",7),("Monthly",30)])]:
            with block.container(border=True):
                st.markdown(f"**{label}**")
                with st.container(horizontal=True):
                    for period, days in periods:
                        result = movement(column, days)
                        if result is None: st.metric(period, "N/A", border=True)
                        else: st.metric(period, f"{result[0]:+.1f}%", f"vs {result[1]}", border=True)

    with st.container(border=True):
        st.subheader("HVaR evolution")
        hvar_history = history[["cob_date", "var_1d_99_hist", "var_limit_amount"]].copy()
        hvar_line = alt.Chart(hvar_history).mark_line(color="#60A5FA", strokeWidth=2.4).encode(x=alt.X("cob_date:T", title="Month", axis=alt.Axis(format="%b", tickCount=12)), y=alt.Y("var_1d_99_hist:Q", title="HVaR (EUR)", scale=alt.Scale(zero=False)), tooltip=[alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"), alt.Tooltip("var_1d_99_hist:Q", title="HVaR", format=",.0f")])
        hvar_limit = alt.Chart(hvar_history).mark_rule(color="#F59E0B", strokeDash=[6,4], strokeWidth=2).encode(y=alt.Y("var_limit_amount:Q"), tooltip=[alt.Tooltip("var_limit_amount:Q", title="HVaR limit", format=",.0f")])
        st.altair_chart((hvar_line + hvar_limit).properties(height=340), key="hvar_evolution")

    with st.container(border=True):
        st.subheader("VaR movement attribution")
        attribution_horizon = st.segmented_control("Attribution horizon", ["Daily","Weekly","Monthly"], default="Daily", required=True, key="v29_var_attribution_horizon")
        horizon_days = {"Daily": 1, "Weekly": 7, "Monthly": 30}[attribution_horizon]
        current_attribution_row = history.iloc[-1]
        attribution_candidates = history.loc[
            history["cob_date"] <= current_attribution_row["cob_date"] - pd.Timedelta(days=horizon_days)
        ]
        if not attribution_candidates.empty:
            reference_attribution_row = attribution_candidates.iloc[-1]
            factor_changes = []
            for factor, columns in risk.VAR_ATTRIBUTION_GROUPS.items():
                factor_changes.append({
                    "factor": factor,
                    "change": float(current_attribution_row[columns].sum() - reference_attribution_row[columns].sum()),
                })
            var_attribution = {
                "status": "AVAILABLE",
                "as_of_date": str(pd.Timestamp(current_attribution_row["cob_date"]).date()),
                "reference_date": str(pd.Timestamp(reference_attribution_row["cob_date"]).date()),
                "total_change": float(current_attribution_row["var_1d_99_hist"] - reference_attribution_row["var_1d_99_hist"]),
                "factor_changes": factor_changes,
                "usage_note": "Calculated from the selected books' explicit daily component-risk records.",
            }
        else:
            var_attribution = {"status": "NO_DATA", "factor_changes": []}
        if var_attribution["status"] == "AVAILABLE":
            factors = [("Diversification effect" if item["factor"] == "Diversification" else item["factor"], item["change"], "Diversification" if item["factor"] == "Diversification" else "Risk factor") for item in var_attribution["factor_changes"]]
            st.altair_chart(build_horizontal_waterfall_chart(factors, total_label="Total VaR change", total_value=var_attribution["total_change"]), key="var_movement_attribution")
            st.caption(f"{attribution_horizon} movement from {pd.Timestamp(var_attribution['reference_date']).strftime('%d/%m')} to {pd.Timestamp(var_attribution['as_of_date']).strftime('%d/%m')}. {var_attribution['usage_note']}")
        else:
            st.info(f"Insufficient history for {attribution_horizon.lower()} VaR movement attribution.", icon=":material/info:")
    with st.container(border=True):
        st.subheader("Historical VaR attribution")
        attribution_columns = {
            "FX Spot": "contrib_var_fx_spot", "FX Implied Vol": "contrib_var_fx_vol_implied",
            "FX Basis": "contrib_var_fx_basis", "SOFR Curve": "contrib_var_ir_sofr_curve",
            "EUR ESTER Curve": "contrib_var_ir_estr_curve", "SONIA Curve": "contrib_var_ir_sonia_curve",
            "Swaption Vol": "contrib_var_ir_swaption_vol", "IR Basis": "contrib_var_ir_basis_tenor",
            "IR Convexity": "contrib_var_ir_convexity", "IG Credit Spread": "contrib_var_credit_ig_spread",
            "HY Credit Spread": "contrib_var_credit_hy_spread", "CDS Basis": "contrib_var_credit_cds_basis",
            "Equity Spot": "contrib_var_equity_spot", "Equity Vol": "contrib_var_equity_vol",
            "Energy": "contrib_var_commodity_energy", "Metals": "contrib_var_commodity_metals",
            "Inflation Breakeven": "contrib_var_inflation_breakeven",
        }
        attribution = pd.Series(
            {label: float(history.iloc[-1][column]) for label, column in attribution_columns.items()},
            name="VaR contribution",
        ).sort_values(ascending=False).rename_axis("Risk factor").reset_index()
        st.altair_chart(alt.Chart(attribution).mark_bar().encode(x=alt.X("VaR contribution:Q", title="VaR contribution (EUR)", axis=alt.Axis(format=",.0f")), y=alt.Y("Risk factor:N", sort="-x", title=None), color=alt.Color("Risk factor:N", legend=None), tooltip=[alt.Tooltip("Risk factor:N"), alt.Tooltip("VaR contribution:Q", format=",.0f")]).properties(height=360), key="historical_var_attribution")

