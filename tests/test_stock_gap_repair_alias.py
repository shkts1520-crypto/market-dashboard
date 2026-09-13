import json

import v38.stock_gap_repair as sgr


def _row(date, close, *, open_=9.96, high=9.99, low=9.95, volume=1000):
    return {
        "ticker": "ATLQ",
        "date": date,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "is_complete": True,
        "split_checked": True,
        "split_anomaly": False,
    }


def test_nasdaq_historical_current_bar_requires_exact_target_date(monkeypatch):
    payload = {
        "data": {
            "tradesTable": {
                "rows": [
                    {
                        "date": "09/10/2026",
                        "open": "$9.95",
                        "high": "$9.97",
                        "low": "$9.94",
                        "close": "$9.96",
                        "volume": "10,000",
                    },
                    {
                        "date": "09/11/2026",
                        "open": "$9.96",
                        "high": "$9.98",
                        "low": "$9.95",
                        "close": "$9.97",
                        "volume": "75,370",
                    },
                ]
            }
        }
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        assert "/api/quote/ATLQ/historical?" in request.full_url
        # Nasdaq's live API rejects an equal from/to date for this symbol.
        # Query a narrow surrounding window, but still accept only the exact
        # requested target-session row below.
        assert "fromdate=2026-09-10" in request.full_url
        assert "todate=2026-09-12" in request.full_url
        assert timeout == 20
        return FakeResponse()

    monkeypatch.setattr(sgr.urllib.request, "urlopen", fake_urlopen)
    row = sgr._nasdaq_historical_current_bar(ticker="ATLQ", target_session="2026-09-11")
    assert row is not None
    assert row["date"] == "2026-09-11"
    assert row["open"] == 9.96
    assert row["high"] == 9.98
    assert row["low"] == 9.95
    assert row["close"] == 9.97
    assert row["volume"] == 75370.0


def test_atlq_verified_alias_prefers_exact_nasdaq_target_bar(monkeypatch):
    def fake_yahoo_rows(yf, *, ticker, symbol, target_session):
        if symbol == "JAB":
            return [_row("2026-08-28", 9.95)]
        return []

    monkeypatch.setattr(sgr, "_yahoo_rows", fake_yahoo_rows)
    monkeypatch.setattr(
        sgr,
        "_nasdaq_historical_current_bar",
        lambda **kwargs: _row("2026-09-11", 9.97, open_=9.96, high=9.98, low=9.95, volume=75370),
    )
    monkeypatch.setattr(
        sgr,
        "_tradingview_current_bar",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("TradingView must not run after exact Nasdaq success")),
    )
    rows = sgr._corporate_action_rows(None, ticker="ATLQ", target_session="2026-09-11")
    assert [row["date"] for row in rows] == ["2026-08-28", "2026-09-11"]
    assert rows[-1]["close"] == 9.97
    assert rows[-1]["volume"] == 75370


def test_atlq_verified_alias_joins_prechange_history_and_current_tradingview_bar(monkeypatch):
    def fake_yahoo_rows(yf, *, ticker, symbol, target_session):
        if symbol == "JAB":
            return [_row("2026-08-28", 9.95)]
        return []

    monkeypatch.setattr(sgr, "_yahoo_rows", fake_yahoo_rows)
    monkeypatch.setattr(sgr, "_nasdaq_historical_current_bar", lambda **kwargs: None)
    monkeypatch.setattr(
        sgr,
        "_tradingview_current_bar",
        lambda **kwargs: _row("2026-09-11", 9.98, open_=9.98, high=9.99, low=9.97, volume=746),
    )
    rows = sgr._corporate_action_rows(None, ticker="ATLQ", target_session="2026-09-11")
    assert [row["date"] for row in rows] == ["2026-08-28", "2026-09-11"]
    assert rows[-1]["close"] == 9.98
    assert sgr.CORPORATE_ACTION_ALIASES["ATLQ"]["same_cusip"] is True


def test_atlq_same_cusip_legacy_symbol_is_exact_date_only_final_fallback(monkeypatch):
    def fake_yahoo_rows(yf, *, ticker, symbol, target_session):
        if symbol == "JAB":
            return [
                _row("2026-08-28", 9.95),
                _row("2026-09-11", 9.97, open_=9.96, high=9.98, low=9.95, volume=75370),
            ]
        return []

    monkeypatch.setattr(sgr, "_yahoo_rows", fake_yahoo_rows)
    monkeypatch.setattr(sgr, "_nasdaq_historical_current_bar", lambda **kwargs: None)
    monkeypatch.setattr(sgr, "_tradingview_current_bar", lambda **kwargs: None)
    rows = sgr._corporate_action_rows(None, ticker="ATLQ", target_session="2026-09-11")
    assert [row["date"] for row in rows] == ["2026-08-28", "2026-09-11"]
    assert rows[-1]["close"] == 9.97
    assert rows[-1]["date"] == "2026-09-11"
