from __future__ import annotations

import pandas as pd

from v38.vwap_restore import add_vwap_columns, classify_vwap, inception_from_frame, inception_value, normalize_ohlcv


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=300, freq="B")
    close = pd.Series([100.0 + i * 0.1 for i in range(len(idx))], index=idx)
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=idx,
    )


def test_rolling_vwap_periods_and_inception_are_finite() -> None:
    frame = add_vwap_columns(normalize_ohlcv(_frame()))
    assert frame["vwap63"].notna().sum() >= 238
    assert frame["vwap252"].notna().sum() >= 49
    record, series = inception_from_frame(frame)
    assert record is not None
    assert record["n"] == 300
    assert record["first"] <= record["through"]
    value = inception_value(record)
    assert value is not None and value > 0
    assert len(series) == 300


def test_classify_vwap_keeps_display_only_contract() -> None:
    frame = add_vwap_columns(normalize_ohlcv(_frame()))
    for key in ("vwap63", "vwap252"):
        result = classify_vwap(frame, key)
        assert set(("value", "dist", "break", "touch", "near", "label")) <= set(result)
        assert result["value"] is not None
        assert isinstance(result["break"], bool)
        assert isinstance(result["touch"], bool)
        assert isinstance(result["near"], bool)
