from __future__ import annotations

import pandas as pd

from v38.recovered_live_inputs import (
    NEUTRAL_THEME_SCORE,
    _nqsar_state_series,
    build_classifications,
    build_neutral_theme_scores,
    build_recovered_nqsar,
    build_rotation_diagnostics,
)


def _market_inputs(n: int = 120):
    idx = pd.bdate_range("2026-03-30", periods=n)
    rows = []
    for i, day in enumerate(idx):
        close = 18000.0 + i * 12.0
        rows.append({
            "date": day.strftime("%Y-%m-%d"),
            "open": close - 5,
            "high": close + 25,
            "low": close - 25,
            "close": close,
        })
    return {"series": {"NQ=F": rows}}, idx[-1].strftime("%Y-%m-%d")


def test_recovered_nqsar_builds_current_estimate_and_history():
    market, session = _market_inputs()
    out = build_recovered_nqsar(market, session_date=session, generated_at="2026-09-12T00:00:00Z")
    assert out["status"] == "READY"
    assert out["state"] in {"Blue", "Green", "Yellow", "Red"}
    assert out["input_kind"] == "RECOVERED_YAHOO_FSM_ESTIMATE"
    assert out["authoritative_exact"] is False
    assert out["parameters"]["psar_max"] == 0.08
    assert out["history"][-1]["date"] == session


def test_nqsar_series_returns_valid_states():
    idx = pd.bdate_range("2026-01-02", periods=90)
    frame = pd.DataFrame({
        "high": [100 + i * 0.5 + 1 for i in range(90)],
        "low": [100 + i * 0.5 - 1 for i in range(90)],
        "close": [100 + i * 0.5 for i in range(90)],
    }, index=idx)
    out = _nqsar_state_series(frame)
    assert len(out) == 90
    assert set(out["state"]).issubset({"Blue", "Green", "Yellow", "Red"})


def test_structural_clinical_biotech_requires_all_conditions_and_fail_opens_missing_revenue():
    rs = {"rows": [
        {"ticker": "BIO1", "industry": "Biotechnology"},
        {"ticker": "BIO2", "industry": "Biotechnology"},
        {"ticker": "BIG", "industry": "Biotechnology"},
        {"ticker": "TECH", "industry": "Semiconductors"},
    ]}
    fundamentals = {
        "BIO1": {"industry": "Biotechnology", "market_cap_basic": 2e9, "total_revenue_ttm": 20e6},
        "BIO2": {"industry": "Biotechnology", "market_cap_basic": 2e9, "total_revenue_ttm": None},
        "BIG": {"industry": "Biotechnology", "market_cap_basic": 20e9, "total_revenue_ttm": 20e6},
        "TECH": {"industry": "Semiconductors", "market_cap_basic": 2e9, "total_revenue_ttm": 20e6},
    }
    out = build_classifications(rs, fundamentals, session_date="2026-09-11", generated_at="2026-09-12T00:00:00Z")
    by_ticker = {row["ticker"]: row for row in out["rows"]}
    assert by_ticker["BIO1"]["structural_clinical_biotech"] is True
    assert by_ticker["BIO2"]["structural_clinical_biotech"] is False
    assert by_ticker["BIG"]["structural_clinical_biotech"] is False
    assert by_ticker["TECH"]["structural_clinical_biotech"] is False


def test_missing_fine_theme_is_neutral_and_not_industry_substitute():
    rs = {"rows": [
        {"ticker": "AAA", "industry": "Semiconductors", "rs63": 90.0},
        {"ticker": "BBB", "industry": "Semiconductors", "rs63": 80.0},
        {"ticker": "CCC", "industry": "Semiconductors", "rs63": 70.0},
    ]}
    out = build_neutral_theme_scores(rs, session_date="2026-09-11", generated_at="2026-09-12T00:00:00Z")
    assert out["status"] == "READY"
    assert out["rules"]["industry_substitution"] is False
    assert all(row["peer_theme_score"] == NEUTRAL_THEME_SCORE for row in out["rows"])


def test_rotation_diagnostics_are_display_only():
    rs = {"coverage": 1.0, "rows": [
        {"ticker": "AAA", "sector": "Technology", "industry": "Semiconductors", "ret20": 0.2, "ret63": 0.3, "rs63": 95},
        {"ticker": "BBB", "sector": "Technology", "industry": "Semiconductors", "ret20": 0.1, "ret63": 0.2, "rs63": 90},
        {"ticker": "CCC", "sector": "Technology", "industry": "Semiconductors", "ret20": 0.0, "ret63": 0.1, "rs63": 85},
    ]}
    out = build_rotation_diagnostics(rs, session_date="2026-09-11", generated_at="2026-09-12T00:00:00Z")
    assert out["status"] == "READY"
    assert out["trade_input"] is False
    assert out["industry"][0]["group"] == "Semiconductors"
    assert out["industry"][0]["leaders"] == ["AAA", "BBB", "CCC"]
