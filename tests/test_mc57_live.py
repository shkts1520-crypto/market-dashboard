import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from v38.mc57_live import (
    CALCULATION_VERSION,
    FIXED_57_ETFS,
    MC57LiveError,
    adjusted_close_series,
    build_mc57_object,
    calculate_mc57_panel,
    load_verified_reference,
)

REFERENCE = Path("config/mc57_reference.json")
GOLDEN = Path("tests/fixtures/mc57_recovery_golden_20260909_11.json")


def _synthetic_closes(periods: int = 4100) -> dict[str, pd.Series]:
    idx = pd.bdate_range("2010-01-04", periods=periods)
    x = np.arange(periods, dtype=float)
    out = {}
    for i, symbol in enumerate(FIXED_57_ETFS):
        # Positive, deterministic histories with ticker-specific cycles/trends.
        values = (
            30.0 + i * 0.7
            + x * (0.006 + (i % 7) * 0.00035)
            + 4.0 * np.sin(x / (13.0 + i % 9) + i * 0.11)
            + 1.3 * np.sin(x / 47.0 + i * 0.07)
        )
        out[symbol] = pd.Series(values, index=idx)
    return out


def test_fixed_57_is_exactly_unique_and_includes_qqqe():
    assert len(FIXED_57_ETFS) == 57
    assert len(set(FIXED_57_ETFS)) == 57
    assert FIXED_57_ETFS[-1] == "QQQE"
    assert "^VIX6M" not in FIXED_57_ETFS


def test_adjusted_close_series_requires_adj_close_and_cuts_target():
    idx = pd.to_datetime(["2026-09-09", "2026-09-10", "2026-09-11"])
    frame = pd.DataFrame(
        {
            "Close": [100.0, 110.0, 120.0],
            "Adj Close": [90.0, 99.0, 108.0],
        },
        index=idx,
    )
    out = adjusted_close_series(frame, target_session="2026-09-10")
    assert list(out.index.strftime("%Y-%m-%d")) == ["2026-09-09", "2026-09-10"]
    assert out.iloc[-1] == 99.0
    assert adjusted_close_series(frame[["Close"]], target_session="2026-09-10").empty


def test_verified_reference_matches_frozen_fixture_sha_and_universe():
    ref = load_verified_reference(REFERENCE, GOLDEN)
    assert ref["verified"] is True
    assert ref["etf_universe"] == list(FIXED_57_ETFS)
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == ref["golden_fixture_sha256"]
    fixture = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert fixture["fixed57"] == list(FIXED_57_ETFS)
    assert [row["date"] for row in fixture["audit_days"]] == [
        "2026-09-09", "2026-09-10", "2026-09-11"
    ]
    assert all(len(row["metric_scores"]) == 12 for row in fixture["audit_days"])


def test_synthetic_full_panel_produces_ready_mc57_contract():
    closes = _synthetic_closes()
    target = closes[FIXED_57_ETFS[0]].index[-1].strftime("%Y-%m-%d")
    panel, metric_frames = calculate_mc57_panel(closes)
    assert target in panel.index.strftime("%Y-%m-%d")
    assert set(metric_frames) == {
        "close_gt_sma10", "close_gt_sma20", "close_gt_sma50", "close_gt_sma200",
        "ret5_gt_0", "ret21_gt_0", "ret63_gt_0", "ret252_gt_0",
        "sma20_gt_sma50", "sma50_gt_sma200", "sma50_gt_sma50_shift20",
        "dd52_continuous_score",
    }
    reference = load_verified_reference(REFERENCE, GOLDEN)
    obj = build_mc57_object(
        closes=closes,
        target_session=target,
        generated_at="2026-09-12T00:00:00Z",
        reference=reference,
        fetch_stats={"synthetic": True},
    )
    assert obj["status"] == "READY"
    assert obj["calculation_version"] == CALCULATION_VERSION
    assert obj["coverage"] == 1.0
    assert obj["coverage_detail"]["current_close_count"] == 57
    assert len(obj["metric_scores"]) == 12
    assert len(obj["etf_universe"]) == 57
    assert 0.0 < obj["mc57"] < 100.0
    assert obj["sigma_prior"] > 0.0
    assert obj["history"]


def test_build_rejects_incomplete_target_close_coverage():
    closes = _synthetic_closes()
    missing = FIXED_57_ETFS[-1]
    closes[missing] = closes[missing].iloc[:-1]
    target = closes[FIXED_57_ETFS[0]].index[-1].strftime("%Y-%m-%d")
    reference = load_verified_reference(REFERENCE, GOLDEN)
    with pytest.raises(MC57LiveError, match="current close coverage"):
        build_mc57_object(
            closes=closes,
            target_session=target,
            generated_at="2026-09-12T00:00:00Z",
            reference=reference,
        )
