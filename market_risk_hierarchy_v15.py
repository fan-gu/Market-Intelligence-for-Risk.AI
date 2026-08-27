"""Synthetic trade hierarchy for V15.

This is a demo allocation structure, not trade-level pricing or a bank hierarchy.
"""

from __future__ import annotations

import pandas as pd


HIERARCHY = [
    ("Cross-asset", "Macro solutions", "XAS_MACRO", 0.18),
    ("Cross-asset", "Structured solutions", "XAS_STRUCT", 0.12),
    ("FX options", "G10 FX options", "FXO_G10", 0.16),
    ("FX options", "Emerging-market FX options", "FXO_EM", 0.08),
    ("IR linear", "EUR rates", "IRL_EUR", 0.14),
    ("IR linear", "USD rates", "IRL_USD", 0.10),
    ("IR non-linear", "Swaptions", "IRN_SWAPTION", 0.10),
    ("IR non-linear", "Exotics", "IRN_EXOTIC", 0.05),
    ("Equity", "Equity derivatives", "EQD_INDEX", 0.04),
    ("Equity", "Equity volatility", "EQD_VOL", 0.03),
]


def build_hierarchy():
    """Create business lines, desks, books and synthetic trade inventory."""
    rows = []
    trade_rows = []
    for business_line, desk, book_prefix, desk_weight in HIERARCHY:
        for book_number, book_share in enumerate((0.58, 0.42), start=1):
            book_id = f"{book_prefix}_BOOK_{book_number:02d}"
            book_weight = desk_weight * book_share
            rows.append({
                "business_line": business_line,
                "trading_desk": desk,
                "book_id": book_id,
                "allocation_weight": book_weight,
            })
            for trade_number, trade_share in enumerate((0.50, 0.30, 0.20), start=1):
                trade_rows.append({
                    "trade_id": f"{book_id}_T{trade_number:03d}",
                    "book_id": book_id,
                    "trading_desk": desk,
                    "business_line": business_line,
                    "product": f"{business_line} synthetic instrument {trade_number}",
                    "reporting_currency": "EUR",
                    "notional_eur": round(20_000_000 * book_weight * trade_share, 0),
                    "allocation_weight": book_weight * trade_share,
                })
    return pd.DataFrame(rows), pd.DataFrame(trade_rows)


def allocated_hierarchy_summary(current_risk: dict):
    """Allocate aggregate demo risk to hierarchy nodes for visual exploration."""
    books, _ = build_hierarchy()
    allocation_columns = {
        "allocated_historical_var": current_risk["var_hist"],
        "allocated_stressed_var": current_risk["stressed_var"],
        "allocated_expected_shortfall": current_risk["expected_shortfall"],
    }
    for column, total in allocation_columns.items():
        books[column] = books["allocation_weight"] * total
    return books
