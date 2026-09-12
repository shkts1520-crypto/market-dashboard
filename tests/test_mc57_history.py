from __future__ import annotations

import numpy as np
import pandas as pd

from v38.mc57_history import (
    HISTORY_CONTRACT_VERSION,
    UI_HISTORY_LIMIT,
    build_mc57_ui_detail,
    enrich_mc57_history,
)
from v38.mc57_live import FIXED_57_ETFS, build_mc57_object, load_verified_reference


def _closes(periods: int = 4400) -> dict[str, pd.Series]:
    idx = pd.bdate_range("2010-01-04", periods=periods)
    x = np.arange(periods, dtype=float)
    out: dict[str, pd.Series] = {}
    for i, symbol in enumerate(FIXED_57_ETFS):
        values = (
            40.0 + i * 0.5
            + x * (0.006 + (i % 5) * 0.0004)
            + 3.0 * np.sin(x / (15.0 + i % 7) + i * 0.1)
        )
        out[symbol] = pd.Series(values, index=idx)
    return out


def test_enriched_history_contains_fixed57_breadth_and_all_metrics():
    closes = _closes()
    target = closes[FIXED_57_ETFS[0]].index[-1].strftime("%Y-%m-%d")
    reference = load_verified_reference(
        "config/mc57_reference.json",
        "tests/fixtures/mc57_recovery_golden_20260909_11.json",
    )
    base = build_mc57_object(
        closes=closes,
        target_session=target,
        generated_at="2026-09-12T00:00:00Z",
        reference=reference,
    )
    out = enrich_mc57_history(base, closes=closes, target_session=target)

    assert out["history_contract_version"] == HISTORY_CONTRACT_VERSION
    assert out["history_window_sessions"] == 260
    assert len(out["history"]) == 260
    assert len(out["metric_history"]) == 12
    assert all(out["metric_history"][key] for key in out["metric_history"])
    assert set(out["fixed57_breadth"]) == {"sma20", "sma50", "sma200"}
    assert out["history"][-1]["fixed57_breadth_sma50"] == out["fixed57_breadth"]["sma50"]
    assert len(out["history"][-1]["metrics"]) == 12


def test_ui_detail_limits_history_to_126_sessions_without_inference():
    closes = _closes()
    target = closes[FIXED_57_ETFS[0]].index[-1].strftime("%Y-%m-%d")
    reference = load_verified_reference(
        "config/mc57_reference.json",
        "tests/fixtures/mc57_recovery_golden_20260909_11.json",
    )
    base = build_mc57_object(
        closes=closes,
        target_session=target,
        generated_at="2026-09-12T00:00:00Z",
        reference=reference,
    )
    enriched = enrich_mc57_history(base, closes=closes, target_session=target)
    detail = build_mc57_ui_detail(enriched, session=target)

    assert detail["status"] == "READY"
    assert detail["history_sessions"] == UI_HISTORY_LIMIT
    assert len(detail["series"]["mc57"]) == UI_HISTORY_LIMIT
    assert len(detail["series"]["fixed57_breadth_sma20"]) == UI_HISTORY_LIMIT
    assert len(detail["series"]["fixed57_breadth_sma50"]) == UI_HISTORY_LIMIT
    assert len(detail["series"]["fixed57_breadth_sma200"]) == UI_HISTORY_LIMIT
    assert set(detail["metrics"]) == set(enriched["metric_history"])
    assert all(len(points) <= UI_HISTORY_LIMIT for points in detail["metrics"].values())


def test_ui_detail_fails_closed_when_history_contract_is_absent():
    detail = build_mc57_ui_detail(
        {"session_date": "2026-09-11", "status": "READY", "mc57": 40.0},
        session="2026-09-11",
    )
    assert detail["status"] == "DATA_REQUIRED"
    assert detail["reason"] == "MC57_HISTORY_CONTRACT_MISSING"
