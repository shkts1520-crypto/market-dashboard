from __future__ import annotations

import json
from pathlib import Path

from v38.history_archive import (
    build_history_index,
    build_session_snapshot,
    materialize_old_top24_from_history,
    stage_session_snapshot,
)


SESSION = "2026-09-10"
GENERATED = "2026-09-11T13:04:51Z"


def write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def meta(**extra):
    return {
        "session_date": SESSION,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "fixture.1",
        "calculation_version": "fixture.1",
        "status": "READY",
        **extra,
    }


def source_tree(root: Path) -> None:
    write(root / "state.json", meta())
    write(
        root / "rs.json",
        meta(rows=[{
            "ticker": f"T{i:03d}",
            "price": 10 + i,
            "rs189": 100 - i,
            "rs126": 90 - i,
            "rs63": 80 - i,
            "ddv20": 20_000_000,
        } for i in range(120)]),
    )
    write(root / "breadth.json", meta(breadth50=61.0, breadth200=72.0))
    write(
        root / "f123.json",
        meta(
            f1={"status": "DATA_REQUIRED", "value": None},
            f2={"status": "OK", "value": 0.25, "severity": "NORMAL"},
            f3={"status": "OK", "value": 0.10, "severity": "NORMAL"},
        ),
    )
    write(
        root / "market_inputs.json",
        meta(series={"QQQ": [{"date": SESSION, "close": 500.0}]}),
    )
    write(
        root / "acquisition_manifest.json",
        meta(
            universe={"active_universe": 120},
            yahoo={"target_session_coverage": 1.0},
            authority_status={
                "nqsar_status": {"status": "READY"},
                "mc57_status": {"status": "DATA_REQUIRED"},
            },
        ),
    )
    write(root / "publish.json", meta(full_v38_ready=False, ready_count=5, required_count=11))


def test_snapshot_is_compact_current_session_evidence(tmp_path: Path):
    source_tree(tmp_path)
    out = build_session_snapshot(tmp_path)
    assert out["session_date"] == SESSION
    assert out["daily"]["breadth50"] == 61.0
    assert out["daily"]["market_closes"]["QQQ"] == 500.0
    assert len(out["rs_top"]) == 100
    assert "positions" not in out


def test_stage_snapshot_merges_existing_history_index(tmp_path: Path):
    data = tmp_path / "data"
    source_tree(data)
    old = meta()
    old["session_date"] = "2026-09-09"
    old["rs_top"] = [{"ticker": "OLD"}]
    old["acquisition"] = {"authority_status": {}}
    write(data / "history" / "sessions" / "2026-09-09.json", old)

    session_path, index_path = stage_session_snapshot(
        data,
        data / "history",
        tmp_path / "stage-history",
    )
    assert session_path.name == f"{SESSION}.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["session_count"] == 2
    assert index["first_session"] == "2026-09-09"
    assert index["latest_session"] == SESSION


def test_old_top24_materializes_only_after_20_archived_session_lag(tmp_path: Path):
    history = tmp_path / "history"
    days = [f"2026-08-{day:02d}" for day in range(10, 30)]
    for index, day in enumerate(days):
        write(
            history / "sessions" / f"{day}.json",
            {
                "session_date": day,
                "coverage": 1.0,
                "rs_top": [{"ticker": f"T{i:02d}"} for i in range(100)],
            },
        )
    current = tmp_path / "rs.json"
    write(current, {"session_date": SESSION, "rows": []})
    out = materialize_old_top24_from_history(
        history,
        current,
        tmp_path / "old_top24.json",
        target_session=SESSION,
        generated_at=GENERATED,
    )
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["lag_sessions"] == 20
    assert payload["pit_frozen"] is True
    assert len(payload["session_sequence"]) == 21
    assert len(payload["rows"]) == 24
    assert payload["target_session_date"] == SESSION


def test_old_top24_falls_back_to_retained_reconstructed_history(tmp_path: Path):
    history = tmp_path / "history"
    write(
        history / "sessions" / "2026-09-09.json",
        {"session_date": "2026-09-09", "coverage": 1.0, "rs_top": []},
    )
    sequence = [
        "2026-08-12", "2026-08-13", "2026-08-14", "2026-08-17", "2026-08-18", "2026-08-19",
        "2026-08-20", "2026-08-21", "2026-08-24", "2026-08-25", "2026-08-26",
        "2026-08-27", "2026-08-28", "2026-08-31", "2026-09-01", "2026-09-02",
        "2026-09-03", "2026-09-04", "2026-09-08", "2026-09-09", "2026-09-10",
    ]
    old_rows = []
    for i in range(100):
        old_rows.append({
            "ticker": f"T{i:03d}",
            "price": 20.0,
            "ddv20": 20_000_000.0,
            "sma50": 90.0 if i < 5 else 110.0,
            "sma200": 100.0,
            "rs189": 100.0 - i * 0.1,
        })
    reconstructed_rows = [
        {
            "date": day,
            "coverage": 1.0,
            "rs_top": old_rows if index == 0 else [],
        }
        for index, day in enumerate(sequence)
    ]
    write(
        history / "reconstructed_stock_metrics.json",
        {
            "session_date": SESSION,
            "status": "READY",
            "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
            "source": "fixture historical OHLC",
            "survivorship_warning": True,
            "provenance": {"membership_scope": "current universe as of 2026-09-10"},
            "rows": reconstructed_rows,
        },
    )
    current = tmp_path / "rs.json"
    write(current, {"session_date": SESSION, "rows": []})

    out = materialize_old_top24_from_history(
        history,
        current,
        tmp_path / "old_top24.json",
        target_session=SESSION,
        generated_at=GENERATED,
    )
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["session_date"] == "2026-08-12"
    assert payload["target_session_date"] == SESSION
    assert payload["source"] == "derived:retained-current-universe-historical-stock-metrics"
    assert payload["provenance"]["pit_universe"] is False
    assert payload["provenance"]["survivorship_warning"] is True
    assert len(payload["session_sequence"]) == 21
    assert [row["ticker"] for row in payload["rows"][:3]] == ["T005", "T006", "T007"]
    assert payload["rows"][-1]["ticker"] == "T028"


def test_old_top24_stays_unavailable_with_less_than_20_prior_sessions(tmp_path: Path):
    history = tmp_path / "history"
    write(
        history / "sessions" / "2026-09-09.json",
        {"session_date": "2026-09-09", "coverage": 1.0, "rs_top": []},
    )
    current = tmp_path / "rs.json"
    write(current, {"session_date": SESSION, "rows": []})
    assert materialize_old_top24_from_history(
        history,
        current,
        tmp_path / "old_top24.json",
        target_session=SESSION,
        generated_at=GENERATED,
    ) is None


def test_index_replaces_same_session_instead_of_duplicating(tmp_path: Path):
    snapshot = {
        "session_date": SESSION,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "rs_top": [],
        "acquisition": {"authority_status": {}},
    }
    write(tmp_path / "sessions" / f"{SESSION}.json", {**snapshot, "coverage": 0.5})
    out = build_history_index(tmp_path, snapshot)
    assert out["session_count"] == 1
    assert out["rows"][0]["coverage"] == 1.0
