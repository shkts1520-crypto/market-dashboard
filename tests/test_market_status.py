import json

from v38.market_status import normalize_market_statuses

SESSION = "2026-09-10"


def dump(root, name, obj):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def meta(**extra):
    obj = {
        "session_date": SESSION,
        "generated_at": "2026-09-11T00:00:00Z",
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "fixture.1",
        "calculation_version": "fixture",
    }
    obj.update(extra)
    return obj


def test_market_mode_data_required_promotes_to_top_status(tmp_path):
    dump(tmp_path, "market_state.json", meta(market_mode="DATA_REQUIRED", mode_reason="BREADTH50_MISSING"))
    normalize_market_statuses(tmp_path, session_date=SESSION)
    obj = json.loads((tmp_path / "market_state.json").read_text())
    assert obj["status"] == "DATA_REQUIRED"
    assert obj["reason"] == "BREADTH50_MISSING"


def test_core12_unresolved_ranking_promotes_to_top_status(tmp_path):
    dump(tmp_path, "core12.json", meta(ranking_status="DATA_REQUIRED", ranking_reason="CLASSIFICATION_COVERAGE_INCOMPLETE"))
    normalize_market_statuses(tmp_path, session_date=SESSION)
    obj = json.loads((tmp_path / "core12.json").read_text())
    assert obj["status"] == "DATA_REQUIRED"
    assert obj["reason"] == "CLASSIFICATION_COVERAGE_INCOMPLETE"


def test_ready_market_and_core12_are_stamped_ready(tmp_path):
    dump(tmp_path, "market_state.json", meta(market_mode="ATTACK", mode_reason="BLUE_GREEN_BREADTH_GE_60"))
    dump(tmp_path, "core12.json", meta(ranking_status="OK", ranking=[]))
    normalize_market_statuses(tmp_path, session_date=SESSION)
    market = json.loads((tmp_path / "market_state.json").read_text())
    core = json.loads((tmp_path / "core12.json").read_text())
    assert market["status"] == "READY"
    assert core["status"] == "READY"
