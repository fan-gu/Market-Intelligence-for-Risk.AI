"""Synthetic reporting hierarchy used by the MIRAI demonstration."""

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


def build_hierarchy() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return deterministic business-line, desk, book and trade records."""
    book_rows: list[dict] = []
    trade_rows: list[dict] = []
    for business_line, desk, book_prefix, desk_weight in HIERARCHY:
        for book_number, book_share in enumerate((0.58, 0.42), start=1):
            book_id = f"{book_prefix}_BOOK_{book_number:02d}"
            book_weight = desk_weight * book_share
            book_rows.append(
                {
                    "business_line": business_line,
                    "trading_desk": desk,
                    "book_id": book_id,
                    "allocation_weight": book_weight,
                }
            )
            for trade_number, trade_share in enumerate((0.50, 0.30, 0.20), start=1):
                trade_rows.append(
                    {
                        "trade_id": f"{book_id}_T{trade_number:03d}",
                        "book_id": book_id,
                        "trading_desk": desk,
                        "business_line": business_line,
                        "product": f"{business_line} synthetic instrument {trade_number}",
                        "reporting_currency": "EUR",
                        "notional_eur": round(
                            20_000_000 * book_weight * trade_share, 0
                        ),
                        "allocation_weight": book_weight * trade_share,
                    }
                )
    return pd.DataFrame(book_rows), pd.DataFrame(trade_rows)
