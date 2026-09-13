from __future__ import annotations

import numpy as np
import pandas as pd

from v38.vix_fear_cycle import _scan_cycle, build_vix_fear_cycle


def test_vix_sequence_event_rollover_bottom_reextreme_and_rearm():
    frame = pd.DataFrame([
        {"date": "2026-01-02", "high": 20.0, "plus1_sigma": 30.0, "plus2_sigma": 40.0, "lwma5": 20.0, "lwma10": 19.0},
        {"date": "2026-01-05", "high": 45.0, "plus1_sigma": 30.0, "plus2_sigma": 40.0, "lwma5": 30.0, "lwma10": 25.0},
        {"date": "2026-01-06", "high": 44.0, "plus1_sigma": 30.0, "plus2_sigma": 40.0, "lwma5": 29.0, "lwma10": 26.0},
        {"date": "2026-01-07", "high": 35.0, "plus1_sigma": 30.0, "plus2_sigma": 40.0, "lwma5": 25.0, "lwma10": 27.0},
        {"date": "2026-01-08", "high": 42.0, "plus1_sigma": 30.0, "plus2_sigma": 40.0, "lwma5": 24.0, "lwma10": 26.0},
        {"date": "2026-01-09", "high": 29.0, "plus1_sigma": 30.0, "plus2_sigma": 40.0, "lwma5": 23.0, "lwma10": 25.0},
    ])
    state, events, markers = _scan_cycle(frame)
    assert state == "NORMAL"
    assert [item["kind"] for item in markers] == ["EVENT", "ROLLOVER", "BOTTOM", "RE-EXTREME"]
    assert events[-1]["event"] == "2026-01-05"
    assert events[-1]["roll"] == "2026-01-06"
    assert events[-1]["bottom"] == "2026-01-07"
    assert events[-1]["days"] == 2
    assert events[-1]["peak"] == 45.0


def test_build_vix_fear_cycle_uses_completed_month_log_distribution_and_is_observational():
    dates = pd.bdate_range("1990-01-02", "1994-02-28")
    idx = np.arange(len(dates), dtype=float)
    high = 18.0 + 2.0 * np.sin(idx / 17.0) + 0.002 * idx
    close = high - 0.6
    frame = pd.DataFrame({"High": high, "Close": close}, index=dates)
    session = dates[-1].strftime("%Y-%m-%d")
    out = build_vix_fear_cycle(frame, session_date=session, generated_at="2026-09-13T00:00:00Z")
    assert out["status"] == "READY"
    assert out["session_date"] == session
    assert out["distribution"]["completed_months"] >= 24
    assert out["current"]["plus2_sigma"] > out["current"]["plus1_sigma"] > 0
    assert out["rules"]["event"] == "daily High >= +2 sigma"
    assert out["rules"]["rollover"] == "after EVENT, LWMA5 declines versus prior session"
    assert out["rules"]["bottom"] == "after ROLLOVER, LWMA5 crosses below LWMA10"
    assert out["trading_gate_eligible"] is False
    assert out["series"][-1]["date"] == session
