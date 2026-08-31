# OpenGamma public knowledge map

Last reviewed: 2026-08-30

## Purpose and scope

This is a living map of OpenGamma's public material that is relevant to M.R. AI Agent. It is not a claim that every public webpage, source line, or historical paper has been permanently absorbed. OpenGamma's public corpus changes over time, and some material describes commercial margin services rather than market-risk management.

The preferred source order is:

1. Current Strata reference documentation and Javadoc.
2. Current Strata source code, tests, examples, and release notes.
3. OpenGamma Quant Research papers.
4. Public Margin API and Java SDK documentation where relevant.
5. Archived OG-Platform and OpenSIMM material for historical context only.

## Official source inventory

### Strata documentation

- Home: https://strata.opengamma.io/
- Reference documentation: https://strata.opengamma.io/docs/
- Javadoc package index: https://strata.opengamma.io/apidocs/
- Calculation flow: https://strata.opengamma.io/calculation_flow/
- Market data: https://strata.opengamma.io/market_data/
- Reference data: https://strata.opengamma.io/reference_data/
- Product model: https://strata.opengamma.io/product_model/
- Loaders: https://strata.opengamma.io/loaders/
- Curve sensitivity CSV loader: https://strata.opengamma.io/sensitivity_loader/
- Extending scenarios: https://strata.opengamma.io/extend_scenario_framework/
- Adding measures: https://strata.opengamma.io/add_measure/
- Swaption model: https://strata.opengamma.io/swaption/
- Quant research index: https://strata.opengamma.io/quant_research/

### Source code and examples

- Strata: https://github.com/OpenGamma/Strata
- Strata examples: https://github.com/OpenGamma/Strata/tree/main/examples
- Strata documentation source: https://github.com/OpenGamma/StrataDocs
- Strata extras: https://github.com/OpenGamma/Strata-Extras
- OpenGamma organisation: https://github.com/OpenGamma

### Public commercial API material

- Margin REST API documentation: https://docs.opengamma.com/
- Java SDK: https://github.com/OpenGamma/JavaSDK

This material is useful for asynchronous calculation requests, portfolio-file ingestion, job status, result schemas, authentication boundaries, and what-if workflows. It is not the primary authority for VaR, PLA, FRTB market-risk governance, or the internal design of a bank's risk platform.

### Historical material

- OG-Platform archive: https://github.com/OpenGamma/OG-Platform
- OpenSIMM archive: https://github.com/OpenGamma/OpenSIMM

Use these only when a concept is absent from current Strata. Do not copy obsolete architecture into the prototype without a current justification.

## Core model learned from Strata

### Separation of concerns

Strata separates:

- product and trade definitions;
- slowly changing reference data;
- observable and calibrated market data;
- calculation targets, measures, rules, and parameters;
- scenario definitions and perturbations;
- calculation execution and failure capture;
- calculation result grids;
- report transformation for user-facing tables or files.

For M.R. AI Agent, this implies that ingestion, validation, risk results, controls, presentation, and LLM explanation should be separate layers.

### Calculation flow

The official flow is:

1. Choose trades, requested measure columns, and calculation rules.
2. Derive market-data requirements.
3. source or build market data and calibrate derived structures.
4. Optionally create scenario market data through perturbations.
5. Run calculations to produce trade-by-measure results.
6. Transform nested results into purpose-specific reports.

The stages can run together or be persisted between stages. This supports the project's run-ID model: each stage should have lineage, status, validation evidence, and immutable output references.

### Data domains

- **Trade/product data:** economic terms and transaction metadata.
- **Reference data:** holidays, security identifiers, calendars, conventions, and other slowly changing information.
- **Market data:** quotes, prices, fixings, FX rates, calibrated curves, and volatility surfaces tied to a valuation date.
- **Scenario market data:** one or many related market-data states indexed by scenario.
- **Risk results:** values derived from both portfolio and market data, such as PV and PV01; these are not themselves market data.

### Sensitivities

OpenGamma distinguishes point sensitivities from parameter or market-quote sensitivities. Bucketed PV01 is a sensitivity to the market quotes used to calibrate affected curves, returned by curve, currency, and parameter bucket. Curve sensitivity files can encode sensitivity type, curve reference, tenor/date, currency, and value in list or grid form.

Implications for the prototype:

- Keep signed Net Delta and absolute Gross Delta as distinct aggregations.
- Store node-level values before aggregating them.
- Identify curve, curve family, currency, tenor/date, sensitivity type, unit, and reporting currency.
- State whether a number is point, parameter, or market-quote sensitivity.
- Gamma may be a vector of diagonal second-order sensitivities or a cross-gamma matrix; a single total is only a reporting summary.
- Vega should retain the dimensions of its volatility structure. For swaptions, the natural base view is option expiry by underlying swap tenor, with strike or moneyness as an additional smile dimension when available.

### Scenarios and stress

Strata scenarios apply filters and perturbations to market data, then run the same calculations over each resulting state. A scenario is therefore more than a name and a final P&L: it should have an identifier, targeted market-data objects, perturbation type, shock magnitude, units, calibration/rebuild policy, ordering, and provenance.

For the prototype, final revaluation P&L may still be ingested from an external engine, but the scenario catalogue should preserve those definitions and lineage.

### Reporting

Calculation results are often nested and unsuitable for direct display. A reporting layer extracts and formats a purpose-specific table. This supports the current design principle that the dashboard and LLM should query curated risk views rather than raw pricer objects or files.

## Quant research routing

The public research index includes market conventions, multi-curve construction, calibration, algorithmic differentiation, local volatility, swaption pricing, FX smiles, inflation, credit, interpolation, and sensitivity computation.

Priority for this project:

1. Interest-rate instruments and market conventions.
2. Multi-curve construction and collateral.
3. Curve calibration and sensitivity computation.
4. Swaption pricing and volatility-smile material.
5. FX option vanilla and smile material.
6. Inflation curve and option material.
7. AAD/calibration papers for scalable Greeks.
8. Credit material when the product scope expands.

## Design decisions for future versions

- Introduce canonical entities for `RiskRun`, `Trade`, `Book`, `Desk`, `BusinessLine`, `MarketDataSnapshot`, `ScenarioDefinition`, `RiskMeasure`, `SensitivityNode`, `Limit`, and `ControlResult`.
- Treat `as_of_date`, `run_id`, `market_data_snapshot_id`, `scenario_set_id`, `model_version`, `source_system`, and `reporting_currency` as first-class lineage fields.
- Separate raw ingestion tables from validated and curated risk views.
- Preserve calculation failures and missing-data diagnostics instead of silently dropping rows.
- Give deterministic tools structured access to curated results; keep the LLM outside numerical calculation and limit evaluation.
- Extend IR Vega from the V26 2 x 2 demonstration to native source nodes, then optionally add strike/moneyness.
- Preserve trade-level drill-down even when the dashboard initially presents book, desk, or business-line aggregates.

## Boundaries

- Strata is a pricing and market-risk analytics library, not a complete bank risk-governance operating model.
- OpenGamma's commercial Margin APIs focus on margin calculations and should not be treated as an FRTB authority.
- Basel, ECB/EBA, PRA, and internal model-governance rules require their own primary regulatory sources.
- OpenGamma examples and source code describe implementations; they do not prove that every bank uses the same architecture.
