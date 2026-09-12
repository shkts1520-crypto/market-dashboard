from __future__ import annotations

import json

import pandas as pd

from v38.two_year_ui import DISPLAY_SESSIONS, attach_two_year_display_history


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_two_year_display_history_caps_at_504_and_preserves_current_observation(tmp_path):
    dates = [day.strftime("%Y-%m-%d") for day in pd.bdate_range("2024-01-02", periods=600)]
    session = dates[-1]

    reconstructed_rows = []
    market_rows = []
    diagnostic_rows = []
    for index, day in enumerate(dates):
        reconstructed_rows.append({
            "date": day,
            "breadth50": float(40 + index % 30),
            "breadth200": float(45 + index % 25),
            "f1": {"value": 0.10},
            "f2": {"value": 0.20},
            "f3": {"value": 0.30},
        })
        market_rows.append({"date": day, "close": 100.0 + index})
        diagnostic_rows.append({
            "date": day,
            "volume_participation": 1.0 + index / 10000.0,
            "up_down_dollar_ratio": 1.2,
            "mcclellan": float(index - 300),
        })

    history = tmp_path / "history"
    _write(history / "reconstructed_stock_metrics.json", {
        "status": "READY",
        "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
        "rows": reconstructed_rows,
    })
    _write(history / "market_series_2y.json", {
        "session_date": session,
        "source": "test",
        "series": {"QQQ": market_rows},
    })
    _write(history / "market_diagnostics_2y.json", {
        "session_date": session,
        "status": "READY",
        "source": "test",
        "series": diagnostic_rows,
    })

    view = {
        "session_date": session,
        "daily": {
            "history": [{
                "date": session,
                "breadth50": 99.0,
                "breadth200": 98.0,
                "f1": 0.11,
            }],
            "market_series": {},
            "market_diagnostics": {"series": []},
        },
    }

    out = attach_two_year_display_history(view, tmp_path)
    daily = out["daily"]

    assert DISPLAY_SESSIONS == 504
    assert len(daily["history"]) == DISPLAY_SESSIONS
    assert daily["history"][-1]["date"] == session
    assert daily["history"][-1]["breadth50"] == 99.0
    assert daily["history"][-1]["breadth200"] == 98.0
    assert daily["history"][-1]["f1"] == 0.11
    assert len(daily["market_series"]["QQQ"]) == DISPLAY_SESSIONS
    assert len(daily["market_diagnostics"]["series"]) == DISPLAY_SESSIONS
    assert daily["display_history"]["window_sessions"] == DISPLAY_SESSIONS
    assert daily["display_history"]["history_points"] == DISPLAY_SESSIONS
    assert daily["display_history"]["trading_gate_eligible"] is False


def test_two_year_display_history_tolerates_absent_optional_market_shards(tmp_path):
    dates = [day.strftime("%Y-%m-%d") for day in pd.bdate_range("2025-01-02", periods=40)]
    _write(tmp_path / "history" / "reconstructed_stock_metrics.json", {
        "rows": [{"date": day, "breadth50": 50.0, "breadth200": 40.0} for day in dates]
    })
    view = {
        "session_date": dates[-1],
        "daily": {"history": [], "market_series": {"QQQ": [{"date": dates[-1], "close": 1.0}]}, "market_diagnostics": {"series": []}},
    }
    out = attach_two_year_display_history(view, tmp_path)
    assert len(out["daily"]["history"]) == 40
    assert out["daily"]["market_series"]["QQQ"][0]["close"] == 1.0
