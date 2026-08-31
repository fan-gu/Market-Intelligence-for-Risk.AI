"""M.R. AI Agent V20: residual-focused P&L, richer sensitivities, and consolidated controls."""

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="M.R. AI Agent | V20", page_icon=":material/monitoring:", layout="wide")

try:
    import market_risk_agent_v20 as v20
except Exception as error:
    st.error(f"The risk dashboard could not load its data or configuration: {error}")
    st.stop()


v13 = v20.v13
v12 = v20.v12
v11 = v20.v11
v8 = v20.v8
st.session_state.setdefault("risk_agent_messages", [])
st.session_state.setdefault("v20_active_page", "Overview")


def select_dashboard_page():
    st.session_state.v20_active_page = st.session_state.v20_navigation


def select_agent_page():
    st.session_state.v20_active_page = "Ask MR Agent"


def amount(value):
    return f"{value:,.0f}"


def percentage(value):
    return f"{value:.1f}%"


def date_labels(frame):
    labelled = frame.copy()
    labelled["display_date"] = labelled["cob_date"].dt.strftime("%d/%m")
    return labelled


def display_amount_table(frame, amount_columns):
    formatted = frame.copy()
    for column in amount_columns:
        if column in formatted:
            formatted[column] = formatted[column].map(amount)
    st.dataframe(formatted, hide_index=True)


def alert_badge(severity):
    return {"CRITICAL": ":red-badge[Critical]", "HIGH": ":orange-badge[High]", "MEDIUM": ":yellow-badge[Monitor]", "INFO": ":blue-badge[Information]"}[severity]


df = v8.df.copy()
current_risk = v8.get_current_risk()
trend = v8.get_var_trend()
limit = v8.get_limit_analysis()
backtesting = v8.get_backtesting_analysis()
alert_summary = v11.get_risk_alerts()
risk_run = v12.get_risk_run_lineage()
lineage = risk_run["lineage"]
stress_evolution = v20.get_stress_evolution()

portfolio_scope = v20.v14.get_portfolio_scope()
portfolio_ids = [row["portfolio_id"] for row in portfolio_scope["portfolios"]]

available_as_of_dates = sorted(df["cob_date"].dt.date.unique(), reverse=True)
header_title, date_control = st.columns([5, 1.2], vertical_alignment="bottom")
with header_title:
    st.title("M.R. AI Agent")
with date_control:
    selected_as_of_date = st.selectbox(
        "As-of date",
        available_as_of_dates,
        format_func=lambda value: value.strftime("%d/%m"),
        key="v20_as_of_date",
    )
nav_control, agent_control = st.columns([6, 1.35], vertical_alignment="center")
with nav_control:
    st.segmented_control(
        "Navigate",
        ["Overview", "VaR", "P&L", "Sensitivities", "Stress", "Controls"],
        default="Overview",
        required=True,
        width="stretch",
        label_visibility="collapsed",
        key="v20_navigation",
        on_change=select_dashboard_page,
    )
with agent_control:
    st.button(
        "Ask MR Agent",
        icon=":material/auto_awesome:",
        type="primary",
        width="stretch",
        on_click=select_agent_page,
    )
page = st.session_state.v20_active_page

portfolio_df = df.loc[df["cob_date"] <= pd.Timestamp(selected_as_of_date)].copy()
if portfolio_df.empty:
    st.error("There are no observations on or before the selected as-of date.")
    st.stop()

stress_frame, stress_metadata = v20.build_supplied_stress_frame(selected_as_of_date)

books, _ = v20.v15.build_hierarchy()
hierarchy_columns = st.columns(3, vertical_alignment="bottom")
with hierarchy_columns[0]:
    selected_business_line = st.selectbox("Business line", ["All business lines"] + sorted(books["business_line"].unique()))
scoped_books = books if selected_business_line == "All business lines" else books.loc[books["business_line"] == selected_business_line]
with hierarchy_columns[1]:
    selected_desk = st.selectbox("Trading desk", ["All desks"] + sorted(scoped_books["trading_desk"].unique()))
