import pandas as pd

import market_risk_agent_v29 as v29
from market_risk_agent_v32 import get_scope_risk_summary
from mirai.book_risk import (
    aggregate_scope_history,
    build_book_risk_history,
    reconciliation_report,
)


def test_book_history_is_granular_and_reconciles():
    books, _ = v29.v15.build_hierarchy()
    history = build_book_risk_history(v29.v8.df, books)
    report = reconciliation_report(v29.v8.df, history)

    assert len(history) == len(v29.v8.df) * len(books)
    assert history["book_id"].nunique() == 20
    assert report["max_absolute_error"] < 1e-6


def test_book_scope_has_distinct_time_varying_risk():
    books, _ = v29.v15.build_hierarchy()
    history = build_book_risk_history(v29.v8.df, books)
    first = aggregate_scope_history(
        history.loc[history["book_id"] == books.iloc[0]["book_id"]]
    )
    second = aggregate_scope_history(
        history.loc[history["book_id"] == books.iloc[1]["book_id"]]
    )

    assert len(first) == 260
    assert not first["var_1d_99_hist"].equals(second["var_1d_99_hist"])
    ratio = first["var_1d_99_hist"] / v29.v8.df["var_1d_99_hist"].reset_index(drop=True)
    assert ratio.nunique() > 20
    assert pd.api.types.is_datetime64_any_dtype(first["cob_date"])


def test_scope_summary_filters_to_one_book():
    summary = get_scope_risk_summary(book_id="FXO_G10_BOOK_01")

    assert summary["status"] == "AVAILABLE"
    assert summary["book_count"] == 1
    assert summary["record_count"] == 260
    assert summary["scope"] == {"book_id": "FXO_G10_BOOK_01"}
