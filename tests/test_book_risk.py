from pathlib import Path

import pandas as pd

from archive.versions.market_risk_hierarchy_v15 import build_hierarchy
from mirai.book_risk import (
    aggregate_scope_history,
    build_book_risk_history,
    reconciliation_report,
)


def bank_history():
    source = pd.read_csv(
        Path(__file__).parents[1] / "data" / "market_risk_attribution_wide.csv"
    )
    source["cob_date"] = pd.to_datetime(source["cob_date"])
    return source.sort_values("cob_date").reset_index(drop=True)


def test_book_history_is_granular_and_reconciles():
    source = bank_history()
    books, _ = build_hierarchy()
    history = build_book_risk_history(source, books)
    report = reconciliation_report(source, history)

    assert len(history) == len(source) * len(books)
    assert history["book_id"].nunique() == 20
    assert report["max_absolute_error"] < 1e-6


def test_book_scope_has_distinct_time_varying_risk():
    source = bank_history()
    books, _ = build_hierarchy()
    history = build_book_risk_history(source, books)
    first = aggregate_scope_history(
        history.loc[history["book_id"] == books.iloc[0]["book_id"]]
    )
    second = aggregate_scope_history(
        history.loc[history["book_id"] == books.iloc[1]["book_id"]]
    )

    assert len(first) == 260
    assert not first["var_1d_99_hist"].equals(second["var_1d_99_hist"])
    ratio = first["var_1d_99_hist"] / source["var_1d_99_hist"].reset_index(drop=True)
    assert ratio.nunique() > 20
    assert pd.api.types.is_datetime64_any_dtype(first["cob_date"])