scoped_books = scoped_books if selected_desk == "All desks" else scoped_books.loc[scoped_books["trading_desk"] == selected_desk]
with hierarchy_columns[2]:
    selected_book = st.selectbox("Book", ["All books"] + sorted(scoped_books["book_id"].unique()))
if selected_book != "All books":
    scoped_books = scoped_books.loc[scoped_books["book_id"] == selected_book]
allocation_weight = float(scoped_books["allocation_weight"].sum())
scope_label = " / ".join(value for value in [selected_business_line if selected_business_line != "All business lines" else None, selected_desk if selected_desk != "All desks" else None, selected_book if selected_book != "All books" else None] if value) or "Whole portfolio"
st.caption(f"Hierarchy scope: {scope_label} · synthetic allocation: {allocation_weight:.1%} of the aggregate risk run")
st.info("V20 hierarchy filters apply transparent synthetic allocations for exploration. They are not trade-level revaluation or additive VaR.", icon=":material/info:")

numeric_columns = portfolio_df.select_dtypes(include="number").columns
portfolio_df[numeric_columns] = portfolio_df[numeric_columns] * allocation_weight
for key in ("var_hist", "var_parametric", "var_monte_carlo", "var_10d_regulatory", "stressed_var", "expected_shortfall", "var_limit"):
    current_risk[key] *= allocation_weight
for key in ("current_var", "previous_var", "change", "10_day_average"):
    trend[key] *= allocation_weight
for key in ("current_var", "var_limit"):
    limit[key] *= allocation_weight
stress_frame = stress_frame.copy()
stress_numeric = [column for column in stress_frame.columns if column != "cob_date"]
stress_frame[stress_numeric] = stress_frame[stress_numeric] * allocation_weight

if page == "Overview":
    st.header("Overview")
    st.caption(f"As of {selected_as_of_date.strftime('%d/%m')} · {len(portfolio_df)} business-day observations")
    with st.container(horizontal=True):
        st.metric("Historical VaR (1 day, 99%)", amount(current_risk["var_hist"]), border=True)
        st.metric("Stressed VaR (SVaR)", amount(current_risk["stressed_var"]), border=True)
        st.metric("Expected shortfall (97.5%)", amount(current_risk["expected_shortfall"]), border=True)
        st.metric("Limit utilisation", percentage(current_risk["limit_utilisation"]), border=True)
    if alert_summary["action_required_count"]:
        st.warning(f"{alert_summary['action_required_count']} item(s) require review. See Controls for detail.", icon=":material/warning:")
    with st.container(border=True):
        st.subheader("Current run")
        st.write(f"**{lineage.get('run_id', 'Unavailable')}** · {lineage.get('source_file', 'Unavailable')}")
        st.caption("The run ID is generated by the demo adapter because the source export has no supplied run ID.")

elif page == "VaR":
    st.header("VaR")
    with st.container(horizontal=True):
        st.metric("Historical VaR (1 day, 99%)", amount(current_risk["var_hist"]), percentage(trend["change_pct"]), border=True)
        st.metric("Stressed VaR (SVaR)", amount(current_risk["stressed_var"]), border=True)
        st.metric("Approved VaR limit", amount(limit["var_limit"]), border=True)
        st.metric("Limit utilisation", percentage(limit["utilisation_pct"]), border=True)
    with st.container(border=True):
        st.subheader("Historical VaR evolution")
        var_chart = date_labels(portfolio_df).set_index("display_date")[["var_1d_99_hist"]].rename(columns={"var_1d_99_hist": "Historical VaR"})
        st.line_chart(var_chart)
        st.caption(f"Latest movement: {amount(trend['change'])} ({percentage(trend['change_pct'])}) versus the previous business-day observation.")
    with st.container(border=True):
        st.subheader("Historical VaR attribution")
        attribution = (pd.Series(v8.get_var_attribution(), name="VaR contribution") * allocation_weight).sort_values(ascending=False)
        st.bar_chart(attribution)
        display_amount_table(attribution.rename_axis("Risk factor").reset_index(), ["VaR contribution"])

