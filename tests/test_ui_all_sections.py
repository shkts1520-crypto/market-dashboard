from __future__ import annotations

import json

from v38.ui_view_model import DATA_REQUIRED, READY, build_ui_view_model

SESSION = "2026-09-10"
GENERATED = "2026-09-11T00:00:00Z"


def dump(root, name, obj):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def meta(**extra):
    obj = {
        "session_date": SESSION,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "fixture.1",
        "calculation_version": "fixture",
    }
    obj.update(extra)
    return obj


def base_inputs(root):
    dump(root, "state.json", meta())
    dump(root, "breadth.json", meta(breadth50=61.0, breadth200=70.0))
    dump(
        root,
        "f123.json",
        meta(
            f1={"status": "FULL", "value": 0.10, "severity": "NORMAL"},
            f2={"status": "OK", "value": 0.20, "severity": "NORMAL"},
            f3={"status": "OK", "value": 0.30, "severity": "NORMAL"},
        ),
    )
    dump(root, "rs.json", meta(rows=[{"ticker": "AAA", "price": 100, "rs189": 99, "rs63": 98, "ddv20": 2e7}]))
    dump(
        root,
        "market_inputs.json",
        meta(series={s: [{"date": SESSION, "close": 100.0}] for s in ("QQQ", "TQQQ", "^VIX", "NQ=F", "SPY")}),
    )
    dump(root, "nqsar.json", meta(status="AUTHORITATIVE_INPUT", state="Green"))
    dump(root, "mc57.json", meta(status="READY", mc57=42.0))
    dump(root, "market_state.json", meta(status="READY", market_mode="ATTACK"))


def test_all_non_daily_sections_are_exposed_from_authoritative_shards(tmp_path):
    base_inputs(tmp_path)
    dump(
        tmp_path,
        "positions.json",
        meta(status="READY", rows=[{"ticker": "AAA", "quantity": 10, "sleeve": "NORMAL_STOCK"}]),
    )
    dump(
        tmp_path,
        "core12.json",
        meta(status="READY", ranking_status="OK", market_mode="ATTACK", max_new_total_slots=12,
             ranking=[{"ticker": "AAA", "final_score": 97.0}]),
    )
    dump(tmp_path, "rotation.json", meta(status="READY", rows=[{"theme": "AI", "score": 95}]))
    dump(tmp_path, "weekly.json", meta(status="READY", state="Green", rows=[]))
    dump(tmp_path, "options/index.json", meta(status="READY", rows=[{"ticker": "AAA", "signal": "UP"}]))
    dump(
        tmp_path,
        "publish.json",
        meta(status="READY", full_v38_ready=True, ready_count=11, required_count=11, blockers=[]),
    )
    dump(tmp_path, "rules.json", meta(status="READY", rules={"allocation": {"normal_tqqq_pct": 30}}))

    out = build_ui_view_model(tmp_path)
    for key in ("positions", "core12", "rotation", "weekly", "options", "publish", "rules"):
        assert key in out
        assert out[key]["status"] == READY

    assert out["positions"]["rows"][0]["ticker"] == "AAA"
    assert out["core12"]["rows"][0]["final_score"] == 97.0
    assert out["rotation"]["rows"][0]["theme"] == "AI"
    assert out["weekly"]["state"] == "Green"
    assert out["options"]["rows"][0]["signal"] == "UP"
    assert out["publish"]["full_v38_ready"] is True
    assert out["rules"]["rows"][0]["key"] == "allocation.normal_tqqq_pct"


def test_declared_data_required_section_reason_survives_to_view_model(tmp_path):
    base_inputs(tmp_path)
    dump(
        tmp_path,
        "rotation.json",
        meta(status="DATA_REQUIRED", reason="PEER_THEME_AUTHORITATIVE_INPUT_MISSING_OR_STALE", rows=[]),
    )
    out = build_ui_view_model(tmp_path)
    assert out["rotation"]["status"] == DATA_REQUIRED
    assert out["rotation"]["reason"] == "PEER_THEME_AUTHORITATIVE_INPUT_MISSING_OR_STALE"


def test_core12_ranking_dependency_cannot_look_ready(tmp_path):
    base_inputs(tmp_path)
    dump(
        tmp_path,
        "core12.json",
        meta(ranking_status="DATA_REQUIRED", ranking_reason="CLASSIFICATION_COVERAGE_INCOMPLETE", ranking=[]),
    )
    out = build_ui_view_model(tmp_path)
    assert out["core12"]["status"] == DATA_REQUIRED
    assert out["core12"]["reason"] == "CLASSIFICATION_COVERAGE_INCOMPLETE"
