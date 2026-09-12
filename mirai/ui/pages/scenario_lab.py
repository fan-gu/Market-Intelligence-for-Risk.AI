"""Render the Scenario Lab page."""

def render(context):
    """Render this page from the application-shell context."""
    allocation_weight = context["allocation_weight"]
    alt = context["alt"]
    amount = context["amount"]
    build_waterfall_chart = context["build_waterfall_chart"]
    pd = context["pd"]
    portfolio_df = context["portfolio_df"]
    risk = context["risk"]
    scope_label = context["scope_label"]
    select_scenario_agent_page = context["select_scenario_agent_page"]
    selected_as_of_date = context["selected_as_of_date"]
    st = context["st"]
    st.header("Scenario Lab")
    scenario_specification = risk.get_scenario_lab_specification()
    st.info(
        "Invent a market shock and watch the supplied sensitivities react instantly. "
        "This is a sensitivity approximation, not an official risk-engine revaluation.",
        icon=":material/science:",
    )

    scenario_layout = st.columns([1, 1.45], gap="large", vertical_alignment="top")
    with scenario_layout[0]:
        with st.container(border=True):
            st.subheader("Build a scenario")
            severity_label = st.segmented_control(
                "Severity",
                list(scenario_specification["severity_options"]),
                default="Adverse (1x)",
                required=True,
                width="stretch",
                key="v29_scenario_severity",
            )
            st.caption("Extreme doubles rate, FX and volatility shocks. The selected time horizon is unchanged.")
            rate_currency = st.selectbox(
                "Rates and volatility currency",
                ["All currencies"] + scenario_specification["rate_currencies"],
                index=1,
                key="v29_scenario_rate_currency",
            )
            curve_family = st.selectbox(
                "Curve family",
                ["All curve families"] + scenario_specification["curve_families"],
                key="v29_scenario_curve_family",
            )
            parallel_shift_bp = st.slider(
                "Parallel rate shift (bp)",
                min_value=-200,
                max_value=200,
                value=50,
                step=5,
                key="v29_scenario_parallel_shift",
            )
            curve_twist_bp = st.slider(
                "Curve twist (bp)",
                min_value=-100,
                max_value=100,
                value=0,
                step=5,
                help="Positive values lower the front end and raise the long end; negative values flatten the curve.",
                key="v29_scenario_curve_twist",
            )
            fx_pair = st.selectbox(
                "FX pair",
                ["All FX pairs"] + scenario_specification["fx_pairs"],
                index=1,
                key="v29_scenario_fx_pair",
            )
            fx_spot_move_pct = st.slider(
                "FX spot move (%)",
                min_value=-25,
                max_value=25,
                value=-5,
                step=1,
                key="v29_scenario_fx_move",
            )
            volatility_shift_points = st.slider(
                "IR implied-volatility change (vol points)",
                min_value=-10,
                max_value=25,
                value=5,
                step=1,
                key="v29_scenario_volatility_shift",
            )
            horizon_days = st.slider(
                "Time horizon (business days)",
                min_value=0,
                max_value=10,
                value=1,
                step=1,
                key="v29_scenario_horizon",
            )

    scenario_result = risk.run_interactive_scenario(
        rate_currency=rate_currency,
        curve_family=curve_family,
        parallel_shift_bp=parallel_shift_bp,
        curve_twist_bp=curve_twist_bp,
        fx_pair=fx_pair,
        fx_spot_move_pct=fx_spot_move_pct,
        volatility_shift_points=volatility_shift_points,
        horizon_days=horizon_days,
        severity_multiplier=scenario_specification["severity_options"][severity_label],
        allocation_weight=allocation_weight,
        scope_label=scope_label,
        as_of_date=selected_as_of_date.isoformat(),
    )
    scenario = scenario_result["scenario"]
    latest_scenario_row = portfolio_df.sort_values("cob_date").iloc[-1]
    scenario_baseline_apl = float(latest_scenario_row["actual_pnl"])
    scenario_total_pnl = scenario_baseline_apl + float(scenario["estimated_pnl"])
    scenario_agent_context = {
        **scenario_result,
        "reporting_currency": str(latest_scenario_row["reporting_currency"]),
        "current_actual_pnl": scenario_baseline_apl,
        "scenario_total_pnl": scenario_total_pnl,
        "baseline_explanation": (
            "A zero no-shock scenario impact is not Actual P&L. Current APL is supplied "
            "separately and scenario total P&L equals current APL plus estimated impact."
        ),
    }

    with scenario_layout[1]:
        with st.container(border=True):
            st.subheader("Today versus your scenario")
            with st.container(horizontal=True):
                st.metric(
                    "Current Actual P&L (APL)",
                    f"EUR {amount(scenario_baseline_apl)}",
                    border=True,
                )
                st.metric(
                    "Estimated scenario impact",
                    f"EUR {amount(scenario['estimated_pnl'])}",
                    delta="Sensitivity-based estimate",
                    border=True,
                )
                st.metric(
                    "Scenario P&L (APL + impact)",
                    f"EUR {amount(scenario_total_pnl)}",
                    border=True,
                )

            st.info(
                "Scenario Lab shows an estimated P&L impact added to the current Actual P&L (APL). "
                "It is separate from official risk-engine limit governance.",
                icon=":material/info:",
            )

            scenario_comparison = pd.DataFrame([
                {
                    "Metric": "Current Actual P&L (APL)",
                    "Today": scenario_baseline_apl,
                    "Under your scenario": scenario_baseline_apl,
                },
                {
                    "Metric": "Estimated scenario impact",
                    "Today": 0.0,
                    "Under your scenario": scenario["estimated_pnl"],
                },
                {
                    "Metric": "Scenario P&L (APL + impact)",
                    "Today": scenario_baseline_apl,
                    "Under your scenario": scenario_total_pnl,
                },
            ])
            st.dataframe(
                scenario_comparison,
                hide_index=True,
                column_config={
                    "Metric": st.column_config.TextColumn(pinned=True),
                    "Today": st.column_config.NumberColumn(format="%,.0f"),
                    "Under your scenario": st.column_config.NumberColumn(format="%,.0f"),
                },
            )
            effective = scenario_result["effective_shocks"]
            st.caption(
                f"{scenario_result['scenario_id']} · {scope_label} · "
                f"effective parallel shift {effective['parallel_shift_bp']:+.0f} bp · "
                f"twist {effective['curve_twist_bp']:+.0f} bp · "
                f"FX {effective['fx_spot_move_pct']:+.0f}% · "
                f"IR volatility {effective['volatility_shift_points']:+.0f} points"
            )

    component_frame = pd.DataFrame(scenario_result["component_contributions"])
    contribution_layout = st.columns(2, gap="medium")
    with contribution_layout[0]:
        with st.container(border=True, height="stretch"):
            st.subheader("Estimated P&L bridge")
            if component_frame["estimated_pnl"].abs().sum() == 0:
                st.info("Move a shock control to create an estimated P&L impact.", icon=":material/info:")
            else:
                component_contributions = [
                    (row["component"], row["estimated_pnl"], "Risk factor")
                    for row in scenario_result["component_contributions"]
                ]
                st.altair_chart(
                    build_waterfall_chart(
                        component_contributions,
                        "Estimated P&L",
                        scenario["estimated_pnl"],
                    ),
                    width="stretch",
                )
    with contribution_layout[1]:
        with st.container(border=True, height="stretch"):
            st.subheader("Contribution by currency")
            currency_contributions = pd.DataFrame(scenario_result["currency_contributions"])
            if currency_contributions.empty:
                st.info("No non-zero sensitivity population is available for this selection.", icon=":material/info:")
            else:
                currency_chart = (
                    alt.Chart(currency_contributions)
                    .mark_bar()
                    .encode(
                        x=alt.X("currency:N", title="Currency"),
                        y=alt.Y("estimated_pnl:Q", title="Estimated P&L (EUR)"),
                        color=alt.Color("component:N", title="Component"),
                        tooltip=[
                            alt.Tooltip("currency:N", title="Currency"),
                            alt.Tooltip("component:N", title="Component"),
                            alt.Tooltip("estimated_pnl:Q", title="Estimated P&L", format=",.0f"),
                        ],
                    )
                    .properties(height=390)
                )
                st.altair_chart(currency_chart, width="stretch")

    with st.container(border=True):
        st.subheader("Largest sensitivity contributions")
        top_contributors = pd.DataFrame(scenario_result["top_contributors"])
        if top_contributors.empty:
            st.info("No sensitivity contributions are available for this selection.", icon=":material/info:")
        else:
            st.dataframe(
                top_contributors,
                hide_index=True,
                column_order=[
                    "component", "currency", "curve_family", "curve", "tenor",
                    "applied_shock", "estimated_pnl",
                ],
                column_config={
                    "component": "Component",
                    "currency": "Currency",
                    "curve_family": "Curve family",
                    "curve": "Curve",
                    "tenor": "Tenor / surface node",
                    "applied_shock": "Applied shock",
                    "estimated_pnl": st.column_config.NumberColumn("Estimated P&L", format="%,.0f"),
                },
            )

    with st.expander("Methodology and limitations", icon=":material/rule:"):
        st.write(scenario_result["methodology"])
        for assumption in scenario_result["assumptions"]:
            st.markdown(f"- {assumption}")
        st.warning(scenario_result["governance_note"], icon=":material/warning:")

    st.button(
        "Ask MIRAI about this scenario",
        icon=":material/auto_awesome:",
        type="primary",
        width="stretch",
        on_click=select_scenario_agent_page,
        args=(scenario_agent_context,),
        key="v29_scenario_agent_button",
    )