elif page == "P&L":
    st.header("P&L attribution")
    st.caption("Official FRTB terminology: Actual P&L (APL), Hypothetical P&L (HPL), and Risk-theoretical P&L (RTPL).")

    pla_history = v20.build_pla_demo_history()
    pla_evaluation = v20.evaluate_pla_test()
    pla_results = pd.DataFrame(pla_evaluation["desk_results"])
    available_pla_desks = sorted(scoped_books["trading_desk"].unique())
    selected_pla_desk = st.selectbox(
        "Trading desk for P&L attribution",
        available_pla_desks,
        key="v20_pla_desk",
    )
    desk_history = pla_history.loc[pla_history["trading_desk"] == selected_pla_desk].copy()
    latest_pnl = desk_history.iloc[-1]
    desk_pla = pla_results.loc[pla_results["trading_desk"] == selected_pla_desk].iloc[0]
    pnl_alert_evaluation = v20.evaluate_pnl_explain_alerts()
    pnl_alert_frame = pd.DataFrame(pnl_alert_evaluation["desk_results"])
    desk_pnl_alert = pnl_alert_frame.loc[pnl_alert_frame["trading_desk"] == selected_pla_desk].iloc[0]

    st.info(
        "The 250-day desk history is deterministic synthetic V20 demo data. "
        "It demonstrates the Basel PLA workflow but is not a regulatory submission.",
        icon=":material/info:",
    )

    with st.container(horizontal=True):
        st.metric("Actual P&L (APL)", amount(latest_pnl["actual_pnl"]), border=True)
        st.metric("Hypothetical P&L (HPL)", amount(latest_pnl["hypothetical_pnl"]), border=True)
        st.metric("Risk-theoretical P&L (RTPL)", amount(latest_pnl["risk_theoretical_pnl"]), border=True)
        st.metric("APL − HPL difference", amount(latest_pnl["apl_hpl_difference"]), border=True)
        st.metric("HPL − RTPL PLA residual", amount(latest_pnl["hpl_rtpl_difference"]), border=True)

    with st.container(border=True):
        st.subheader("Recent P&L comparison")
        recent_pnl = desk_history.tail(30)[
            ["cob_date", "actual_pnl", "hypothetical_pnl", "risk_theoretical_pnl"]
        ].melt("cob_date", var_name="P&L measure", value_name="P&L")
        recent_pnl["P&L measure"] = recent_pnl["P&L measure"].map({
            "actual_pnl": "APL",
            "hypothetical_pnl": "HPL",
            "risk_theoretical_pnl": "RTPL",
        })
        comparison_chart = (
            alt.Chart(recent_pnl)
            .mark_bar()
            .encode(
                x=alt.X("cob_date:O", title="Business date", axis=alt.Axis(format="%d/%m", labelAngle=-45)),
                xOffset="P&L measure:N",
                y=alt.Y("P&L:Q", title="P&L (EUR)"),
                color=alt.Color("P&L measure:N", title=None),
                tooltip=[
                    alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"),
                    alt.Tooltip("P&L measure:N"),
                    alt.Tooltip("P&L:Q", format=",.0f"),
                ],
            )
        )
        st.altair_chart(comparison_chart)

    with st.container(border=True):
        st.subheader("P&L residuals")
        residuals = desk_history.tail(60)[
            ["cob_date", "apl_hpl_difference", "hpl_rtpl_difference"]
        ].melt("cob_date", var_name="Residual", value_name="P&L difference")
        residuals["Residual"] = residuals["Residual"].map({
            "apl_hpl_difference": "APL − HPL",
            "hpl_rtpl_difference": "HPL − RTPL",
        })
        residual_chart = (
            alt.Chart(residuals)
            .mark_bar()
            .encode(
                x=alt.X("cob_date:O", title="Business date", axis=alt.Axis(format="%d/%m", labelAngle=-45)),
                y=alt.Y("P&L difference:Q", title="Difference (EUR)"),
                color=alt.Color("Residual:N", title=None),
                tooltip=[
                    alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"),
                    alt.Tooltip("Residual:N"),
                    alt.Tooltip("P&L difference:Q", format=",.0f"),
                ],
            )
        )
        st.altair_chart(residual_chart)
        st.caption("Residual bars expose small model and trading-activity differences that overlap in a level chart.")

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
        driver_values = latest_pnl[v20.DRIVER_COLUMNS].sort_values()
        st.bar_chart(driver_values)
        driver_table = driver_values.rename_axis("Driver").rename("P&L contribution").reset_index()
        display_amount_table(driver_table, ["P&L contribution"])
        st.caption(
            "Driver unexplained P&L is RTPL minus recognised driver contributions. "
            "The PLA residual is HPL minus RTPL; these are separate diagnostics."
        )

    with st.container(border=True):
        st.subheader("FRTB P&L Attribution test")
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
            st.metric("250-day exceptions", backtesting["exception_count_250d"], border=True)
            st.metric("Hypothetical exception today", backtesting["hypothetical_exception"], border=True)
            st.metric("Actual exception today", backtesting["actual_exception"], border=True)
            st.metric("Traffic-light zone", backtesting["basel_traffic_light_zone"], border=True)

