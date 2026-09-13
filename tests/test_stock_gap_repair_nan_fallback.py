from __future__ import annotations

import math

import v38.stock_gap_repair as sgr


def _row(*, ticker: str, date: str, close: float | None, volume: float = 1000.0):
    price = close
    return {
        "ticker": ticker,
        "date": date,
        "open": price,
        "high": price,
        "low": price,
        "close": close,
        "volume": volume,
        "is_complete": True,
        "split_checked": True,
        "split_anomaly": False,
    }


def test_invalid_direct_atlq_target_row_does_not_block_tradingview(monkeypatch):
    target = "2026-09-11"
    calls: list[str] = []

    def fake_yahoo_rows(yf, *, ticker, symbol, target_session):
        assert target_session == target
        if symbol == "ATLQ":
            # Mirrors the real provider failure: date and volume exist, but price
            # fields are unusable. This must not count as a valid observed bar.
            return [{
                "ticker": ticker,
                "date": target,
                "open": math.nan,
                "high": math.nan,
                "low": math.nan,
                "close": math.nan,
                "volume": 75370.0,
                "is_complete": True,
                "split_checked": True,
                "split_anomaly": False,
            }]
        if symbol == "JAB":
            return [_row(ticker=ticker, date="2026-08-28", close=9.95)]
        return []

    monkeypatch.setattr(sgr, "_yahoo_rows", fake_yahoo_rows)
    monkeypatch.setattr(sgr, "_nasdaq_historical_current_bar", lambda **kwargs: None)

    def fake_tv(**kwargs):
        calls.append(kwargs["ticker"])
        return {
            "ticker": "ATLQ",
            "date": target,
            "open": 9.98,
            "high": 9.98,
            "low": 9.96,
            "close": 9.97,
            "volume": 78095.0,
            "is_complete": True,
            "split_checked": True,
            "split_anomaly": False,
        }

    monkeypatch.setattr(sgr, "_tradingview_current_bar", fake_tv)

    rows = sgr.isolated_history_rows(None, ticker="ATLQ", target_session=target)
    exact = [row for row in rows if row["date"] == target]
    assert calls == ["ATLQ"]
    assert len(exact) == 1
    assert exact[0]["close"] == 9.97
    assert exact[0]["volume"] == 78095.0


def test_valid_exact_legacy_alias_is_still_accepted_after_live_fallbacks_fail(monkeypatch):
    target = "2026-09-11"

    def fake_yahoo_rows(yf, *, ticker, symbol, target_session):
        if symbol == "ATLQ":
            return [_row(ticker=ticker, date=target, close=None, volume=75370.0)]
        if symbol == "JAB":
            return [
                _row(ticker=ticker, date="2026-08-28", close=9.95),
                _row(ticker=ticker, date=target, close=9.97, volume=15328.0),
            ]
        return []

    monkeypatch.setattr(sgr, "_yahoo_rows", fake_yahoo_rows)
    monkeypatch.setattr(sgr, "_nasdaq_historical_current_bar", lambda **kwargs: None)
    monkeypatch.setattr(sgr, "_tradingview_current_bar", lambda **kwargs: None)

    rows = sgr.isolated_history_rows(None, ticker="ATLQ", target_session=target)
    exact = [row for row in rows if row["date"] == target]
    assert len(exact) == 1
    assert exact[0]["close"] == 9.97
    assert exact[0]["volume"] == 15328.0
