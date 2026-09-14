from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from v38.display_observations import (
    build_ftd_proxy,
    build_net_liquidity,
    build_sentiment,
    update_nqsar_history,
)


def test_net_liquidity_uses_fixed_fred_units_and_asof_alignment() -> None:
    dates = pd.date_range("2026-07-01", periods=16, freq="W-WED")
    fred = {
        "WALCL": [(day, 8_000_000.0 + i * 10_000.0) for i, day in enumerate(dates)],
        "RRPONTSYD": [(dates[1], 1_000.0), (dates[8], 900.0)],
        "WTREGEN": [(dates[2], 500_000.0), (dates[10], 550_000.0)],
    }
    out = build_net_liquidity(fred, asof=dates[-1].strftime("%Y-%m-%d"))
    assert out["status"] == "READY"
    # The first two WALCL observations are skipped because TGA is not yet known.
    assert out["series"][0]["date"] == dates[2].strftime("%Y-%m-%d")
    expected = (8_000_000.0 + 15 * 10_000.0) / 1e6 - 900.0 / 1e3 - 550_000.0 / 1e6
    assert out["current_t"] == expected
    assert out["formula"] == "WALCL/1e6 - RRPONTSYD/1e3 - WTREGEN/1e6"


def _market_frame(index: pd.DatetimeIndex, close_scale: float, volume_scale: float) -> pd.DataFrame:
    close = pd.Series([close_scale + i * 0.05 for i in range(len(index))], index=index)
    volume = pd.Series([volume_scale + (i % 11) * 1000 for i in range(len(index))], index=index)
    return pd.DataFrame({"Close": close, "Volume": volume})


def test_sentiment_available_component_average_is_ready() -> None:
    index = pd.bdate_range("2025-01-02", periods=320)
    market = {
        "TQQQ": _market_frame(index, 60.0, 3_000_000),
        "SOXL": _market_frame(index, 40.0, 2_000_000),
        "SQQQ": _market_frame(index, 30.0, 1_500_000),
        "SOXS": _market_frame(index, 20.0, 1_000_000),
        "^SKEW": _market_frame(index, 130.0, 1),
    }
    fear_greed = pd.Series(range(40, 40 + len(index)), index=index, dtype=float).clip(upper=100)
    put_call = pd.Series([0.7 + (i % 40) * 0.002 for i in range(len(index))], index=index, dtype=float)
    parabolic = pd.Series([2.0 + (i % 80) * 0.03 for i in range(len(index))], index=index, dtype=float)
    out = build_sentiment(
        market,
        session=index[-1].strftime("%Y-%m-%d"),
        fear_greed=fear_greed,
        put_call=put_call,
        parabolic=parabolic,
    )
    assert out["status"] == "READY"
    assert {"lever", "parab", "fng", "pc"}.issubset(set(out["composite_component_keys"]))
    assert 0.0 <= out["current"] <= 100.0
    assert out["trading_gate_eligible"] is False


def _ftd_rows() -> list[dict]:
    dates = pd.bdate_range("2025-06-02", periods=265)
    closes = [100.0] * 260 + [90.0, 91.0, 92.0, 93.0, 94.3]
    volumes = [100.0] * 264 + [200.0]
    rows = []
    for day, close, volume in zip(dates, closes, volumes):
        rows.append({
            "date": day.strftime("%Y-%m-%d"),
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": volume,
        })
    return rows


def test_ftd_proxy_requires_day4_gain_and_higher_volume() -> None:
    rows = _ftd_rows()
    out = build_ftd_proxy({"QQQ": rows, "SPY": rows})
    assert out["status"] == "READY"
    assert len(out["rows"]) == 2
    for row in out["rows"]:
        assert row["state"] == "FTD_ACTIVE"
        assert row["ftd_day"] == 4
        assert row["ftd_gain"] >= 0.0125
        assert row["trading_gate_eligible"] if "trading_gate_eligible" in row else True
    assert out["trading_gate_eligible"] is False


def test_nqsar_history_appends_only_authoritative_observations(tmp_path: Path) -> None:
    root = tmp_path / "data"
    (root / "history").mkdir(parents=True)
    (root / "nqsar.json").write_text(
        json.dumps({
            "session_date": "2026-09-11",
            "generated_at": "2026-09-12T00:00:00Z",
            "source": "sar_state.txt",
            "state": "Green",
        }),
        encoding="utf-8",
    )
    out = update_nqsar_history(
        root,
        session="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
    )
    assert out["status"] == "READY"
    assert out["records"] == [{
        "date": "2026-09-11",
        "state": "Green",
        "source": "sar_state.txt",
        "generated_at": "2026-09-12T00:00:00Z",
    }]
    stored = json.loads((root / "history" / "nqsar_state_history.json").read_text(encoding="utf-8"))
    assert stored["history_kind"] == "AUTHORITATIVE_OBSERVED_ONLY"