elif page == "Sensitivities":
    st.header("Sensitivities")
    sensitivities = v20.get_market_sensitivities()
    st.caption(sensitivities["usage_note"])
    sensitivity_frame = pd.DataFrame(sensitivities["sensitivities"])
    sensitivity_frame["value"] = sensitivity_frame["value"] * allocation_weight

    rates_frame = sensitivity_frame.loc[sensitivity_frame["risk_class"] == "Rates"].copy()
    fx_frame = sensitivity_frame.loc[sensitivity_frame["risk_class"] == "FX"].copy()
    currency_filter, curve_filter = st.columns(2, vertical_alignment="bottom")
    with currency_filter:
        selected_currencies = st.multiselect(
            "Rates currencies",
            sensitivities["currencies"],
            default=sensitivities["currencies"],
            key="v20_sensi_currencies",
        )
    with curve_filter:
        selected_curve_types = st.multiselect(
            "Curve types",
            ["OIS", "BOR"],
            default=["OIS", "BOR"],
            key="v20_sensi_curve_types",
        )

    selected_rates = rates_frame.loc[
        rates_frame["currency"].isin(selected_currencies)
        & rates_frame["curve_type"].isin(selected_curve_types)
    ].copy()
    dv01 = selected_rates.loc[selected_rates["measure"] == "IR Delta (DV01)", "value"]
    vega = selected_rates.loc[selected_rates["measure"] == "Vega", "value"]
    fx_delta = fx_frame["value"]
    with st.container(horizontal=True):
        st.metric("Net IR Delta (DV01, EUR / bp)", amount(dv01.sum()), border=True)
        st.metric("Gross IR Delta (DV01, EUR / bp)", amount(dv01.abs().sum()), border=True)
        st.metric("Net Vega (EUR / vol point)", amount(vega.sum()), border=True)
        st.metric("Gross FX Delta (EUR / 1% spot)", amount(fx_delta.abs().sum()), border=True)

    chart_columns = st.columns(2)
    with chart_columns[0]:
        with st.container(border=True, height="stretch"):
            st.subheader("Rates sensitivity by currency and curve")
            selected_rates_measure = st.selectbox(
                "Rates measure",
                ["IR Delta (DV01)", "IR Gamma", "Vega"],
                key="v20_rates_measure",
            )
            rates_chart_data = selected_rates.loc[selected_rates["measure"] == selected_rates_measure]
            if rates_chart_data.empty:
                st.info("Select at least one currency and curve type.", icon=":material/info:")
            else:
                rates_chart = (
                    alt.Chart(rates_chart_data)
                    .mark_bar()
                    .encode(
                        x=alt.X("curve:N", title="Curve", sort=None, axis=alt.Axis(labelAngle=-35)),
                        y=alt.Y("value:Q", title=str(rates_chart_data["unit"].iloc[0])),
                        color=alt.Color("currency:N", title="Currency"),
                        xOffset="currency:N",
                        tooltip=[
                            alt.Tooltip("currency:N", title="Currency"),
                            alt.Tooltip("curve_type:N", title="Curve type"),
                            alt.Tooltip("curve:N", title="Curve"),
                            alt.Tooltip("value:Q", title="Sensitivity", format=",.0f"),
                            alt.Tooltip("unit:N", title="Unit"),
                        ],
                    )
                )
                st.altair_chart(rates_chart)

    with chart_columns[1]:
        with st.container(border=True, height="stretch"):
            st.subheader("FX Delta versus USD")
            available_pairs = list(fx_frame["curve"])
            selected_pairs = st.multiselect(
                "FX pairs",
                available_pairs,
                default=available_pairs,
                key="v20_fx_pairs",
            )
            fx_chart_data = fx_frame.loc[fx_frame["curve"].isin(selected_pairs)]
            if fx_chart_data.empty:
                st.info("Select at least one FX pair.", icon=":material/info:")
            else:
                fx_chart = (
                    alt.Chart(fx_chart_data)
                    .mark_bar()
                    .encode(
                        x=alt.X("curve:N", title="FX pair", sort=None),
                        y=alt.Y("value:Q", title="EUR / 1% spot"),
                        color=alt.condition(
                            alt.datum.value >= 0,
                            alt.value("#2E8B57"),
                            alt.value("#C44E52"),
                        ),
                        tooltip=[
                            alt.Tooltip("curve:N", title="FX pair"),
                            alt.Tooltip("value:Q", title="FX Delta", format=",.0f"),
                            alt.Tooltip("unit:N", title="Unit"),
                        ],
                    )
                )
                st.altair_chart(fx_chart)

    with st.container(border=True):
        st.subheader("Sensitivity records")
        sensitivity_records = pd.concat([selected_rates, fx_frame], ignore_index=True)
        st.dataframe(
            sensitivity_records,
            hide_index=True,
            column_order=["risk_class", "measure", "currency", "curve_type", "curve", "value", "unit", "definition"],
            column_config={
                "risk_class": "Risk class",
                "measure": "Measure",
                "currency": "Currency / pair",
                "curve_type": "Curve type",
                "curve": "Curve",
                "value": st.column_config.NumberColumn("Sensitivity", format="%.0f"),
                "unit": "Unit",
                "definition": "Definition",
            },
        )
    st.caption("IR Delta is DV01 per +1 bp curve move. FX Delta is measured per +1% move in the quoted pair.")

