"""M.R. AI Agent V27: residual-focused P&L, richer sensitivities, and consolidated controls."""

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="M.R. AI Agent | V27", page_icon=":material/monitoring:", layout="wide")

try:
    import market_risk_agent_v27 as v27
except Exception as error:
    st.error(f"The risk dashboard could not load its data or configuration: {error}")
    st.stop()


v13 = v27.v13
v12 = v27.v12
v11 = v27.v11
v8 = v27.v8
st.session_state.setdefault("risk_agent_messages", [])
st.session_state.setdefault("v27_active_page", "Overview")


def select_dashboard_page():
    st.session_state.v27_active_page = st.session_state.v27_navigation


def select_agent_page():
    st.session_state.v27_active_page = "Ask MR Agent"


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


def build_waterfall_chart(
    factor_contributions,
    total_label,
    total_value,
    bridge_label=None,
    bridge_value=None,
):
    """Build a cumulative factor bridge with an optional unexplained step."""
    rows = []
    running = 0.0
    for contribution in factor_contributions:
        label, value = contribution[:2]
        contribution_type = contribution[2] if len(contribution) > 2 else "Risk factor"
        start = running
        running += float(value)
        rows.append({
            "Step": label,
            "start": start,
            "end": running,
            "low": min(start, running),
            "high": max(start, running),
            "display_value": float(value),
            "Type": contribution_type,
        })
    if bridge_label is not None and bridge_value is not None:
        bridge_end = running + float(bridge_value)
        rows.append({
            "Step": bridge_label,
            "start": running,
            "end": bridge_end,
            "low": min(running, bridge_end),
            "high": max(running, bridge_end),
            "display_value": float(bridge_value),
            "Type": "Unexplained",
        })
    rows.append({
        "Step": total_label,
        "start": 0.0,
        "end": float(total_value),
        "low": min(0.0, float(total_value)),
        "high": max(0.0, float(total_value)),
        "display_value": float(total_value),
        "Type": "Total",
    })
    waterfall = pd.DataFrame(rows)
    order = waterfall["Step"].tolist()
    base = alt.Chart(waterfall).encode(
        x=alt.X("Step:N", title=None, sort=order, axis=alt.Axis(labelAngle=-25)),
        tooltip=[
            alt.Tooltip("Step:N"),
            alt.Tooltip("display_value:Q", title="Contribution", format=",.0f"),
            alt.Tooltip("end:Q", title="Running total", format=",.0f"),
            alt.Tooltip("Type:N"),
        ],
    )
    bars = base.mark_bar(size=48).encode(
        y=alt.Y("low:Q", title="EUR"),
        y2="high:Q",
        color=alt.Color(
            "Type:N",
            title=None,
            scale=alt.Scale(
                domain=["Risk factor", "Diversification", "Unexplained", "Total"],
                range=["#60A5FA", "#FBBF24", "#F87171", "#34D399"],
            ),
        ),
    )
    zero = alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(
        color="#94A3B8", strokeWidth=1
    ).encode(y="zero:Q")
    positive_labels = (
        base.transform_filter(alt.datum.display_value >= 0)
        .mark_text(dy=-9, fontWeight="bold")
        .encode(y="high:Q", text=alt.Text("display_value:Q", format=",.0f"))
    )
    negative_labels = (
        base.transform_filter(alt.datum.display_value < 0)
        .mark_text(dy=13, fontWeight="bold")
        .encode(y="low:Q", text=alt.Text("display_value:Q", format=",.0f"))
    )
    return (zero + bars + positive_labels + negative_labels).properties(height=390)

df = v8.df.copy()
current_risk = v8.get_current_risk()
trend = v8.get_var_trend()
limit = v8.get_limit_analysis()
backtesting = v8.get_backtesting_analysis()
alert_summary = v11.get_risk_alerts()
risk_run = v12.get_risk_run_lineage()
lineage = risk_run["lineage"]
stress_evolution = v27.get_stress_evolution()

portfolio_scope = v27.v14.get_portfolio_scope()
portfolio_ids = [row["portfolio_id"] for row in portfolio_scope["portfolios"]]

available_as_of_dates = sorted(df["cob_date"].dt.date.unique(), reverse=True)
books, _ = v27.v15.build_hierarchy()

