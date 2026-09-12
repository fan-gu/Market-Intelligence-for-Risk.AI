"""Render the Sensitivities page."""

from html import escape


def render(context):
    """Render this page from the application-shell context."""
    allocation_weight = context["allocation_weight"]
    alt = context["alt"]
    amount = context["amount"]
    pd = context["pd"]
    risk = context["risk"]
    st = context["st"]
    st.header("Sensitivities")
    sensitivities = risk.get_market_sensitivities()
    sensitivity_frame = pd.DataFrame(sensitivities["sensitivities"])
    sensitivity_frame["value"] = sensitivity_frame["value"] * allocation_weight

    selected_currencies = st.multiselect(
        "Rates and Theta currencies",
        sensitivities["currencies"],
        default=sensitivities["currencies"],
        key="v29_sensi_currencies",
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
        st.metric("IR Vega (EUR / vol point)", amount(vega.sum()), border=True)
        st.metric("FX Delta (EUR / 1% spot)", amount(fx_frame["value"].abs().sum()), border=True)
        st.metric("Theta (EUR / day)", amount(theta_frame["value"].sum()), border=True)

    currency_domain = ["EUR", "USD", "JPY", "GBP", "CHF", "AUD", "HKD", "CNY"]
    currency_range = ["#2F6BFF", "#E07A5F", "#22A06B", "#8B5CF6", "#60A5FA", "#FB7185", "#F59E0B", "#14B8A6"]

    with st.container(border=True):
        st.subheader("IR Delta by curve and tenor (EUR / bp)")
        delta_result = risk.get_delta_curve_tenor_summary(selected_currencies)
        tenor_order = delta_result["tenors"]
        delta_table = pd.DataFrame(delta_result["rows"])
        scaled_columns = tenor_order + ["net_delta", "gross_delta"]
        delta_table[scaled_columns] = delta_table[scaled_columns] * allocation_weight

        controlled_mask = delta_table["net_limit"].notna()
        delta_table.loc[controlled_mask, "net_pct"] = (
            delta_table.loc[controlled_mask, "net_delta"].abs()
            / delta_table.loc[controlled_mask, "net_limit"]
            * 100.0
        )
        delta_table.loc[controlled_mask, "gross_pct"] = (
            delta_table.loc[controlled_mask, "gross_delta"]
            / delta_table.loc[controlled_mask, "gross_limit"]
            * 100.0
        )

        delta_table["curve_display"] = delta_table.apply(
            lambda row: (
                str(row["curve"])
                if row["row_type"] == "Currency subtotal"
                else f'{row["curve_type"]} | {row["curve"]}'
            ),
            axis=1,
        )

        delta_display_columns = (
            ["currency", "curve_display"]
            + tenor_order
            + [
                "net_delta", "net_limit", "net_pct",
                "gross_delta", "gross_limit", "gross_pct",
            ]
        )
        delta_headers = {
            "currency": "Currency",
            "curve_display": "Curve",
            **{tenor: tenor for tenor in tenor_order},
            "net_delta": "Net Delta",
            "net_limit": "Limit",
            "net_pct": "%",
            "gross_delta": "Gross Delta",
            "gross_limit": "Limit",
            "gross_pct": "%",
        }
        percentage_columns = {"net_pct", "gross_pct"}
        text_columns = {"currency", "curve_display"}

        def format_delta_cell(column, value):
            if pd.isna(value) or value == "":
                return ""
            if column in text_columns:
                return escape(str(value))
            if column in percentage_columns:
                return f"{float(value):.1f}%"
            return f"{float(value):,.0f}"

        delta_html_rows = []
        for delta_row in delta_table.to_dict("records"):
            row_class = "currency-subtotal" if delta_row["row_type"] == "Currency subtotal" else "curve-row"
            cells = "".join(
                f"<td>{format_delta_cell(column, delta_row[column])}</td>"
                for column in delta_display_columns
            )
            delta_html_rows.append(f'<tr class="{row_class}">{cells}</tr>')
            if delta_row["row_type"] == "Currency subtotal":
                delta_html_rows.append(
                    f'<tr class="currency-gap"><td colspan="{len(delta_display_columns)}"></td></tr>'
                )

        delta_header_html = "".join(
            f"<th>{escape(delta_headers[column])}</th>"
            for column in delta_display_columns
        )
        delta_table_html = f"""
        <style>
            .delta-risk-wrap {{
                max-height: 610px;
                overflow-y: auto;
                overflow-x: hidden;
                border: 1px solid #334155;
                border-radius: 7px;
            }}
            .delta-risk-table {{
                width: 100%;
                min-width: 0;
                table-layout: fixed;
                border-collapse: separate;
                border-spacing: 0;
                color: #E5E7EB;
                font-family: Inter, Arial, sans-serif;
                font-size: 0.67rem;
            }}
            .delta-risk-table th {{
                position: sticky;
                top: 0;
                z-index: 2;
                padding: 5px 3px;
                background: #1E293B;
                border-bottom: 1px solid #475569;
                text-align: right;
                white-space: nowrap;
            }}
            .delta-risk-table td {{
                padding: 5px 3px;
                border-bottom: 1px solid #263449;
                background: #111827;
                text-align: right;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .delta-risk-table th:nth-child(-n+2),
            .delta-risk-table td:nth-child(-n+2) {{ text-align: left; }}
            .delta-risk-table th:nth-child(1),
            .delta-risk-table td:nth-child(1) {{ width: 4%; }}
            .delta-risk-table th:nth-child(2),
            .delta-risk-table td:nth-child(2) {{ width: 10%; }}
            .delta-risk-table tr.currency-subtotal td {{
                background: #24324A;
                border-top: 1px solid #60A5FA;
                font-weight: 700;
            }}
            .delta-risk-table tr.currency-gap td {{
                height: 14px;
                padding: 0;
                border: 0;
                background: #0F172A;
            }}
        </style>
        <div class="delta-risk-wrap">
            <table class="delta-risk-table">
                <thead><tr>{delta_header_html}</tr></thead>
                <tbody>{''.join(delta_html_rows)}</tbody>
            </table>
        </div>
        """
        st.html(delta_table_html)
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
        surface_result = risk.get_ir_vega_surface(selected_currencies)
        surface_frame = pd.DataFrame(surface_result["surface"])
        surface_frame["value"] = surface_frame["value"] * allocation_weight
        currency_surface = (
            surface_frame.groupby(
                ["currency", "option_expiry", "underlying_tenor"],
                as_index=False,
            )["value"]
            .sum()
        )
        surface_order = [
            currency for currency in currency_domain if currency in selected_currencies
        ]

        for row_start in range(0, len(surface_order), 4):
            surface_columns = st.columns(4, gap="small")
            for offset, currency in enumerate(surface_order[row_start:row_start + 4]):
                with surface_columns[offset]:
                    with st.container(border=True):
                        st.markdown(f"**{currency}**")
                        currency_data = currency_surface.loc[
                            currency_surface["currency"] == currency
                        ].copy()
                        currency_scale = max(float(currency_data["value"].abs().max()), 1.0)
                        cells = (
                            alt.Chart(currency_data)
                            .mark_rect(cornerRadius=4)
                            .encode(
                                x=alt.X(
                                    "underlying_tenor:N",
                                    title=None,
                                    sort=surface_result["underlying_tenors"],
                                    axis=alt.Axis(labelAngle=0),
                                ),
                                y=alt.Y(
                                    "option_expiry:N",
                                    title=None,
                                    sort=surface_result["option_expiries"],
                                ),
                                color=alt.Color(
                                    "value:Q",
                                    title=None,
                                    scale=alt.Scale(
                                        scheme="redblue",
                                        domain=[-currency_scale, currency_scale],
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
                            .properties(height=155)
                        )
                        labels = (
                            alt.Chart(currency_data)
                            .mark_text(
                                font="Arial",
                                fontSize=13,
                                fontWeight=700,
                                color="#F8FAFC",
                                stroke="#0F172A",
                                strokeWidth=1.6,
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
                        st.altair_chart(cells + labels, width="stretch")
        st.caption(
            "Each currency has its own 2 x 2 option-expiry by underlying-swap-tenor matrix. "
            "Each matrix uses a local symmetric color scale so all four cells remain legible. "
            "The MIRAI demo preserves each currency's source Vega; production feeds should provide native surface nodes."
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
