"""Risk-data service independent of Streamlit and the LLM client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

SVAR_LIMIT_MULTIPLIER = 1.5
WARNING_THRESHOLD_PCT = 80.0
BREACH_THRESHOLD_PCT = 100.0


class RiskDataError(ValueError):
    """Raised when a risk-run request cannot be resolved from the supplied feed."""


def classify_limit(consumption_pct: float) -> str:
    if consumption_pct >= BREACH_THRESHOLD_PCT:
        return "BREACH"
    if consumption_pct >= WARNING_THRESHOLD_PCT:
        return "WARNING"
    return "OK"


@dataclass
class RiskDataService:
    data_path: Path

    @classmethod
    def from_default_data(cls) -> RiskDataService:
        return cls(
            Path(__file__).resolve().parents[1]
            / "data"
            / "market_risk_attribution_wide.csv"
        )

    def load(self) -> pd.DataFrame:
        frame = pd.read_csv(self.data_path)
        frame["cob_date"] = pd.to_datetime(frame["cob_date"])
        required = {
            "cob_date",
            "portfolio_id",
            "reporting_currency",
            "actual_pnl",
            "var_1d_99_hist",
            "stressed_var_1d_99",
            "var_limit_amount",
        }
        missing = required.difference(frame.columns)
        if missing:
            raise RiskDataError(
                f"Risk feed is missing required columns: {', '.join(sorted(missing))}"
            )
        if frame.empty:
            raise RiskDataError("Risk feed contains no observations")
        return frame.sort_values("cob_date").reset_index(drop=True)

    def select_run(self, as_of_date: date | None = None) -> pd.Series:
        frame = self.load()
        requested = pd.Timestamp(as_of_date) if as_of_date else frame["cob_date"].max()
        eligible = frame.loc[frame["cob_date"] <= requested]
        if eligible.empty:
            raise RiskDataError(
                f"No approved run is available on or before {requested.date().isoformat()}"
            )
        return eligible.iloc[-1]

    @staticmethod
    def run_id(row: pd.Series) -> str:
        return f"DEMO-RUN-{pd.Timestamp(row['cob_date']).date().isoformat()}-{str(row['portfolio_id']).upper()}"

    @staticmethod
    def limit_metric(name: str, value: float, limit: float) -> dict:
        consumption = 0.0 if limit == 0 else value / limit * 100
        return {
            "metric": name,
            "value": round(float(value), 2),
            "limit": round(float(limit), 2),
            "consumption_pct": round(float(consumption), 2),
            "status": classify_limit(float(consumption)),
        }

    def get_summary(self, as_of_date: date | None = None) -> dict:
        row = self.select_run(as_of_date)
        hvar_limit = float(row["var_limit_amount"])
        return {
            "run_id": self.run_id(row),
            "as_of_date": pd.Timestamp(row["cob_date"]).date(),
            "reporting_currency": str(row["reporting_currency"]),
            "pnl": round(float(row["actual_pnl"]), 2),
            "hvar": self.limit_metric("HVaR", float(row["var_1d_99_hist"]), hvar_limit),
            "svar": self.limit_metric(
                "SVaR",
                float(row["stressed_var_1d_99"]),
                hvar_limit * SVAR_LIMIT_MULTIPLIER,
            ),
        }

    def get_breaches(self, as_of_date: date | None = None) -> dict:
        summary = self.get_summary(as_of_date)
        items = [summary["hvar"], summary["svar"]]
        return {
            "run_id": summary["run_id"],
            "as_of_date": summary["as_of_date"],
            "items": [item for item in items if item["status"] != "OK"],
        }

    def run_scenario(
        self,
        *,
        as_of_date: date | None,
        rate_shock_bp: float,
        fx_spot_move_pct: float,
        volatility_shock_pct: float,
        severity: str,
    ) -> dict:
        row = self.select_run(as_of_date)
        multiplier = 2.0 if severity == "Extreme" else 1.0
        rate_base = sum(
            abs(float(row[column]))
            for column in (
                "contrib_var_ir_sofr_curve",
                "contrib_var_ir_estr_curve",
                "contrib_var_ir_sonia_curve",
            )
        )
        fx_base = abs(float(row["contrib_var_fx_spot"]))
        vol_base = abs(float(row["contrib_var_ir_swaption_vol"])) + abs(
            float(row["contrib_var_fx_vol_implied"])
        )
        estimated_pnl = (
            -(
                rate_base * rate_shock_bp / 10_000
                + fx_base * fx_spot_move_pct / 100
                + vol_base * volatility_shock_pct / 100
            )
            * multiplier
        )
        return {
            "run_id": self.run_id(row),
            "as_of_date": pd.Timestamp(row["cob_date"]).date(),
            "estimated_pnl": round(float(estimated_pnl), 2),
            "methodology": "Illustrative sensitivity proxy from approved VaR contributors; not a full risk-engine revaluation.",
            "is_official_risk_result": False,
        }
