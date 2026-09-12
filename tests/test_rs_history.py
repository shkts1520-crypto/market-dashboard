from __future__ import annotations

import pandas as pd

from v38.rs_history import build_rs_history_analysis, _tag_persistence
from v38.stock_adapter import calculate_stock_outputs


def _panel(n_tickers: int = 40, n_days: int = 330):
    dates = pd.bdate_range(end="2026-09-11", periods=n_days)
    rows = []
    tickers = [f"T{i:03d}" for i in range(n_tickers)]
    for i, ticker in enumerate(tickers):
        rate = 0.00015 + i * 0.000018
        for j, day in enumerate(dates):
            close = 20.0 * ((1.0 + rate) ** j)
            # Force a formerly weak name sharply upward near the end so at least
            # one historical Top10 comparison has a real IN/OUT transition.
            if ticker == "T000" and j >= n_days - 28:
                close *= 1.0 + 0.025 * (j - (n_days - 29))
            rows.append({
                "ticker": ticker,
                "date": day.strftime("%Y-%m-%d"),
                "open": close * 0.997,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_500_000.0,
                "is_complete": True,
                "split_checked": True,
                "split_anomaly": False,
            })
    # Two names are intentionally outside the RS percentile pool. They still have
    # valid OHLCV rows but must not dilute the percentile denominator.
    for ticker, price, volume in (("TLOW", 4.0, 4_000_000.0), ("TILLQ", 20.0, 1_000.0)):
        for j, day in enumerate(dates):
            close = price * (1.0 + 0.0004 * j)
            rows.append({
                "ticker": ticker,
                "date": day.strftime("%Y-%m-%d"),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": volume,
                "is_complete": True,
                "split_checked": True,
                "split_anomaly": False,
            })
        tickers.append(ticker)
    ohlcv = pd.DataFrame(rows)
    universe = pd.DataFrame({
        "ticker": tickers,
        "session_date": "2026-09-11",
        "in_universe": True,
    })
    return ohlcv, universe


def _current_rs():
    ohlcv, universe = _panel()
    rs, _ = calculate_stock_outputs(
        ohlcv,
        universe,
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
        source="test",
    )
    return ohlcv, rs


def test_rs_history_reproduces_current_formula_and_all_comparison_windows():
    ohlcv, rs = _current_rs()
    analysis = build_rs_history_analysis(ohlcv, rs, session_date="2026-09-11")
    assert analysis["status"] == "READY"
    assert analysis["identity_check"]["mismatch_count"] == 0
    assert analysis["identity_check"]["compared_values"] > 0
    for period in ("63", "126", "189"):
        block = analysis["comparison"][period]
        assert len(block["current"]) == 10
        assert len(block["windows"]) == 3
        assert [row["lag"] for row in block["windows"]] == [1, 5, 21]
        assert all(row["status"] == "READY" for row in block["windows"])
    assert len(analysis["persistence"]["rows"]) == 24
    assert any(
        window["turnover"] > 0
        for period in analysis["comparison"].values()
        for window in period["windows"]
    )


def test_price_and_ddv_failures_do_not_enter_rs_percentile_pool():
    ohlcv, rs = _current_rs()
    by_ticker = {row["ticker"]: row for row in rs["rows"]}
    assert by_ticker["TLOW"]["rs63"] is None
    assert by_ticker["TLOW"]["rs189"] is None
    assert by_ticker["TILLQ"]["rs63"] is None
    assert by_ticker["TILLQ"]["rs189"] is None
    analysis = build_rs_history_analysis(ohlcv, rs, session_date="2026-09-11")
    for period in ("63", "126", "189"):
        assert "TLOW" not in analysis["comparison"][period]["current"]
        assert "TILLQ" not in analysis["comparison"][period]["current"]


def test_recovered_persistence_tag_rules_remain_display_only_logic():
    assert _tag_persistence(
        rs_now=99, top10_days=1, streak=1, move21=12,
        d63=15, d126=8, d189=3, top24_rate=0.9, smooth63=88,
    ) == "一日急騰型"
    assert _tag_persistence(
        rs_now=94, top10_days=8, streak=2, move21=12,
        d63=6, d126=2, d189=1, top24_rate=0.8, smooth63=90,
    ) == "新規急浮上"
    assert _tag_persistence(
        rs_now=88, top10_days=8, streak=0, move21=-9,
        d63=-4, d126=-2, d189=-1, top24_rate=0.8, smooth63=87,
    ) == "失速中"
    assert _tag_persistence(
        rs_now=93, top10_days=16, streak=8, move21=1,
        d63=1, d126=1, d189=-1, top24_rate=0.8, smooth63=90,
    ) == "定着"