elif page == "Stress":
    st.header("Stress")
    st.caption("Risk-engine-supplied scenario revaluation P&L only. Negative values represent losses versus the base valuation.")
    st.info(stress_evolution["usage_note"], icon=":material/info:")

    latest_stress = stress_frame.iloc[-1].drop(labels="cob_date").sort_values()
    scenario_names = [column for column in stress_frame.columns if column != "cob_date"]
    with st.container(border=True):
        st.subheader("Stress evolution by scenario")
        selected_scenarios = st.multiselect("Scenarios to display", scenario_names, default=scenario_names)
        if selected_scenarios:
            stress_chart = date_labels(stress_frame).set_index("display_date")[selected_scenarios]
            st.line_chart(stress_chart)

    worst_scenario, worst_impact = latest_stress.index[0], latest_stress.iloc[0]
    previous_stress = stress_frame.iloc[-2].drop(labels="cob_date") if len(stress_frame) > 1 else latest_stress
    deterioration = (latest_stress - previous_stress).sort_values().iloc[0]
    with st.container(horizontal=True):
        st.metric("Most adverse scenario", worst_scenario, amount(worst_impact), border=True)
        st.metric("Largest day-on-day deterioration", amount(deterioration), border=True)
        st.metric("Supplied scenarios", len(latest_stress), border=True)

    with st.container(border=True):
        st.subheader("Scenario definitions and current impacts")
        stress_table = pd.DataFrame({
            "Scenario": latest_stress.index,
            "Type": [stress_metadata[name]["type"] for name in latest_stress.index],
            "Current P&L impact": latest_stress.values,
            "Definition": [stress_metadata[name]["definition"] for name in latest_stress.index],
        })
        st.dataframe(
            stress_table,
            hide_index=True,
            column_config={
                "Current P&L impact": st.column_config.NumberColumn(format="%.0f"),
            },
        )

