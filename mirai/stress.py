"""Supplied stress-series analytics for the consolidated runtime."""

from __future__ import annotations

import pandas as pd

from .core import STRESS_SCENARIO_DEFINITIONS, STRESS_SCENARIO_LIMITS, df


def build_supplied_stress_frame(as_of_date=None):
    source = df.copy()
    if as_of_date is not None:
        source = source.loc[source["cob_date"] <= pd.Timestamp(as_of_date)]
    frame = source[["cob_date"]].copy()
    metadata = {}
    for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items():
        frame[scenario] = source[definition["column"]].astype(float)
        metadata[scenario] = {
            "source": "Supplied synthetic risk-engine feed",
            "type": definition["type"],
            "definition": definition["definition"],
        }
    return frame.reset_index(drop=True), metadata


def get_stress_evolution(as_of_date=None):
    frame, metadata = build_supplied_stress_frame(as_of_date)
    return {
        "dates": [str(date.date()) for date in frame["cob_date"]],
        "scenarios": {
            scenario: {
                "type": metadata[scenario]["type"],
                "definition": metadata[scenario]["definition"],
                "values": [float(value) for value in frame[scenario]],
            }
            for scenario in metadata
        },
    }


def _reference_row(frame, current_date, *, days=None, months=None):
    target = (
        current_date - pd.Timedelta(days=days)
        if days is not None
        else current_date - pd.DateOffset(months=months)
    )
    candidates = frame.loc[frame["cob_date"] <= target]
    return None if candidates.empty else candidates.iloc[-1]


def get_stress_movement_table(as_of_date=None) -> dict:
    frame, metadata = build_supplied_stress_frame(as_of_date)
    if frame.empty:
        return {"status": "NO_DATA", "scenarios": []}
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else None
    weekly = _reference_row(frame, latest["cob_date"], days=7)
    monthly = _reference_row(frame, latest["cob_date"], months=1)
    rows = []
    for scenario, item in metadata.items():
        impact = float(latest[scenario])
        rows.append(
            {
                "scenario": scenario,
                "category": item["type"],
                "latest_impact": impact,
                "daily_move": None if previous is None else impact - float(previous[scenario]),
                "weekly_move": None if weekly is None else impact - float(weekly[scenario]),
                "monthly_move": None if monthly is None else impact - float(monthly[scenario]),
                "definition": item["definition"],
            }
        )
    return {
        "status": "AVAILABLE",
        "as_of_date": str(latest["cob_date"].date()),
        "scenarios": rows,
        "usage_note": "Daily uses the prior business date; weekly and monthly use the latest observation on or before the reference date.",
    }


def get_stress_scenario_catalog() -> list[dict]:
    return [
        {
            "scenario": scenario,
            "category": definition["type"],
            "shock": definition["definition"],
            "limit": STRESS_SCENARIO_LIMITS[scenario],
            "limit_unit": "EUR P&L loss",
            "derived_from": "",
            "pricing_status": "Priced by supplied synthetic risk-engine feed",
        }
        for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items()
    ]


def _limit_status(consumption_pct: float) -> str:
    if consumption_pct >= 100.0:
        return "BREACH"
    if consumption_pct >= 80.0:
        return "WARNING"
    return "OK"


def get_stress_limit_monitor(as_of_date=None) -> dict:
    movement = get_stress_movement_table(as_of_date)
    rows = []
    for item in movement.get("scenarios", []):
        limit = float(STRESS_SCENARIO_LIMITS[item["scenario"]])
        consumption = abs(min(float(item["latest_impact"]), 0.0)) / limit * 100.0
        rows.append(
            {
                "scenario": item["scenario"],
                "category": item["category"],
                "impact": item["latest_impact"],
                "limit": limit,
                "consumption_pct": consumption,
                "status": _limit_status(consumption),
            }
        )
    return {
        "status": movement.get("status", "NO_DATA"),
        "as_of_date": movement.get("as_of_date"),
        "scenarios": rows,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "usage_note": "Prototype scenario limits use 80% for warning and 100% for breach; they are not approved production mandates.",
    }


def get_stress_analysis() -> dict:
    frame, _ = build_supplied_stress_frame()
    latest = frame.iloc[-1]
    return {
        scenario: float(latest[scenario])
        for scenario in STRESS_SCENARIO_DEFINITIONS
    }
