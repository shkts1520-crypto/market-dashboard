from __future__ import annotations

import json

import pandas as pd

from v38.historical_reconstruction import build_reconstructed_stock_history
from v38.rs_history import build_rs_history


def _ohlcv(ticker_count: int = 40, session_count: int = 340):
    dates = pd.bdate_range("2025-05-19", periods=session_count)
    rows = []
    tickers = [f"T{i:02d}" for i in range(ticker_count)]
    for index, ticker in enumerate(tickers):
        growth = 1.0002 + index * 0.000035
        price = 20.0 + index
        for day in dates:
            price *= growth
            rows.append({
                "ticker": ticker,
                "date": day.strftime("%Y-%m-%d"),
                "open": price * 0.998,
                "high": price * 1.004,
                "low": price * 0.996,
                "close": price,
                "volume": 2_000_000 + index * 25_000,
                "is_complete": True,
                "split_checked": True,
                "split_anomaly": False,
            })
    return pd.DataFrame(rows), tickers, dates[-1].strftime("%Y-%m-%d")


def test_same_ohlcv_reconstructs_breadth_rs_and_f123_history():
    frame, tickers, session = _ohlcv()
    out = build_reconstructed_stock_history(
        frame,
        tickers,
        session_date=session,
        generated_at="2026-09-12T00:00:00Z",
        sessions=80,
    )

    assert out["status"] == "READY"
    assert out["history_kind"] == "CURRENT_UNIVERSE_RECONSTRUCTED"
    assert out["session_count"] == 80
    assert out["current_universe_count"] == 40
    assert out["survivorship_warning"] is True
    assert out["trading_gate_eligible"] is False

    latest = out["rows"][-1]
    assert latest["breadth50"] == 100.0
    assert latest["breadth200"] == 100.0
    assert len(latest["rs_windows"]["63"]) == 10
    assert len(latest["rs_windows"]["126"]) == 10
    assert len(latest["rs_top"]) == 40
    assert latest["rs_top"][0]["rs189"] == 100.0
    assert latest["f1"]["status"] == "FULL"
    assert latest["f1"]["value"] == 0.0
    assert latest["f2"]["status"] == "OK"
    assert latest["f2"]["value"] is not None
    assert latest["f3"]["status"] == "OK"
    assert latest["f3"]["value"] == 0.0


def test_reconstructed_windows_enable_rs_21_session_history(tmp_path):
    frame, tickers, session = _ohlcv()
    reconstructed = build_reconstructed_stock_history(
        frame,
        tickers,
        session_date=session,
        generated_at="2026-09-12T00:00:00Z",
        sessions=60,
    )
    history = tmp_path / "history"
    history.mkdir()
    (history / "reconstructed_stock_metrics.json").write_text(
        json.dumps(reconstructed), encoding="utf-8"
    )

    latest = reconstructed["rows"][-1]
    current = {
        "session_date": session,
        "rows": latest["rs_top"],
    }
    out = build_rs_history(
        history,
        current,
        session_date=session,
        generated_at="2026-09-12T00:00:00Z",
    )

    assert out["history_kind"] == "CURRENT_UNIVERSE_RECONSTRUCTED"
    assert out["reconstructed_sessions"] >= 59
    assert out["survivorship_warning"] is True
    assert out["trading_gate_eligible"] is False
    for period in ("63", "126", "189"):
        window = out["windows"][period]
        assert window["available_sessions"] >= 59
        assert window["comparisons"][2]["status"] == "READY"
    assert out["persistence"]["classification_ready"] is True
    assert out["persistence"]["observed_sessions"] == 21