elif page == "Controls":
    st.header("Controls")
    limit_evaluation = v20.evaluate_all_limits()
    limit_frame = pd.DataFrame(limit_evaluation["limits"])
    status_rank = {"BREACH": 0, "WARNING": 1, "OK": 2}
    limit_frame["status_rank"] = limit_frame["status"].map(status_rank)
    limit_frame = limit_frame.sort_values(["status_rank", "consumption_pct"], ascending=[True, False]).drop(columns="status_rank")
    limit_summary = limit_evaluation["summary"]

    with st.container(horizontal=True):
        st.metric("Breaches", limit_summary["breaches"], border=True)
        st.metric("Warnings", limit_summary["warnings"], border=True)
        st.metric("Within limit", limit_summary["ok"], border=True)
        st.metric("Rules evaluated", len(limit_frame), border=True)

    with st.container(border=True):
        st.subheader("Limit governance")
        st.caption("Below 80% is OK · 80% to below 100% is WARNING · 100% or above is BREACH.")
        if limit_summary["breaches"]:
            st.error(f"{limit_summary['breaches']} limit breach(es) require immediate escalation.", icon=":material/error:")
        elif limit_summary["warnings"]:
            st.warning(f"{limit_summary['warnings']} limit warning(s) require owner review.", icon=":material/warning:")
        else:
            st.success("All governed metrics are below the 80% warning threshold.", icon=":material/check_circle:")
        st.dataframe(
            limit_frame,
            hide_index=True,
            column_order=["family", "metric", "exposure", "limit", "unit", "consumption_pct", "status", "owner", "escalation_status", "consumption_basis"],
            column_config={
                "family": "Risk family",
                "metric": "Metric",
                "exposure": st.column_config.NumberColumn("Exposure", format="%.0f"),
                "limit": st.column_config.NumberColumn("Limit", format="%.0f"),
                "unit": "Unit",
                "consumption_pct": st.column_config.ProgressColumn("Consumption", format="%.1f%%", min_value=0, max_value=120),
                "status": "Status",
                "owner": "Owner",
                "escalation_status": "Escalation",
                "consumption_basis": "Consumption basis",
            },
        )
        st.caption(limit_evaluation["usage_note"])
    weekday_rows = int((portfolio_df["cob_date"].dt.dayofweek < 5).sum())
    with st.container(horizontal=True):
        st.metric("Validation", risk_run["validation_status"], border=True)
        st.metric("Rows validated", lineage.get("row_count", 0), border=True)
        st.metric("Portfolio observations", len(portfolio_df), border=True)
        st.metric("Weekday observations", weekday_rows, border=True)
    with st.container(border=True):
        st.subheader("Run lineage")
        lineage_table = pd.DataFrame([
            ("Run ID", lineage.get("run_id")), ("Source", lineage.get("source_type")),
            ("Source file", lineage.get("source_file")), ("Fingerprint", lineage.get("data_fingerprint")),
            ("As-of date", pd.to_datetime(lineage.get("as_of_date")).strftime("%d/%m")),
        ], columns=["Field", "Value"])
        st.dataframe(lineage_table, hide_index=True)
    with st.container(border=True):
        st.subheader("Business-date controls")
        st.success("All observations in the current extract fall on Monday–Friday.", icon=":material/check_circle:")
        preview = date_labels(portfolio_df)[["display_date", "portfolio_id", "reporting_currency"]].rename(columns={"display_date": "COB date"})
        st.dataframe(preview, hide_index=True)
    with st.container(border=True):
        st.subheader("Data-quality checks")
        quality = pd.DataFrame([v8.validate_data()]).T.rename(columns={0: "Result"}).reset_index(names="Control")
        quality["Result"] = quality["Result"].astype(str)
        st.dataframe(quality, hide_index=True)

    with st.container(border=True):
        st.subheader("Alerts and exceptions")
        pnl_alert_evaluation = v20.evaluate_pnl_explain_alerts()
        pnl_alert_frame = pd.DataFrame(pnl_alert_evaluation["desk_results"])
        flagged_pnl = pnl_alert_frame.loc[pnl_alert_frame["status"] == "ALERT"].copy()
        with st.container(horizontal=True):
            st.metric("Rules-based risk alerts", len(alert_summary["alerts"]), border=True)
            st.metric("Unexplained-P&L flags", pnl_alert_evaluation["flagged_count"], border=True)
            st.metric("Unexplained threshold", "20% of |APL|", border=True)

        for alert in alert_summary["alerts"]:
            st.markdown(f"{alert_badge(alert['severity'])}  **{alert['title']}** — {alert['summary']}")

        if flagged_pnl.empty:
            st.success("No desk exceeds the unexplained-P&L threshold.", icon=":material/check_circle:")
        else:
            st.error(
                f"{len(flagged_pnl)} desk(s) exceed the 20% unexplained-to-|APL| threshold.",
                icon=":material/error:",
            )
            st.dataframe(
                flagged_pnl,
                hide_index=True,
                column_order=[
                    "business_line",
                    "trading_desk",
                    "actual_pnl",
                    "unexplained_pnl",
                    "unexplained_to_apl_pct",
                    "threshold_pct",
                    "status",
                ],
                column_config={
                    "business_line": "Business line",
                    "trading_desk": "Trading desk",
                    "actual_pnl": st.column_config.NumberColumn("APL", format="%.0f"),
                    "unexplained_pnl": st.column_config.NumberColumn("Unexplained P&L", format="%.0f"),
                    "unexplained_to_apl_pct": st.column_config.ProgressColumn(
                        "Unexplained / |APL|",
                        format="%.1f%%",
                        min_value=0,
                        max_value=50,
                    ),
                    "threshold_pct": st.column_config.NumberColumn("Threshold", format="%.1f%%"),
                    "status": "Status",
                },
            )
        st.caption(pnl_alert_evaluation["usage_note"])

