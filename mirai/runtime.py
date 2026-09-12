# ruff: noqa: F401
"""Public production API for MIRAI V33.

The dashboard and API import this facade only. Archived version modules are
rollback artefacts and are deliberately absent from the active import graph.
"""

from .agent import ask_risk_agent, ask_scenario_agent, get_recent_investigation_context
from .controls import (
    detect_material_risk_movements,
    evaluate_all_limits,
    evaluate_pnl_explain_alerts,
    evaluate_sensitivity_limits,
    generate_daily_risk_brief,
    get_risk_alerts,
)
from .core import (
    DRIVER_COLUMNS,
    STRESS_SCENARIO_DEFINITIONS,
    STRESS_SCENARIO_LIMITS,
    SVAR_LIMIT_MULTIPLIER,
    VAR_ATTRIBUTION_GROUPS,
    VERSION,
    _empirical_ks_statistic,
    _pla_zone,
    build_pla_demo_history,
    df,
    get_backtesting_analysis,
    get_current_risk,
    get_limit_analysis,
    get_pnl_analysis,
    get_portfolio_scope,
    get_risk_run_lineage,
    get_ten_day_summary,
    get_var_trend,
    validate_data,
)
from .hierarchy import build_hierarchy
from .scenario import run_interactive_scenario
from .sensitivities import (
    get_dashboard_ir_volatility_surface,
    get_delta_curve_tenor_summary,
    get_ir_vega_surface,
    get_market_sensitivities,
    get_scenario_lab_specification,
)
from .stress import (
    build_supplied_stress_frame,
    get_stress_analysis,
    get_stress_evolution,
    get_stress_limit_monitor,
    get_stress_movement_table,
    get_stress_scenario_catalog,
)

__all__ = [name for name in globals() if not name.startswith("__")]

