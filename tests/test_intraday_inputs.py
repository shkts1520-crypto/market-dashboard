from __future__ import annotations

import json

import pandas as pd

from v38.intraday_inputs import (
    add_candidate_rsi,
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
    rows = normalise_qqq_60m(_frame(), target_session="2026-09-11")
    assert rows
    assert rows[-1]["date"] == "2026-09-11"
    assert rows[-1]["timestamp"].startswith("2026-09-11T15:30")
    assert all("T09:30" in row["timestamp"] or "T10:30" in row["timestamp"] or "T11:30" in row["timestamp"] or "T12:30" in row["timestamp"] or "T13:30" in row["timestamp"] or "T14:30" in row["timestamp"] or "T15:30" in row["timestamp"] for row in rows)


def test_candidate_aggregation_has_two_rth_buckets_and_rsi():
    hourly = normalise_qqq_60m(_frame(), target_session="2026-09-11")
    candidate = add_candidate_rsi(aggregate_rth_4h_candidate(hourly))
    latest = [row for row in candidate if row["date"] == "2026-09-11"]
    assert [row["bucket"] for row in latest] == ["09:30-13:30", "13:30-16:00"]
    assert latest[0]["source_bar_count"] == 4
    assert latest[1]["source_bar_count"] == 3
    assert candidate[-1]["rsi14"] is not None


def test_patch_marks_4h_candidate_display_only_pending_fixture(tmp_path):
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
    assert out["qqq_4h_status"] == "READY_DISPLAY_ONLY"
    assert out["qqq_4h_trading_gate_eligible"] is False
    assert out["qqq_4h_reason"] == "RTH_60M_AGGREGATED_PENDING_STAGE56_4H_FIXTURE"
    assert out["qqq_4h_latest"]["current_rsi14"] is not None
