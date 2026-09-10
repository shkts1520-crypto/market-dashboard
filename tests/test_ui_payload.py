import json

from v38.ui_payload import (
    DATA_REQUIRED,
    READY,
    STALE,
    build_ui_payload,
    discover_target_session,
    write_ui_payload,
)


GENERATED = "2026-09-11T00:00:00+00:00"
SESSION = "2026-09-10"


def shard(session=SESSION):
    return {
        "session_date": session,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "x",
        "calculation_version": "x",
    }


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_no_inputs_fail_closed(tmp_path):
    payload = build_ui_payload(
        tmp_path,
        generated_at=GENERATED,
    )
    assert payload["status"] == DATA_REQUIRED
    assert payload["session_date"] is None
    assert len(payload["sections"]) == 9


def test_state_json_is_session_authority(tmp_path):
    write(
        tmp_path / "state.json",
        {"session_date": SESSION},
    )
    found = discover_target_session(tmp_path)
    assert found["session_date"] == SESSION
    assert found["reason"] == "STATE_AUTHORITY"


def test_single_session_consensus_is_allowed(tmp_path):
    write(tmp_path / "core12.json", shard())
    found = discover_target_session(tmp_path)
    assert found["session_date"] == SESSION
    assert found["reason"] == "SINGLE_SESSION_CONSENSUS"


def test_multiple_sessions_without_state_are_stale(tmp_path):
    write(tmp_path / "core12.json", shard("2026-09-10"))
    write(tmp_path / "rs.json", shard("2026-09-09"))
    found = discover_target_session(tmp_path)
    assert found["status"] == STALE
    payload = build_ui_payload(
        tmp_path,
        generated_at=GENERATED,
    )
    assert payload["status"] == STALE


def test_ready_single_input_section(tmp_path):
    write(tmp_path / "core12.json", shard())
    payload = build_ui_payload(
        tmp_path,
        generated_at=GENERATED,
        target_session=SESSION,
    )
    assert payload["sections"]["t-port"]["status"] == READY
    assert payload["sections"]["t-alloc"]["status"] == DATA_REQUIRED


def test_stale_component_dominates_section(tmp_path):
    write(tmp_path / "core12.json", shard("2026-09-09"))
    payload = build_ui_payload(
        tmp_path,
        generated_at=GENERATED,
        target_session=SESSION,
    )
    assert payload["sections"]["t-port"]["status"] == STALE
    assert payload["status"] == STALE


def test_daily_requires_all_four_authoritative_inputs(tmp_path):
    for name in (
        "market_state.json",
        "breadth.json",
        "mc57.json",
        "f123.json",
    ):
        write(tmp_path / name, shard())
    payload = build_ui_payload(
        tmp_path,
        generated_at=GENERATED,
        target_session=SESSION,
    )
    assert payload["sections"]["t-market"]["status"] == READY


def test_atomic_payload_write(tmp_path):
    out = write_ui_payload(
        tmp_path / "data",
        tmp_path / "site" / "data" / "ui_payload.json",
        generated_at=GENERATED,
    )
    obj = json.loads(out.read_text(encoding="utf-8"))
    assert obj["status"] == DATA_REQUIRED
    assert "NaN" not in out.read_text(encoding="utf-8")
