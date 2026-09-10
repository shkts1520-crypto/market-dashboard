import json

from v38.diagnostics import (
    atomic_write_json,
    build_diagnostics,
)

SESSION = "2026-09-08"
GENERATED = "2026-09-10T19:00:00+09:00"


def good_nq():
    return {
        "verified": True,
        "fsm_version": "v1",
        "golden_fixture_sha256": "abc",
    }


def good_mc():
    return {
        "verified": True,
        "etf_universe": [
            f"ETF{i:02d}"
            for i in range(57)
        ],
        "golden_fixture_sha256": "def",
    }


def test_diagnostics_blocks_both_components_without_references():
    out = build_diagnostics(
        session_date=SESSION,
        generated_at=GENERATED,
    )

    assert out["status"] == "DATA_REQUIRED"
    assert out["production_ready"] is False

    assert out["blocked_components"] == [
        "NQSAR",
        "MC57",
    ]


def test_diagnostics_keeps_components_separate():
    out = build_diagnostics(
        session_date=SESSION,
        generated_at=GENERATED,
        nqsar_reference=good_nq(),
    )

    assert out["nqsar"]["status"] == "READY"
    assert out["mc57"]["status"] == "DATA_REQUIRED"
    assert out["blocked_components"] == ["MC57"]


def test_diagnostics_ready_requires_both_authoritative_packages():
    out = build_diagnostics(
        session_date=SESSION,
        generated_at=GENERATED,
        nqsar_reference=good_nq(),
        mc57_reference=good_mc(),
    )

    assert out["status"] == "READY"
    assert out["production_ready"] is True
    assert out["blocked_components"] == []


def test_diagnostics_preserves_common_session_metadata():
    out = build_diagnostics(
        session_date=SESSION,
        generated_at=GENERATED,
    )

    assert (
        out["session_date"]
        == out["nqsar"]["session_date"]
        == out["mc57"]["session_date"]
    )

    assert (
        out["generated_at"]
        == out["nqsar"]["generated_at"]
        == out["mc57"]["generated_at"]
    )


def test_atomic_json_is_valid_and_contains_no_nan(
    tmp_path,
):
    out = build_diagnostics(
        session_date=SESSION,
        generated_at=GENERATED,
    )

    path = atomic_write_json(
        tmp_path / "diagnostics.json",
        out,
    )

    loaded = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert loaded["status"] == "DATA_REQUIRED"

    assert (
        "NaN"
        not in path.read_text(
            encoding="utf-8"
        )
    )
