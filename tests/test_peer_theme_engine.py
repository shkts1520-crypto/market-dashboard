from __future__ import annotations

import json

import pandas as pd

from v38.peer_theme_engine import (
    INPUT_VERSION,
    augment_rs_peer_theme_inputs,
    build_strict_loo_peer_theme_scores,
)


def _rs_rows():
    rows = []
    specs = [
        ("A1", "TA", 98.0, 97.0, True),
        ("A2", "TA", 96.0, 95.0, True),
        ("A3", "TA", 94.0, 93.0, True),
        ("B1", "TB", 70.0, 80.0, False),
        ("B2", "TB", 68.0, 78.0, False),
        ("B3", "TB", 66.0, 76.0, True),
        ("C1", "TC", 50.0, 50.0, False),
        ("C2", "TC", 48.0, 48.0, False),
        ("C3", "TC", 46.0, 46.0, False),
    ]
    for ticker, _theme, current, prior, above in specs:
        rows.append({
            "ticker": ticker,
            "rs63": current,
            "rs63_20d": prior,
            "above_ema21": above,
            "rs189": current,
        })
    return rows


def _membership():
    rows = []
    for ticker in ("A1", "A2", "A3"):
        rows.append({"ticker": ticker, "theme_id": "TA", "theme_name": "Theme A", "major_theme": "Major A", "tag_method": "EXACT", "tag_confidence": 1.0})
    for ticker in ("B1", "B2", "B3"):
        rows.append({"ticker": ticker, "theme_id": "TB", "theme_name": "Theme B", "major_theme": "Major B", "tag_method": "EXACT", "tag_confidence": 1.0})
    for ticker in ("C1", "C2", "C3"):
        rows.append({"ticker": ticker, "theme_id": "TC", "theme_name": "Theme C", "major_theme": "Major C", "tag_method": "EXACT", "tag_confidence": 1.0})
    return {"session_date": "2026-09-11", "rows": rows}


def test_strict_loo_peer_theme_score_uses_all_three_components():
    rs = {"session_date": "2026-09-11", "rows": _rs_rows()}
    scores = build_strict_loo_peer_theme_scores(
        rs,
        _membership(),
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
    )
    by_ticker = {row["ticker"]: row for row in scores["rows"]}
    a1 = by_ticker["A1"]
    b1 = by_ticker["B1"]
    assert scores["loo_required"] is True
    assert a1["theme_status"] == "STRICT_LOO_READY"
    assert a1["peer_count"] == 2
    assert a1["theme_rs63_score"] > b1["theme_rs63_score"]
    assert a1["above_ema21_score"] == 100.0
    assert 0.0 <= a1["rank_acceleration_score"] <= 100.0
    assert a1["peer_theme_score"] != 50.0
    assert scores["rules"]["component_weights"] == [1 / 3, 1 / 3, 1 / 3]


def test_missing_theme_is_neutral_not_sector_substitution():
    rs = {"session_date": "2026-09-11", "rows": _rs_rows() + [{"ticker": "MISS", "rs63": 99.0, "rs63_20d": 99.0, "above_ema21": True}]}
    membership = _membership()
    membership["rows"].append({"ticker": "MISS", "theme_id": None, "theme_name": None})
    scores = build_strict_loo_peer_theme_scores(
        rs,
        membership,
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
    )
    miss = {row["ticker"]: row for row in scores["rows"]}["MISS"]
    assert miss["peer_theme_score"] == 50.0
    assert miss["theme_status"] == "MISSING_NEUTRAL"
    assert scores["rules"]["sector_substitution"] is False
    assert scores["rules"]["industry_substitution"] is False


def test_augment_rs_adds_ema21_and_twenty_session_prior_rs63(tmp_path):
    session = "2026-09-11"
    dates = pd.bdate_range(end=session, periods=100)
    rows = []
    for ticker, slope in (("AAA", 1.0), ("BBB", 0.2), ("CCC", -0.1)):
        for index, day in enumerate(dates):
            close = 20.0 + slope * index / 10.0
            rows.append({
                "ticker": ticker,
                "date": day.strftime("%Y-%m-%d"),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000_000.0,
                "is_complete": True,
                "split_checked": True,
                "split_anomaly": False,
            })
    ohlcv = tmp_path / "ohlcv.csv"
    pd.DataFrame(rows).to_csv(ohlcv, index=False)
    rs_path = tmp_path / "rs.json"
    rs_path.write_text(json.dumps({
        "session_date": session,
        "rows": [{"ticker": "AAA"}, {"ticker": "BBB"}, {"ticker": "CCC"}],
    }), encoding="utf-8")

    out = augment_rs_peer_theme_inputs(rs_path, ohlcv)
    by_ticker = {row["ticker"]: row for row in out["rows"]}
    assert out["peer_theme_input_version"] == INPUT_VERSION
    assert out["peer_theme_input_coverage"] == 1.0
    assert by_ticker["AAA"]["ema21"] is not None
    assert by_ticker["AAA"]["above_ema21"] is True
    assert by_ticker["AAA"]["rs63_20d"] > by_ticker["BBB"]["rs63_20d"] > by_ticker["CCC"]["rs63_20d"]
    assert by_ticker["AAA"]["peer_theme_input_status"] == "READY"
