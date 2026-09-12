"""Render the Stress page."""

def render(context):
    """Render this page from the application-shell context."""
    allocation_weight = context["allocation_weight"]
    alt = context["alt"]
    pd = context["pd"]
    risk = context["risk"]
    st = context["st"]
    stress_frame = context["stress_frame"]
    stress_metadata = context["stress_metadata"]
    stress_numeric = context["stress_numeric"]
    st.header("Stress")
    st.caption("Risk-engine-supplied scenario revaluation P&L only. Negative values represent losses versus the base valuation.")
    st.info("The supplied demo extract contains historical, hypothetical, adverse and extreme full-revaluation scenario results.", icon=":material/info:")

    scenario_names = [column for column in stress_frame.columns if column != "cob_date"]
    latest_stress_row = stress_frame.iloc[-1]
    previous_stress_row = stress_frame.iloc[-2] if len(stress_frame) > 1 else None
    weekly_candidates = stress_frame.loc[
        stress_frame["cob_date"] <= latest_stress_row["cob_date"] - pd.Timedelta(days=7)
    ]
    monthly_candidates = stress_frame.loc[
        stress_frame["cob_date"] <= latest_stress_row["cob_date"] - pd.DateOffset(months=1)
    ]
    weekly_stress_row = None if weekly_candidates.empty else weekly_candidates.iloc[-1]
    monthly_stress_row = None if monthly_candidates.empty else monthly_candidates.iloc[-1]
    stress_movement_rows = []
    stress_limit_rows = []
    for scenario in stress_numeric:
        current_impact = float(latest_stress_row[scenario])
        scenario_limit = float(risk.STRESS_SCENARIO_LIMITS[scenario]) * allocation_weight
        consumption = 0.0 if scenario_limit == 0 else abs(min(current_impact, 0.0)) / scenario_limit * 100.0
        status = "BREACH" if consumption >= 100.0 else "WARNING" if consumption >= 80.0 else "OK"
        stress_movement_rows.append({
            "scenario": scenario,
            "category": stress_metadata[scenario]["type"],
            "latest_impact": current_impact,
            "daily_move": None if previous_stress_row is None else current_impact - float(previous_stress_row[scenario]),
            "weekly_move": None if weekly_stress_row is None else current_impact - float(weekly_stress_row[scenario]),
            "monthly_move": None if monthly_stress_row is None else current_impact - float(monthly_stress_row[scenario]),
            "definition": stress_metadata[scenario]["definition"],
        })
        stress_limit_rows.append({
            "scenario": scenario, "category": stress_metadata[scenario]["type"],
            "impact": current_impact, "limit": scenario_limit,
            "consumption_pct": consumption, "status": status,
        })
    stress_movements = pd.DataFrame(stress_movement_rows)
    stress_limit_table = pd.DataFrame(stress_limit_rows)
    stress_limit_monitor = {
        "scenarios": stress_limit_rows,
        "usage_note": "Selected-perimeter scenario limits use 80% for warning and 100% for breach.",
    }
    movement_scores = stress_movements.copy()
    movement_scores["magnitude_score"] = movement_scores["latest_impact"].abs() / max(movement_scores["latest_impact"].abs().max(), 1.0)
    movement_scores["move_score"] = movement_scores["daily_move"].abs() / max(movement_scores["daily_move"].abs().max(), 1.0)
    material_defaults = movement_scores.assign(attention_score=movement_scores["magnitude_score"] + movement_scores["move_score"]).nlargest(10, "attention_score")["scenario"].tolist()

    with st.container(border=True):
        st.subheader("Top 10 stress evolutions")
        selected_scenarios = st.multiselect(
            "Priced scenarios to display",
            scenario_names,
            default=material_defaults,
            key="v30_stress_scenarios",
        )
        if selected_scenarios:
            chart_wide = stress_frame[["cob_date"] + selected_scenarios].copy()
            chart_long = chart_wide.melt("cob_date", var_name="scenario", value_name="impact")
            chart_long["category"] = chart_long["scenario"].map(lambda name: stress_metadata[name]["type"])
            lines = (
                alt.Chart(chart_long)
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("cob_date:T", title="Business date", axis=alt.Axis(format="%b", tickCount=12)),
                    y=alt.Y("impact:Q", title="P&L impact (EUR)", scale=alt.Scale(zero=False)),
                    color=alt.Color(
                        "category:N",
                        title="Category",
                        scale=alt.Scale(
                            domain=["Historical", "Hypothetical", "Adverse", "Extreme"],
                            range=["#60A5FA", "#A78BFA", "#F59E0B", "#F87171"],
                        ),
                        legend=alt.Legend(orient="bottom"),
                    ),
                    strokeDash=alt.StrokeDash("scenario:N", title=None, legend=None),
                    tooltip=[alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"), alt.Tooltip("scenario:N", title="Scenario"), alt.Tooltip("category:N", title="Category"), alt.Tooltip("impact:Q", title="P&L impact", format=",.0f")],
                )
            )
            last_date = chart_long["cob_date"].max()
            endpoints = chart_long.loc[chart_long["cob_date"] == last_date]
            endpoint_points = alt.Chart(endpoints).mark_point(filled=True, size=65).encode(x="cob_date:T", y="impact:Q", color=alt.Color("category:N", scale=alt.Scale(domain=["Historical", "Hypothetical", "Adverse", "Extreme"], range=["#60A5FA", "#A78BFA", "#F59E0B", "#F87171"]), legend=None))
            endpoint_labels = alt.Chart(endpoints).mark_text(align="left", dx=7, fontSize=11).encode(x="cob_date:T", y="impact:Q", text=alt.Text("scenario:N"), color=alt.Color("category:N", scale=alt.Scale(domain=["Historical", "Hypothetical", "Adverse", "Extreme"], range=["#60A5FA", "#A78BFA", "#F59E0B", "#F87171"]), legend=None))
            st.altair_chart((lines + endpoint_points + endpoint_labels).properties(height=430), key="stress_evolution")
        else:
            st.info("Select at least one priced scenario.", icon=":material/info:")

    with st.container(border=True):
        st.subheader("Scenario definitions and current impacts")
        limit_lookup = stress_limit_table.set_index("scenario")
        movement_lookup = stress_movements.set_index("scenario")
        latest_stress = stress_frame.iloc[-1].drop(labels="cob_date").sort_values()
        stress_table = pd.DataFrame({
            "Scenario": latest_stress.index,
            "Category": [stress_metadata[name]["type"] for name in latest_stress.index],
            "Stressed P&L": latest_stress.values,
            "Daily move": [movement_lookup.loc[name, "daily_move"] for name in latest_stress.index],
            "Weekly move": [movement_lookup.loc[name, "weekly_move"] for name in latest_stress.index],
            "Monthly move": [movement_lookup.loc[name, "monthly_move"] for name in latest_stress.index],
            "Limit": [limit_lookup.loc[name, "limit"] for name in latest_stress.index],
            "Consumption": [limit_lookup.loc[name, "consumption_pct"] for name in latest_stress.index],
            "Status": [limit_lookup.loc[name, "status"] for name in latest_stress.index],
            "Definition": [stress_metadata[name]["definition"] for name in latest_stress.index],
        })
        st.dataframe(
            stress_table,
            hide_index=True,
            column_config={
                "Stressed P&L": st.column_config.NumberColumn(format="%,.0f"),
                "Daily move": st.column_config.NumberColumn(format="%,.0f"),
                "Weekly move": st.column_config.NumberColumn(format="%,.0f"),
                "Monthly move": st.column_config.NumberColumn(format="%,.0f"),
                "Limit": st.column_config.NumberColumn(format="%,.0f"),
                "Consumption": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=120),
            },
        )

    with st.expander("Scenario catalogue", icon=":material/assignment:"):
        scenario_catalog = pd.DataFrame(risk.get_stress_scenario_catalog())
        scenario_catalog["limit"] = scenario_catalog["limit"] * allocation_weight
        st.dataframe(
            scenario_catalog,
            hide_index=True,
            column_order=["scenario", "category", "shock", "limit", "limit_unit", "derived_from", "pricing_status"],
            column_config={
                "scenario": "Scenario",
                "category": "Category",
                "shock": "Shock / definition",
                "limit": st.column_config.NumberColumn("Limit", format="%,.0f"),
                "limit_unit": "Limit unit",
                "derived_from": "Adverse counterpart",
                "pricing_status": "Pricing status",
            },
        )
        st.caption(stress_limit_monitor["usage_note"])

