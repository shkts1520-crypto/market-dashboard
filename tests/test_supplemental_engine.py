from __future__ import annotations

import json

from v38.supplemental_engine import (
    DATA_REQUIRED,
    READY,
    build_positions_shard,
    build_rotation_shard,
    build_rules_shard,
    build_weekly_shard,
    materialize_supplemental_shards,
)

SESSION = "2026-09-10"
GENERATED = "2026-09-11T00:00:00Z"


def meta(**updates):
    out = {
        "session_date": SESSION,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "fixture.1",
        "calculation_version": "fixture",
    }
    out.update(updates)
    return out


def test_rules_shard_is_current_code_contract():
    out = build_rules_shard(session_date=SESSION, generated_at=GENERATED)
    assert out["status"] == READY
    assert out["rules"]["allocation"]["normal_tqqq_pct"] == 30
    assert out["rules"]["allocation"]["panic_tqqq_target_pct"] == 80
    assert out["rules"]["allocation"]["share_level_golden_ledger_status"] == DATA_REQUIRED
    assert "first QQQ 4H RSI14 touch" in out["rules"]["tqqq_panic"]["trigger"]


def test_weekly_fails_closed_without_authoritative_nqsar():
    out = build_weekly_shard(session_date=SESSION, generated_at=GENERATED, nqsar=None)
    assert out["status"] == DATA_REQUIRED
    assert out["state"] is None


def test_weekly_uses_authoritative_nqsar_without_recomputing_fsm():
    nq = meta(state="Green", status="AUTHORITATIVE_INPUT")
    out = build_weekly_shard(session_date=SESSION, generated_at=GENERATED, nqsar=nq)
    assert out["status"] == READY
    assert out["state"] == "Green"
    assert "not recomputed" in out["note"]


def test_rotation_fails_closed_without_peer_theme_authority():
    out = build_rotation_shard(session_date=SESSION, generated_at=GENERATED, theme_scores=None)
    assert out["status"] == DATA_REQUIRED
    assert out["rows"] == []


def test_rotation_preserves_authoritative_source_order():
    theme = meta(rows=[{"theme": "B", "score": 90}, {"theme": "A", "score": 99}])
    out = build_rotation_shard(session_date=SESSION, generated_at=GENERATED, theme_scores=theme)
    assert out["status"] == READY
    assert [row["theme"] for row in out["rows"]] == ["B", "A"]


def test_positions_require_explicit_ledger_and_never_infer_quantity():
    out = build_positions_shard(
        session_date=SESSION,
        generated_at=GENERATED,
        ledger=None,
        nqsar_state="Green",
    )
    assert out["status"] == DATA_REQUIRED
    assert out["rows"] == []


def test_positions_enrich_normal_stock_action_from_explicit_fields():
    ledger = meta(
        rows=[
            {
                "ticker": "AAA",
                "sleeve": "NORMAL_STOCK",
                "quantity": 10,
                "entry": 100.0,
                "close": 125.0,
                "peak_close": 125.0,
                "partial_taken": False,
            }
        ],
        ledger_version="fixture-ledger-1",
    )
    out = build_positions_shard(
        session_date=SESSION,
        generated_at=GENERATED,
        ledger=ledger,
        nqsar_state="Green",
    )
    assert out["status"] == READY
    assert out["rows"][0]["quantity"] == 10
    assert out["rows"][0]["next_open_action"]["action"] == "SELL_25_PCT_NEXT_OPEN"


def test_materialize_creates_current_fail_closed_shards_and_publish_report(tmp_path):
    for name in ("state.json", "rs.json", "breadth.json", "f123.json"):
        (tmp_path / name).write_text(json.dumps(meta()), encoding="utf-8")

    outputs = materialize_supplemental_shards(
        tmp_path,
        session_date=SESSION,
        generated_at=GENERATED,
    )
    names = {p.relative_to(tmp_path).as_posix() for p in outputs}
    assert "rules.json" in names
    assert "weekly.json" in names
    assert "rotation.json" in names
    assert "positions.json" in names
    assert "mc57.json" in names
    assert "options/index.json" in names
    assert "market_state.json" in names
    assert "core12.json" in names
    assert "publish.json" in names

    weekly = json.loads((tmp_path / "weekly.json").read_text(encoding="utf-8"))
    assert weekly["status"] == DATA_REQUIRED
    publish = json.loads((tmp_path / "publish.json").read_text(encoding="utf-8"))
    assert publish["status"] == READY
    assert publish["full_v38_ready"] is False
    assert publish["blockers"]


def test_materialize_does_not_overwrite_current_authoritative_mc57(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps(meta()), encoding="utf-8")
    authoritative = meta(status="READY", mc57=42.0, schema_version="v38.mc57.1")
    (tmp_path / "mc57.json").write_text(json.dumps(authoritative), encoding="utf-8")
    materialize_supplemental_shards(
        tmp_path,
        session_date=SESSION,
        generated_at=GENERATED,
    )
    got = json.loads((tmp_path / "mc57.json").read_text(encoding="utf-8"))
    assert got["mc57"] == 42.0
