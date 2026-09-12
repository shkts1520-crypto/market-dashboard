from __future__ import annotations

import json
from datetime import date, timedelta

from v38.rs_history import build_rs_history


def _current_rs(session: str = "2026-09-11"):
    rows = []
    for i, ticker in enumerate("ABCDEFGHIJKL", start=1):
        rows.append({
            "ticker": ticker,
            "rs63": 101.0 - i,
            "rs126": 100.5 - i,
            "rs189": 101.0 - i,
        })
    return {"session_date": session, "rows": rows}


def test_archive_seed_is_used_only_for_rs189_and_never_fakes_short_windows(tmp_path):
    sessions = tmp_path / "history" / "sessions"
    sessions.mkdir(parents=True)
    prior = {
        "session_date": "2026-09-10",
        "rs_top": [
            {"ticker": ticker, "rs63": 50 - i, "rs126": 60 - i, "rs189": 100 - i}
            for i, ticker in enumerate("BACDEFGHIJK", start=1)
        ],
    }
    (sessions / "2026-09-10.json").write_text(json.dumps(prior), encoding="utf-8")

    out = build_rs_history(
        tmp_path / "history",
        _current_rs(),
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
    )

    assert out["observed_sessions"] == 2
    assert out["windows"]["189"]["available_sessions"] == 2
    one_day = out["windows"]["189"]["comparisons"][0]
    assert one_day["status"] == "READY"
    assert one_day["target_session"] == "2026-09-10"

    assert out["windows"]["63"]["available_sessions"] == 1
    assert out["windows"]["63"]["comparisons"][0]["status"] == "ACCUMULATING"
    assert out["windows"]["126"]["available_sessions"] == 1
    assert out["persistence"]["classification_ready"] is False
    assert all(row["classification"] == "蓄積中" for row in out["persistence"]["rows"])


def test_21_observed_sessions_enable_original_persistence_classification(tmp_path):
    start = date(2026, 8, 13)
    snapshots = []
    for i in range(20):
        day = (start + timedelta(days=i)).isoformat()
        rows = [
            {"rank": 1, "ticker": "A", "rs63": 80 + i, "rs126": 85 + i / 2, "rs189": 90 + i / 10},
        ]
        rows += [
            {"rank": rank, "ticker": f"X{rank:02d}", "rs63": 70 - rank, "rs126": 70 - rank, "rs189": 80 - rank}
            for rank in range(2, 25)
        ]
        snapshots.append({
            "date": day,
            "windows": {"63": rows[:10], "126": rows[:10], "189": rows},
            "window_source": {"63": "CURRENT_RS_FULL_UNIVERSE", "126": "CURRENT_RS_FULL_UNIVERSE", "189": "CURRENT_RS_FULL_UNIVERSE"},
        })

    current = {
        "session_date": "2026-09-11",
        "rows": [
            {"ticker": "A", "rs63": 100.0, "rs126": 96.0, "rs189": 93.0},
        ] + [
            {"ticker": f"X{rank:02d}", "rs63": 70 - rank, "rs126": 70 - rank, "rs189": 80 - rank}
            for rank in range(2, 25)
        ],
    }
    existing = {"snapshots": snapshots}
    out = build_rs_history(
        tmp_path / "history",
        current,
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
        existing=existing,
    )

    persistence = out["persistence"]
    assert persistence["classification_ready"] is True
    assert persistence["observed_sessions"] == 21
    a = next(row for row in persistence["rows"] if row["ticker"] == "A")
    assert a["top10_days"] == 21
    assert a["top24_pct"] == 100.0
    assert a["consecutive_top10_observed"] == 21
    assert a["classification"] == "定着"


def test_existing_short_window_snapshots_accumulate_without_retrospective_backfill(tmp_path):
    prior = {
        "date": "2026-09-10",
        "windows": {
            "63": [{"rank": 1, "ticker": "B", "rs63": 99, "rs126": 90, "rs189": 80}],
            "126": [{"rank": 1, "ticker": "B", "rs63": 99, "rs126": 99, "rs189": 80}],
            "189": [{"rank": 1, "ticker": "B", "rs63": 99, "rs126": 99, "rs189": 99}],
        },
        "window_source": {"63": "CURRENT_RS_FULL_UNIVERSE", "126": "CURRENT_RS_FULL_UNIVERSE", "189": "CURRENT_RS_FULL_UNIVERSE"},
    }
    out = build_rs_history(
        tmp_path / "history",
        _current_rs(),
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
        existing={"snapshots": [prior]},
    )
    for period in ("63", "126", "189"):
        cmp = out["windows"][period]["comparisons"][0]
        assert cmp["status"] == "READY"
        assert cmp["target_session"] == "2026-09-10"
