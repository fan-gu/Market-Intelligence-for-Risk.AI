"""Deterministic granular synthetic book-risk records for MIRAI V32."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

IDENTIFIER_COLUMNS = [
    "cob_date",
    "portfolio_id",
    "reporting_currency",
    "business_line",
    "trading_desk",
    "book_id",
]

NON_ADDITIVE_COLUMNS = {
    "var_limit_utilization_pct",
    "backtest_hypo_exception",
    "backtest_actual_exception",
    "backtest_exception_count_250d",
}


def _stable_loading(book_id: str, column: str) -> float:
    digest = hashlib.sha256(f"{book_id}|{column}".encode()).digest()
    return (int.from_bytes(digest[:4], "big") / (2**32 - 1)) * 2.0 - 1.0


def build_book_risk_history(bank_history: pd.DataFrame, books: pd.DataFrame) -> pd.DataFrame:
    """Create explicit book/date records that reconcile to the supplied bank totals.

    Additive measures reconcile exactly on every business date. Book contributions use
    deterministic, measure-specific and time-varying loadings instead of one fixed scalar.
    VaR and SVaR fields represent Euler-style contributions to the parent portfolio.
    """
    source = bank_history.sort_values("cob_date").reset_index(drop=True).copy()
    hierarchy = books.sort_values("book_id").reset_index(drop=True).copy()
    weights = hierarchy["allocation_weight"].to_numpy(dtype=float)
    weights = weights / weights.sum()
    dates = source["cob_date"].reset_index(drop=True)
    numeric_columns = [
        column
        for column in source.select_dtypes(include="number").columns
        if column not in NON_ADDITIVE_COLUMNS
    ]
    rows: list[pd.DataFrame] = []
    time_axis = np.arange(len(source), dtype=float)

    for book_index, book in hierarchy.iterrows():
        frame = pd.DataFrame({
            "cob_date": dates,
            "portfolio_id": source["portfolio_id"].astype(str),
            "reporting_currency": source["reporting_currency"].astype(str),
            "business_line": book["business_line"],
            "trading_desk": book["trading_desk"],
            "book_id": book["book_id"],
            "risk_budget_weight": float(weights[book_index]),
        })
        rows.append(frame)

    result = pd.concat(rows, ignore_index=True)
    result = result.sort_values(["cob_date", "book_id"]).reset_index(drop=True)

    for column in numeric_columns:
        values = source[column].to_numpy(dtype=float)
        contribution_blocks = []
        loadings = np.array([
            _stable_loading(str(book_id), column) for book_id in hierarchy["book_id"]
        ])
        phase = np.array([
            _stable_loading(str(book_id), f"{column}:phase") * np.pi
            for book_id in hierarchy["book_id"]
        ])
        for date_index, total in enumerate(values):
            cycle = np.sin(time_axis[date_index] / 17.0 + phase)
            raw = weights * (1.0 + 0.22 * loadings + 0.10 * cycle)
            raw = np.clip(raw, weights * 0.25, None)
            shares = raw / raw.sum()
            contribution_blocks.append(total * shares)
        matrix = np.asarray(contribution_blocks)
        result[column] = matrix.reshape(-1)

    result["var_limit_utilization_pct"] = np.where(
        result["var_limit_amount"].ne(0),
        result["var_1d_99_hist"].abs() / result["var_limit_amount"].abs() * 100.0,
        0.0,
    )
    result["backtest_hypo_exception"] = (
        result["hypothetical_pnl"] < -result["var_1d_99_hist"].abs()
    ).astype(int)
    result["backtest_actual_exception"] = (
        result["actual_pnl"] < -result["var_1d_99_hist"].abs()
    ).astype(int)
    result["backtest_exception_count_250d"] = (
        result.groupby("book_id")["backtest_hypo_exception"]
        .transform(lambda series: series.rolling(250, min_periods=1).sum())
        .astype(int)
    )
    result["basel_traffic_light_zone"] = np.select(
        [result["backtest_exception_count_250d"] <= 4, result["backtest_exception_count_250d"] <= 9],
        ["GREEN", "AMBER"],
        default="RED",
    )
    return result


def aggregate_scope_history(book_history: pd.DataFrame) -> pd.DataFrame:
    """Aggregate selected book records into a daily risk perimeter."""
    if book_history.empty:
        return pd.DataFrame()
    additive = [
        column
        for column in book_history.select_dtypes(include="number").columns
        if column not in NON_ADDITIVE_COLUMNS and column != "risk_budget_weight"
    ]
    aggregated = book_history.groupby("cob_date", as_index=False)[additive].sum()
    identifiers = book_history.groupby("cob_date", as_index=False).agg(
        portfolio_id=("portfolio_id", "first"),
        reporting_currency=("reporting_currency", "first"),
        selected_books=("book_id", "nunique"),
    )
    aggregated = identifiers.merge(aggregated, on="cob_date", how="inner")
    aggregated["var_limit_utilization_pct"] = np.where(
        aggregated["var_limit_amount"].ne(0),
        aggregated["var_1d_99_hist"].abs() / aggregated["var_limit_amount"].abs() * 100.0,
        0.0,
    )
    aggregated["backtest_hypo_exception"] = (
        aggregated["hypothetical_pnl"] < -aggregated["var_1d_99_hist"].abs()
    ).astype(int)
    aggregated["backtest_actual_exception"] = (
        aggregated["actual_pnl"] < -aggregated["var_1d_99_hist"].abs()
    ).astype(int)
    aggregated["backtest_exception_count_250d"] = (
        aggregated["backtest_hypo_exception"].rolling(250, min_periods=1).sum().astype(int)
    )
    aggregated["basel_traffic_light_zone"] = np.select(
        [aggregated["backtest_exception_count_250d"] <= 4, aggregated["backtest_exception_count_250d"] <= 9],
        ["GREEN", "AMBER"],
        default="RED",
    )
    return aggregated.sort_values("cob_date").reset_index(drop=True)


def reconciliation_report(bank_history: pd.DataFrame, book_history: pd.DataFrame) -> dict:
    """Report maximum daily reconciliation error for additive measures."""
    aggregate = aggregate_scope_history(book_history)
    numeric = [
        column
        for column in bank_history.select_dtypes(include="number").columns
        if column not in NON_ADDITIVE_COLUMNS
    ]
    merged = bank_history[["cob_date", *numeric]].merge(
        aggregate[["cob_date", *numeric]], on="cob_date", suffixes=("_bank", "_books")
    )
    errors = {
        column: float((merged[f"{column}_bank"] - merged[f"{column}_books"]).abs().max())
        for column in numeric
    }
    return {
        "dates": int(len(merged)),
        "books": int(book_history["book_id"].nunique()),
        "records": int(len(book_history)),
        "max_absolute_error": max(errors.values(), default=0.0),
        "column_errors": errors,
    }
