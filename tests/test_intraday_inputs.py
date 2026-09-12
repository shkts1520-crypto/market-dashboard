from __future__ import annotations

import json

import pandas as pd
import pytest

from v38.intraday_inputs import (
    QQQ_4H_DEFINITION,
    _wilder_rsi,
    add_wilder_rsi,
    aggregate_rth_4h,
    aggregate_rth_4h_candidate,
    normalise_qqq_60m,
    patch_market_inputs_with_qqq_intraday,
)


def _frame():
    rows = []
    index = []
    for day_index, day in enumerate(pd.bdate_range("2026-08-10", "2026-09-11")):
        for hour, minute in ((9, 30), (10, 30), (11, 30), (12, 30), (13, 30), (14, 30), (15, 30)):
            stamp = pd.Timestamp(day.date()).tz_localize("America/New_York") + pd.Timedelta(hours=hour, minutes=minute)
            base = 100.0 + day_index * 0.4 + (hour - 9) * 0.05
            index.append(stamp)
            rows.append({
                "Open": base,
                "High": base + 0.4,
                "Low": base - 0.4,
                "Close": base + 0.1,
                "Volume": 1000.0,
            })
    return pd.DataFrame(rows, index=index)


def test_normalise_qqq_60m_keeps_rth_and_target_session():
    frame = _frame()
    pre = frame.iloc[[0]].copy()
    pre.index = pd.DatetimeIndex([pd.Timestamp("2026-08-10 08:30", tz="America/New_York")])
    post = frame.iloc[[0]].copy()
    post.index = pd.DatetimeIndex([pd.Timestamp("2026-08-10 16:30", tz="America/New_York")])
    rows = normalise_qqq_60m(pd.concat([pre, frame, post]).sort_index(), target_session="2026-09-11")
    assert rows
    assert rows[-1]["date"] == "2026-09-11"
    assert rows[-1]["timestamp"].startswith("2026-09-11T15:30")
    assert all("T08:30" not in row["timestamp"] and "T16:30" not in row["timestamp"] for row in rows)


def test_canonical_aggregation_has_full_4h_and_session_tail():
    hourly = normalise_qqq_60m(_frame(), target_session="2026-09-11")
    bars = add_wilder_rsi(aggregate_rth_4h(hourly))
    latest = [row for row in bars if row["date"] == "2026-09-11"]
    assert [row["bucket"] for row in latest] == ["09:30-13:30", "13:30-16:00"]
    assert [row["bar_kind"] for row in latest] == ["FULL_4H", "SESSION_TAIL"]
    assert [row["source_bar_count"] for row in latest] == [4, 3]
    assert all(row["complete"] is True for row in latest)
    assert bars[-1]["rsi14"] is not None
    # First recovery-pass API remains a compatibility alias to the adopted definition.
    assert aggregate_rth_4h_candidate(hourly) == aggregate_rth_4h(hourly)


def test_textbook_wilder_rsi_uses_sma_seed_then_recursive_smoothing():
    closes = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00,
        46.03, 46.41, 46.22, 45.64, 46.21,
    ]
    values = _wilder_rsi(closes, 14)
    assert all(value is None for value in values[:14])
    assert values[14] == pytest.approx(70.464135, rel=1e-6)
    assert values[-1] == pytest.approx(62.880718, rel=1e-6)


def test_patch_promotes_standard_completed_4h_to_trading_authority(tmp_path):
    path = tmp_path / "market_inputs.json"
    path.write_text(json.dumps({
        "session_date": "2026-09-11",
        "generated_at": "2026-09-12T00:00:00Z",
        "coverage": 1.0,
        "source": "test",
        "schema_version": "v38.market_inputs.1",
        "calculation_version": "test",
        "series": {},
        "qqq_4h_status": "DATA_REQUIRED",
    }), encoding="utf-8")
    out = patch_market_inputs_with_qqq_intraday(
        path,
        frame=_frame(),
        target_session="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
    )
    assert out["qqq_4h_status"] == "READY"
    assert out["qqq_4h_trading_gate_eligible"] is True
    assert out["qqq_4h_reason"] == "V38_CANONICAL_RTH_4H"
    assert out["qqq_4h_definition"] == QQQ_4H_DEFINITION
    assert out["qqq_4h_latest"]["current_rsi14"] is not None
    assert out["qqq_4h_latest"]["current_bucket"] == "13:30-16:00"
    assert out["qqq_4h"] == out["qqq_4h_candidate"]


def test_incomplete_target_session_fails_closed(tmp_path):
    frame = _frame().drop(pd.Timestamp("2026-09-11 15:30", tz="America/New_York"))
    path = tmp_path / "market_inputs.json"
    path.write_text(json.dumps({
        "session_date": "2026-09-11",
        "generated_at": "2026-09-12T00:00:00Z",
        "coverage": 1.0,
        "source": "test",
        "schema_version": "v38.market_inputs.1",
        "calculation_version": "test",
        "series": {},
    }), encoding="utf-8")
    out = patch_market_inputs_with_qqq_intraday(
        path,
        frame=frame,
        target_session="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
    )
    assert out["qqq_4h_status"] == "DATA_REQUIRED"
    assert out["qqq_4h_trading_gate_eligible"] is False
    assert out["qqq_4h_reason"] == "QQQ_CANONICAL_4H_INCOMPLETE"
    assert out["qqq_4h_rejected_partial_count"] >= 1