header_background = "#0F172A"
header_border = "#334155"
st.html(
    f"""
    <style>
    html, body, [data-testid="stAppViewContainer"], .stApp {{
        background: #0F172A !important;
        color-scheme: dark;
    }}
    [data-testid="stMainBlockContainer"] {{
        overflow: visible !important;
    }}
    div[data-testid="stElementContainer"]:has(.st-key-sticky_header),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-sticky_header),
    .st-key-sticky_header {{
        position: sticky !important;
        top: 2.875rem !important;
        z-index: 9999 !important;
        overflow: visible !important;
        background: {header_background} !important;
    }}
    .st-key-sticky_header {{
        padding: 0.35rem 0 0.45rem 0;
        border-bottom: 1px solid {header_border};
        box-shadow: 0 6px 14px rgba(0, 0, 0, 0.24);
        isolation: isolate;
    }}
    .st-key-sticky_header > div {{
        background: {header_background} !important;
    }}
    .st-key-sticky_header h1 {{
        font-size: 3.25rem !important;
        line-height: 1 !important;
        letter-spacing: -0.04em !important;
        white-space: nowrap;
    }}
    </style>
    """
)

with st.container(key="sticky_header"):
    header_controls = st.columns([2.35, 1.75, 1.75, 1.75, 1.15], vertical_alignment="bottom")
    with header_controls[0]:
        st.title("M.R.AI Agent")
    with header_controls[1]:
        selected_business_line = st.selectbox(
            "Business line",
            ["All business lines"] + sorted(books["business_line"].unique()),
            key="v27_business_line",
        )
    scoped_books = (
        books
        if selected_business_line == "All business lines"
        else books.loc[books["business_line"] == selected_business_line]
    )
    with header_controls[2]:
        selected_desk = st.selectbox(
            "Trading desk",
            ["All desks"] + sorted(scoped_books["trading_desk"].unique()),
            key="v27_trading_desk",
        )
    scoped_books = (
        scoped_books
        if selected_desk == "All desks"
        else scoped_books.loc[scoped_books["trading_desk"] == selected_desk]
    )
    with header_controls[3]:
        selected_book = st.selectbox(
            "Book",
            ["All books"] + sorted(scoped_books["book_id"].unique()),
            key="v27_book",
        )
    if selected_book != "All books":
        scoped_books = scoped_books.loc[scoped_books["book_id"] == selected_book]
    with header_controls[4]:
        selected_as_of_date = st.selectbox(
            "As-of date",
            available_as_of_dates,
            format_func=lambda value: value.strftime("%d/%m"),
            key="v27_as_of_date",
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
            key="v27_navigation",
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

page = st.session_state.v27_active_page
portfolio_df = df.loc[df["cob_date"] <= pd.Timestamp(selected_as_of_date)].copy()
if portfolio_df.empty:
    st.error("There are no observations on or before the selected as-of date.")
    st.stop()
stress_frame, stress_metadata = v27.build_supplied_stress_frame(selected_as_of_date)

allocation_weight = float(scoped_books["allocation_weight"].sum())
scope_label = " / ".join(
    value
    for value in [
        selected_business_line if selected_business_line != "All business lines" else None,
        selected_desk if selected_desk != "All desks" else None,
        selected_book if selected_book != "All books" else None,
    ]
    if value
) or "Whole portfolio"
header_limit_rows = v27.evaluate_all_limits()["limits"]
header_stress_rows = v27.get_stress_limit_monitor(selected_as_of_date)["scenarios"]
header_breaches = (
    [row["metric"] for row in header_limit_rows if row["status"] == "BREACH"]
    + [row["scenario"] for row in header_stress_rows if row["status"] == "BREACH"]
)
header_warnings = (
    [row["metric"] for row in header_limit_rows if row["status"] == "WARNING"]
    + [row["scenario"] for row in header_stress_rows if row["status"] == "WARNING"]
)
if header_breaches:
    st.error("Current limit breaches: " + " · ".join(dict.fromkeys(header_breaches)), icon=":material/error:")
if header_warnings:
    st.warning("Current limit warnings: " + " · ".join(dict.fromkeys(header_warnings)), icon=":material/warning:")
if not header_breaches and not header_warnings:
    st.success("All current governed risk measures are below warning thresholds.", icon=":material/check_circle:")
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
    var_change_summary = v27.get_var_change_summary(selected_as_of_date)
    selected_raw_risk = v8.df.loc[
        v8.df["cob_date"] <= pd.Timestamp(selected_as_of_date)
    ].sort_values("cob_date").iloc[-1]
    selected_hist_var = float(selected_raw_risk["var_1d_99_hist"]) * allocation_weight
    selected_stressed_var = float(selected_raw_risk["stressed_var_1d_99"]) * allocation_weight
    selected_var_limit = float(selected_raw_risk["var_limit_amount"]) * allocation_weight
    selected_utilisation = 0.0 if selected_var_limit == 0 else selected_hist_var / selected_var_limit * 100.0

    with st.container(horizontal=True):
        st.metric("Historical VaR (1 day, 99%)", amount(selected_hist_var), border=True)
        st.metric("Stressed VaR (SVaR)", amount(selected_stressed_var), border=True)
        st.metric("Approved VaR limit", amount(selected_var_limit), border=True)
        st.metric("Limit utilisation", percentage(selected_utilisation), border=True)

    with st.container(border=True):
        st.subheader("Historical VaR changes")
        comparison_by_period = {
            item["period"]: item for item in var_change_summary["comparisons"]
        }
        with st.container(horizontal=True):
            for period in ("Daily", "Weekly", "Monthly"):
                comparison = comparison_by_period[period]
                if comparison["available"]:
                    scaled_change = comparison["change"] * allocation_weight
                    reference_date = pd.Timestamp(comparison["reference_date"]).strftime("%d/%m")
                    delta_text = (
                        "N/A"
                        if comparison["change_pct"] is None
                        else f"{comparison['change_pct']:+.1f}% vs {reference_date}"
                    )
                    st.metric(
                        f"{period} change",
                        amount(scaled_change),
                        delta_text,
                        border=True,
                    )
                else:
                    st.metric(
                        f"{period} change",
                        "Insufficient history",
                        border=True,
                    )
        st.caption(var_change_summary["usage_note"])

    with st.container(border=True):
        st.subheader("VaR movement attribution")
        attribution_horizon = st.segmented_control(
            "Attribution horizon",
            ["Daily", "Weekly", "Monthly"],
            default="Daily",
            required=True,
            key="v27_var_attribution_horizon",
        )
        var_attribution = v27.get_var_change_attribution(
            selected_as_of_date,
            horizon=attribution_horizon,
            hierarchy_level=scope_label,
        )
        if var_attribution["status"] == "AVAILABLE":
            factor_movements = [
                (
                    "Diversification effect" if item["factor"] == "Diversification" else item["factor"],
                    item["change"] * allocation_weight,
                    "Diversification" if item["factor"] == "Diversification" else "Risk factor",
                )
                for item in var_attribution["factor_changes"]
            ]
            st.altair_chart(
                build_waterfall_chart(
                    factor_movements,
                    total_label="Total VaR change",
                    total_value=var_attribution["total_change"] * allocation_weight,
                )
            )
            st.caption(
                f"{attribution_horizon} movement from "
                f"{pd.Timestamp(var_attribution['reference_date']).strftime('%d/%m')} to "
                f"{pd.Timestamp(var_attribution['as_of_date']).strftime('%d/%m')}. "
                "Factor movements, including diversification, build directly to the total VaR change. "
                + var_attribution["usage_note"]
            )
        else:
            st.info(
                f"Insufficient history for {attribution_horizon.lower()} VaR movement attribution.",
                icon=":material/info:",
            )
    with st.container(border=True):
        st.subheader("Historical VaR evolution")
        var_chart = date_labels(portfolio_df).set_index("display_date")[["var_1d_99_hist"]].rename(columns={"var_1d_99_hist": "Historical VaR"})
        st.line_chart(var_chart)
    with st.container(border=True):
        st.subheader("Historical VaR attribution")
        attribution = (pd.Series(v8.get_var_attribution(), name="VaR contribution") * allocation_weight).sort_values(ascending=False)
        st.bar_chart(attribution)
        display_amount_table(attribution.rename_axis("Risk factor").reset_index(), ["VaR contribution"])
elif page == "P&L":
    st.header("P&L attribution")
    st.caption("Official FRTB terminology: Actual P&L (APL), Hypothetical P&L (HPL), and Risk-theoretical P&L (RTPL).")

    pla_history = v27.build_pla_demo_history()
    pla_history = pla_history.loc[pla_history["cob_date"] <= pd.Timestamp(selected_as_of_date)].copy()
    pnl_value_columns = [
        "actual_pnl", "hypothetical_pnl", "risk_theoretical_pnl",
        "apl_hpl_difference", "hpl_rtpl_difference", "explained_pnl", "unexplained_pnl",
        *v27.DRIVER_COLUMNS,
    ]
    full_desk_weights = books.groupby("trading_desk")["allocation_weight"].sum()
    scope_desk_weights = scoped_books.groupby("trading_desk")["allocation_weight"].sum()
    scope_scalars = (scope_desk_weights / full_desk_weights.reindex(scope_desk_weights.index)).to_dict()
    scoped_pla_history = pla_history.loc[
        pla_history["trading_desk"].isin(scope_scalars)
    ].copy()
    scoped_pla_history["scope_scalar"] = scoped_pla_history["trading_desk"].map(scope_scalars)
    scoped_pla_history[pnl_value_columns] = scoped_pla_history[pnl_value_columns].mul(
        scoped_pla_history["scope_scalar"], axis=0
    )
    desk_history = scoped_pla_history.groupby("cob_date", as_index=False)[pnl_value_columns].sum()
    latest_pnl = desk_history.iloc[-1]
    pla_correlation = float(
        desk_history["hypothetical_pnl"].rank(method="average").corr(
            desk_history["risk_theoretical_pnl"].rank(method="average")
        )
    )
    pla_ks = v27.v19._empirical_ks_statistic(
        desk_history["hypothetical_pnl"], desk_history["risk_theoretical_pnl"]
    )
    pla_zone = v27.v19._pla_zone(pla_correlation, pla_ks)
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
    st.info(
        "The 250-day desk history is deterministic synthetic V27 demo data. "
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
        st.subheader("P&L levels and residuals")
        recent_window = desk_history.tail(20).copy()
        recent_window["Business date"] = recent_window["cob_date"].dt.strftime("%d/%m")
        date_order = recent_window["Business date"].tolist()

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
        date_rules = pd.DataFrame({"Business date": date_order})

        vertical_separators = (
            alt.Chart(date_rules)
            .mark_rule(color="#98A2B3", strokeDash=[2, 4], opacity=0.45)
            .encode(x=alt.X("Business date:N", sort=date_order))
        )
        residual_bars = (
            alt.Chart(residual_data)
            .mark_bar(opacity=0.32, size=9)
            .encode(
                x=alt.X("Business date:N", title="Business date", sort=date_order, axis=alt.Axis(labelAngle=-45)),
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
                x=alt.X("Business date:N", sort=date_order),
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
        pnl_points = pnl_lines.mark_point(filled=True, size=42)
        combined_pnl_chart = (
            alt.layer(vertical_separators, residual_bars, pnl_lines, pnl_points)
            .resolve_scale(y="independent", color="independent")
            .properties(height=430)
        )
        st.altair_chart(combined_pnl_chart)
        st.caption(
            "APL, HPL and RTPL are lines on the left axis. APL − HPL and HPL − RTPL are translucent bars "
            "on the right axis. Dotted vertical rules separate business dates."
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
        driver_contributions = [
            (column, float(latest_pnl[column]))
            for column in v27.DRIVER_COLUMNS
        ]
        st.altair_chart(
            build_waterfall_chart(
                driver_contributions,
                total_label="RTPL",
                total_value=float(latest_pnl["risk_theoretical_pnl"]),
                bridge_label="Unexplained P&L",
                bridge_value=float(latest_pnl["unexplained_pnl"]),
            )
        )
        st.caption(
            "Risk factors accumulate directly into an unexplained P&L bridge and then RTPL. "
            "Unexplained P&L is not presented as a risk factor or subtotal. PLA residual remains HPL minus RTPL."
        )
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
            st.metric("250-day exceptions", backtesting["exception_count_250d"], border=True)
            st.metric("Hypothetical exception today", backtesting["hypothetical_exception"], border=True)
            st.metric("Actual exception today", backtesting["actual_exception"], border=True)
            st.metric("Traffic-light zone", backtesting["basel_traffic_light_zone"], border=True)

elif page == "Sensitivities":
    st.header("Sensitivities")
    sensitivities = v27.get_market_sensitivities()
    st.caption(sensitivities["usage_note"])
    sensitivity_frame = pd.DataFrame(sensitivities["sensitivities"])
    sensitivity_frame["value"] = sensitivity_frame["value"] * allocation_weight

    selected_currencies = st.multiselect(
        "Rates and Theta currencies",
        sensitivities["currencies"],
        default=sensitivities["currencies"],
        key="v27_sensi_currencies",
    )
    if not selected_currencies:
        st.warning("Select at least one currency to display sensitivities.")
        st.stop()

    rates_frame = sensitivity_frame.loc[
        (sensitivity_frame["risk_class"] == "Rates")
        & sensitivity_frame["currency"].isin(selected_currencies)
    ].copy()
    fx_frame = sensitivity_frame.loc[sensitivity_frame["risk_class"] == "FX"].copy()
    theta_frame = sensitivity_frame.loc[
        (sensitivity_frame["measure"] == "Theta")
        & sensitivity_frame["currency"].isin(selected_currencies)
    ].copy()

    dv01 = rates_frame.loc[rates_frame["measure"] == "IR Delta (DV01)", "value"]
    gamma = rates_frame.loc[rates_frame["measure"] == "IR Gamma", "value"]
    vega = rates_frame.loc[rates_frame["measure"] == "Vega", "value"]
    with st.container(horizontal=True):
        st.metric("Net Delta (EUR / bp)", amount(dv01.sum()), border=True)
        st.metric("Gross Delta (EUR / bp)", amount(dv01.abs().sum()), border=True)
        st.metric("IR Gamma (EUR / bp^2)", amount(gamma.sum()), border=True)
        st.metric("Net IR Vega (EUR / vol point)", amount(vega.sum()), border=True)
        st.metric("Gross FX Delta (EUR / 1% spot)", amount(fx_frame["value"].abs().sum()), border=True)
        st.metric("Net Theta (EUR / day)", amount(theta_frame["value"].sum()), border=True)

    currency_domain = ["EUR", "USD", "JPY", "GBP", "HKD"]
    currency_range = ["#2F6BFF", "#E07A5F", "#22A06B", "#8B5CF6", "#F59E0B"]

    with st.container(border=True):
        st.subheader("IR Delta by curve and tenor (EUR / bp)")
        delta_result = v27.get_delta_curve_tenor_summary(selected_currencies)
        tenor_order = delta_result["tenors"]
        delta_table = pd.DataFrame(delta_result["rows"])
        scaled_columns = tenor_order + ["net_delta", "gross_delta"]
        delta_table[scaled_columns] = delta_table[scaled_columns] * allocation_weight

        subtotal_mask = delta_table["row_type"] == "Currency subtotal"
        delta_table.loc[subtotal_mask, "net_pct"] = (
            delta_table.loc[subtotal_mask, "net_delta"].abs()
            / delta_table.loc[subtotal_mask, "net_limit"]
            * 100.0
        )
        delta_table.loc[subtotal_mask, "gross_pct"] = (
            delta_table.loc[subtotal_mask, "gross_delta"]
            / delta_table.loc[subtotal_mask, "gross_limit"]
            * 100.0
        )

        delta_display_columns = (
            ["currency", "curve_type", "curve"]
            + tenor_order
            + [
                "net_delta", "net_limit", "net_pct",
                "gross_delta", "gross_limit", "gross_pct",
            ]
        )
        st.dataframe(
            delta_table[delta_display_columns],
            hide_index=True,
            height=610,
            column_config={
                "currency": st.column_config.TextColumn("Currency", pinned=True),
                "curve_type": st.column_config.TextColumn("Curve family", pinned=True),
                "curve": st.column_config.TextColumn("Curve", pinned=True),
                **{
                    tenor: st.column_config.NumberColumn(tenor, format="%.0f")
                    for tenor in tenor_order
                },
                "net_delta": st.column_config.NumberColumn("Net Delta", format="%.0f"),
                "net_limit": st.column_config.NumberColumn("Limit", format="%.0f"),
                "net_pct": st.column_config.ProgressColumn(
                    "%", format="%.1f%%", min_value=0, max_value=160
                ),
                "gross_delta": st.column_config.NumberColumn("Gross Delta", format="%.0f"),
                "gross_limit": st.column_config.NumberColumn("Limit", format="%.0f"),
                "gross_pct": st.column_config.ProgressColumn(
                    "%", format="%.1f%%", min_value=0, max_value=160
                ),
            },
        )
        st.caption(delta_result["usage_note"])

    with st.container(border=True):
        st.subheader("IR Gamma by currency (EUR / bp^2)")
        gamma_table = (
            rates_frame.loc[rates_frame["measure"] == "IR Gamma"]
            .groupby("currency", as_index=False)["value"]
            .sum()
            .rename(columns={"currency": "Currency", "value": "IR Gamma"})
        )
        gamma_columns = st.columns([1.65, 1], gap="medium", vertical_alignment="center")
        with gamma_columns[0]:
            st.altair_chart(
                alt.Chart(gamma_table)
                .mark_bar(size=38)
                .encode(
                    x=alt.X("Currency:N", sort=currency_domain),
                    y=alt.Y("IR Gamma:Q", title="EUR / bp^2", scale=alt.Scale(zero=True)),
                    color=alt.Color(
                        "Currency:N",
                        scale=alt.Scale(domain=currency_domain, range=currency_range),
                        legend=None,
                    ),
                    tooltip=["Currency:N", alt.Tooltip("IR Gamma:Q", format=",.0f")],
                )
                .properties(height=205)
            )
        with gamma_columns[1]:
            st.dataframe(
                gamma_table,
                hide_index=True,
                height=245,
                column_config={
                    "Currency": st.column_config.TextColumn(pinned=True),
                    "IR Gamma": st.column_config.NumberColumn(format="%.0f"),
                },
            )
        st.caption(
            "IR Gamma is the signed sum across all curve and tenor nodes for each currency. "
            "It is informational and has no limit or consumption."
        )

    with st.container(border=True):
        st.subheader("IR Vega surfaces by currency (EUR / vol point)")
        surface_result = v27.get_ir_vega_surface(selected_currencies)
        surface_frame = pd.DataFrame(surface_result["surface"])
        surface_frame["value"] = surface_frame["value"] * allocation_weight
        currency_surface = (
            surface_frame.groupby(
                ["currency", "option_expiry", "underlying_tenor"],
                as_index=False,
            )["value"]
            .sum()
        )
        surface_scale = max(float(currency_surface["value"].abs().max()), 1.0)
        surface_order = [
            currency for currency in currency_domain if currency in selected_currencies
        ]

        for row_start in range(0, len(surface_order), 3):
            surface_columns = st.columns(3, gap="small")
            for offset, currency in enumerate(surface_order[row_start:row_start + 3]):
                with surface_columns[offset]:
                    with st.container(border=True):
                        st.markdown(f"**{currency}**")
                        currency_data = currency_surface.loc[
                            currency_surface["currency"] == currency
                        ]
                        cells = (
                            alt.Chart(currency_data)
                            .mark_rect(cornerRadius=4)
                            .encode(
                                x=alt.X(
                                    "underlying_tenor:N",
                                    title="Swap tenor",
                                    sort=surface_result["underlying_tenors"],
                                ),
                                y=alt.Y(
                                    "option_expiry:N",
                                    title="Option expiry",
                                    sort=surface_result["option_expiries"],
                                ),
                                color=alt.Color(
                                    "value:Q",
                                    title=None,
                                    scale=alt.Scale(
                                        scheme="redblue",
                                        domain=[-surface_scale, surface_scale],
                                        domainMid=0,
                                    ),
                                    legend=None,
                                ),
                                tooltip=[
                                    alt.Tooltip("currency:N", title="Currency"),
                                    alt.Tooltip("option_expiry:N", title="Option expiry"),
                                    alt.Tooltip("underlying_tenor:N", title="Swap tenor"),
                                    alt.Tooltip("value:Q", title="IR Vega", format=",.0f"),
                                ],
                            )
                            .properties(height=185)
                        )
                        labels = (
                            alt.Chart(currency_data)
                            .mark_text(
                                fontSize=14,
                                fontWeight=600,
                                color="#F8FAFC",
                                stroke="#0F172A",
                                strokeWidth=1,
                            )
                            .encode(
                                x=alt.X(
                                    "underlying_tenor:N",
                                    sort=surface_result["underlying_tenors"],
                                ),
                                y=alt.Y(
                                    "option_expiry:N",
                                    sort=surface_result["option_expiries"],
                                ),
                                text=alt.Text("value:Q", format=",.0f"),
                            )
                        )
                        st.altair_chart(cells + labels)
        st.caption(
            "Each currency has its own 2 x 2 option-expiry by underlying-swap-tenor matrix. "
            "All matrices share the same symmetric color scale, so color intensity is comparable. "
            "The V27 prototype preserves each currency's source Vega; production feeds should provide native surface nodes."
        )

    lower_charts = st.columns(2)
    with lower_charts[0]:
        with st.container(border=True, height="stretch"):
            st.subheader("FX Delta (EUR / 1% spot)")
            fx_chart = (
                alt.Chart(fx_frame)
                .mark_bar()
                .encode(
                    x=alt.X("curve:N", title="FX pair", sort=None),
                    y=alt.Y("value:Q", title="EUR / 1% spot", scale=alt.Scale(zero=True)),
                    color=alt.Color("currency:N", title="FX pair"),
                    tooltip=[
                        alt.Tooltip("curve:N", title="FX pair"),
                        alt.Tooltip("value:Q", title="FX Delta", format=",.0f"),
                    ],
                )
                .properties(height=290)
            )
            st.altair_chart(fx_chart)
    with lower_charts[1]:
        with st.container(border=True, height="stretch"):
            st.subheader("Theta (EUR / day)")
            theta_chart = (
                alt.Chart(theta_frame)
                .mark_bar()
                .encode(
                    x=alt.X("currency:N", title="Currency", sort=currency_domain),
                    y=alt.Y("value:Q", title="EUR / day", scale=alt.Scale(zero=True)),
                    color=alt.Color(
                        "currency:N",
                        title="Currency",
                        scale=alt.Scale(domain=currency_domain, range=currency_range),
                    ),
                    tooltip=[
                        alt.Tooltip("currency:N", title="Currency"),
                        alt.Tooltip("value:Q", title="Theta", format=",.0f"),
                    ],
                )
                .properties(height=290)
            )
            st.altair_chart(theta_chart)

    st.caption(
        "IR Delta is DV01 per +1 bp move at each curve-tenor node. Net and Gross Delta controls "
        "are evaluated separately by currency. IR Vega is displayed as separate currency surfaces. "
        "FX Delta is measured per +1% move in the quoted pair."
    )
elif page == "Stress":
    st.header("Stress")
    st.caption("Risk-engine-supplied scenario revaluation P&L only. Negative values represent losses versus the base valuation.")
    st.info(stress_evolution["usage_note"], icon=":material/info:")

    latest_stress = stress_frame.iloc[-1].drop(labels="cob_date").sort_values()
    scenario_names = [column for column in stress_frame.columns if column != "cob_date"]
    material_evaluation = v27.get_material_stress_scenarios(selected_as_of_date)
    stress_limit_monitor = v27.get_stress_limit_monitor(selected_as_of_date)
    stress_limit_table = pd.DataFrame(stress_limit_monitor["scenarios"])
    material_defaults = material_evaluation["selected_scenarios"]

    with st.container(border=True):
        st.subheader("Material stress evolution")
        selected_scenarios = st.multiselect(
            "Priced scenarios to display",
            scenario_names,
            default=material_defaults,
            key="v27_stress_scenarios",
        )
        st.caption(material_evaluation["rule"])
        if selected_scenarios:
            chart_wide = stress_frame[["cob_date"] + selected_scenarios].copy()
            chart_long = chart_wide.melt("cob_date", var_name="scenario", value_name="impact")
            chart_long["category"] = chart_long["scenario"].map(lambda name: stress_metadata[name]["type"])
            lines = (
                alt.Chart(chart_long)
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("cob_date:T", title="Business date", axis=alt.Axis(format="%d/%m")),
                    y=alt.Y("impact:Q", title="P&L impact (EUR)", scale=alt.Scale(zero=False)),
                    color=alt.Color("scenario:N", title="Scenario"),
                    strokeDash=alt.StrokeDash("category:N", title="Category"),
                    tooltip=[
                        alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"),
                        alt.Tooltip("scenario:N", title="Scenario"),
                        alt.Tooltip("category:N", title="Category"),
                        alt.Tooltip("impact:Q", title="P&L impact", format=",.0f"),
                    ],
                )
            )
            last_date = chart_long["cob_date"].max()
            endpoints = chart_long.loc[chart_long["cob_date"] == last_date]
            endpoint_points = (
                alt.Chart(endpoints)
                .mark_point(filled=True, size=65)
                .encode(
                    x="cob_date:T",
                    y="impact:Q",
                    color=alt.Color("scenario:N", legend=None),
                )
            )
            endpoint_labels = (
                alt.Chart(endpoints)
                .mark_text(align="left", dx=7, fontSize=11)
                .encode(
                    x="cob_date:T",
                    y="impact:Q",
                    text=alt.Text("scenario:N"),
                    color=alt.Color("scenario:N", legend=None),
                )
            )
            st.altair_chart((lines + endpoint_points + endpoint_labels).properties(height=410))
        else:
            st.info("Select at least one priced scenario.", icon=":material/info:")

    material_table = pd.DataFrame(material_evaluation["scenario_metrics"])
    if not material_table.empty:
        material_table[["latest_impact", "latest_jump"]] = material_table[["latest_impact", "latest_jump"]] * allocation_weight
        material_table = material_table.merge(
            stress_limit_table[["scenario", "limit", "consumption_pct", "status"]],
            on="scenario",
            how="left",
        )
        material_table["limit"] = material_table["limit"] * allocation_weight
        with st.container(border=True):
            st.subheader("Why these curves are material")
            st.dataframe(
                material_table,
                hide_index=True,
                column_order=["scenario", "category", "latest_impact", "latest_jump", "limit", "consumption_pct", "status", "selection_reason"],
                column_config={
                    "scenario": "Scenario",
                    "category": "Category",
                    "latest_impact": st.column_config.NumberColumn("Current P&L impact", format="%.0f"),
                    "latest_jump": st.column_config.NumberColumn("Latest jump", format="%.0f"),
                    "limit": st.column_config.NumberColumn("Loss limit", format="%.0f"),
                    "consumption_pct": st.column_config.ProgressColumn("Consumption", format="%.1f%%", min_value=0, max_value=120),
                    "status": "Limit status",
                    "selection_reason": "Selection reason",
                },
            )

    worst_scenario, worst_impact = latest_stress.index[0], latest_stress.iloc[0]
    previous_stress = stress_frame.iloc[-2].drop(labels="cob_date") if len(stress_frame) > 1 else latest_stress
    deterioration = (latest_stress - previous_stress).sort_values().iloc[0]
    with st.container(horizontal=True):
        st.metric("Most adverse scenario", worst_scenario, amount(worst_impact), border=True)
        st.metric("Largest day-on-day deterioration", amount(deterioration), border=True)
        st.metric("Priced scenarios", len(latest_stress), border=True)
        st.metric("Governed categories", 4, border=True)

    with st.container(border=True):
        st.subheader("Scenario definitions and current impacts")
        limit_lookup = stress_limit_table.set_index("scenario")
        stress_table = pd.DataFrame({
            "Scenario": latest_stress.index,
            "Category": [stress_metadata[name]["type"] for name in latest_stress.index],
            "Current P&L impact": latest_stress.values,
            "Loss limit": [limit_lookup.loc[name, "limit"] * allocation_weight for name in latest_stress.index],
            "Consumption": [limit_lookup.loc[name, "consumption_pct"] for name in latest_stress.index],
            "Limit status": [limit_lookup.loc[name, "status"] for name in latest_stress.index],
            "Definition": [stress_metadata[name]["definition"] for name in latest_stress.index],
        })
        st.dataframe(
            stress_table,
            hide_index=True,
            column_config={
                "Current P&L impact": st.column_config.NumberColumn(format="%.0f"),
                "Loss limit": st.column_config.NumberColumn(format="%.0f"),
                "Consumption": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=120),
            },
        )

    with st.expander("Scenario catalogue, including Extreme configurations", icon=":material/assignment:"):
        scenario_catalog = pd.DataFrame(v27.get_stress_scenario_catalog())
        scenario_catalog["limit"] = scenario_catalog["limit"] * allocation_weight
        st.dataframe(
            scenario_catalog,
            hide_index=True,
            column_order=["scenario", "category", "shock", "limit", "limit_unit", "derived_from", "pricing_status"],
            column_config={
                "scenario": "Scenario",
                "category": "Category",
                "shock": "Shock / definition",
                "limit": st.column_config.NumberColumn("Loss limit", format="%.0f"),
                "limit_unit": "Limit unit",
                "derived_from": "Adverse counterpart",
                "pricing_status": "Pricing status",
            },
        )
        st.caption(stress_limit_monitor["usage_note"])
        st.warning(
            "Extreme shock parameters are exactly 2× the corresponding adverse parameters. "
            "Their P&L is intentionally blank until the risk engine performs a full nonlinear revaluation.",
            icon=":material/warning:",
        )
elif page == "Controls":
    st.header("Controls")
    limit_evaluation = v27.evaluate_all_limits()
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
    daily_brief = v27.generate_daily_risk_brief(selected_as_of_date)
    daily_actions = pd.DataFrame(daily_brief["actions"])
    with st.container(border=True):
        st.subheader("Daily risk brief and action queue")
        with st.container(horizontal=True):
            st.metric("Daily status", daily_brief["overall_status"], border=True)
            st.metric("Open actions", daily_brief["sign_off"]["open_actions"], border=True)
            st.metric("Sign-off", daily_brief["sign_off"]["status"], border=True)
            st.metric("Required role", daily_brief["sign_off"]["required_role"], border=True)
        if daily_brief["overall_status"] == "ESCALATION REQUIRED":
            st.error(daily_brief["headline"], icon=":material/error:")
        elif daily_brief["overall_status"] == "REVIEW REQUIRED":
            st.warning(daily_brief["headline"], icon=":material/warning:")
        else:
            st.info(daily_brief["headline"], icon=":material/info:")
        if not daily_actions.empty:
            st.dataframe(
                daily_actions,
                hide_index=True,
                column_order=[
                    "action_id", "priority", "source", "finding", "owner",
                    "required_action", "workflow_status", "due",
                ],
                column_config={
                    "action_id": "Action ID",
                    "priority": "Priority",
                    "source": "Source",
                    "finding": "Finding",
                    "owner": "Owner",
                    "required_action": "Required action",
                    "workflow_status": "Workflow status",
                    "due": "Due",
                },
            )
        st.caption(daily_brief["usage_note"])
    materiality = v27.detect_material_risk_movements(selected_as_of_date)
    materiality_frame = pd.DataFrame(materiality["findings"])
    with st.container(border=True):
        st.subheader("Material risk movements")
        with st.container(horizontal=True):
            st.metric("Critical", materiality["summary"]["critical"], border=True)
            st.metric("High", materiality["summary"]["high"], border=True)
            st.metric("Medium", materiality["summary"]["medium"], border=True)
            st.metric("Findings", materiality["finding_count"], border=True)
        if materiality_frame.empty:
            st.success("No material movement crossed a configured threshold.", icon=":material/check_circle:")
        else:
            st.dataframe(
                materiality_frame,
                hide_index=True,
                column_order=["severity", "source", "finding", "observed", "threshold", "unit", "action"],
                column_config={
                    "severity": "Severity",
                    "source": "Source",
                    "finding": "Finding",
                    "observed": st.column_config.NumberColumn("Observed", format="%.1f"),
                    "threshold": st.column_config.NumberColumn("Threshold", format="%.1f"),
                    "unit": "Unit",
                    "action": "Required review",
                },
            )
        st.caption(materiality["usage_note"])
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
        pnl_alert_evaluation = v27.evaluate_pnl_explain_alerts()
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
            answer = None
            with st.status("Running the risk investigation...", expanded=True) as status:
                try:
                    answer = v27.ask_risk_agent(question)
                except Exception as error:
                    status.update(label="Investigation could not be completed", state="error")
                    st.error(str(error), icon=":material/error:")
                else:
                    status.update(label="Investigation complete", state="complete", expanded=False)
            if answer is not None:
                st.session_state.risk_agent_messages.append({"role": "assistant", "content": answer})
                with st.chat_message("assistant", avatar=":material/analytics:"):
                    st.markdown(answer)
    with st.expander("Recent investigation memory", icon=":material/history:"):
        memory = v27.v9.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.", icon=":material/info:")