else:
    st.header("Ask MR Agent")
    st.caption("The agent investigates deterministic risk results, stress evolution, run lineage and portfolio scope.")
    with st.container(border=True):
        selected_question = None
        if not st.session_state.risk_agent_messages:
            selected_question = st.pills("Suggested questions", ["How has stress evolved across scenarios?", "Which portfolios are included in this risk run?", "What are the main VaR and P&L risks today?"], label_visibility="collapsed")
        for message in st.session_state.risk_agent_messages:
            avatar = ":material/analytics:" if message["role"] == "assistant" else None
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])
        typed_question = st.chat_input("Ask about the current market-risk position", submit_mode="disable")
        question = typed_question or selected_question
        if question:
            st.session_state.risk_agent_messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant", avatar=":material/analytics:"):
                with st.status("Running the risk investigation...", expanded=True) as status:
                    try:
                        answer = v20.ask_risk_agent(question)
                    except Exception as error:
                        status.update(label="Investigation could not be completed", state="error")
                        st.error(str(error), icon=":material/error:")
                    else:
                        status.update(label="Investigation complete", state="complete", expanded=False)
                        st.markdown(answer)
                        st.session_state.risk_agent_messages.append({"role": "assistant", "content": answer})
    with st.expander("Recent investigation memory", icon=":material/history:"):
        memory = v20.v9.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.", icon=":material/info:")
