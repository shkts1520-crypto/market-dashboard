import pandas as pd

import v38.stock_gap_repair as sgr


def test_atlq_verified_alias_joins_prechange_history_and_current_tradingview_bar(monkeypatch):
    def fake_yahoo_rows(yf, *, ticker, symbol, target_session):
        if symbol == "JAB":
            return [
                {"ticker": ticker, "date": "2026-08-28", "open": 9.9, "high": 10.0, "low": 9.9, "close": 9.95, "volume": 1000, "is_complete": True, "split_checked": True, "split_anomaly": False},
            ]
        return []

    monkeypatch.setattr(sgr, "_yahoo_rows", fake_yahoo_rows)
    monkeypatch.setattr(
        sgr,
        "_tradingview_current_bar",
        lambda **kwargs: {"ticker": "ATLQ", "date": "2026-09-11", "open": 9.98, "high": 9.99, "low": 9.97, "close": 9.98, "volume": 746, "is_complete": True, "split_checked": True, "split_anomaly": False},
    )
    rows = sgr._corporate_action_rows(None, ticker="ATLQ", target_session="2026-09-11")
    assert [row["date"] for row in rows] == ["2026-08-28", "2026-09-11"]
    assert rows[-1]["close"] == 9.98
    assert sgr.CORPORATE_ACTION_ALIASES["ATLQ"]["same_cusip"] is True
