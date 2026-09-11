from __future__ import annotations

import json
from pathlib import Path

import pytest

from v38.authority_contracts import AuthorityContractError
from v38.authority_status import sync_acquisition_manifest
from v38.extended_authority_contracts import validate_full_authority

SESSION = "2026-09-08"
SEQUENCE = [
    "2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
    "2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21",
    "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
    "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
    "2026-09-08",
]


def old_top24():
    return {
        "session_date": "2026-08-10",
        "target_session_date": SESSION,
        "generated_at": "2026-09-08T21:00:00Z",
        "coverage": 1.0,
        "source": "pit-rank-authority",
        "calendar_source": "observed completed XNYS/XNAS sessions",
        "schema_version": "upstream",
        "calculation_version": "pit-rank-v1",
        "lag_sessions": 20,
        "pit_frozen": True,
        "session_sequence": list(SEQUENCE),
        "rows": [{"ticker": f"T{i:02d}"} for i in range(24)],
    }


def test_old_top24_accepts_exact_20_session_pit_provenance():
    target, obj = validate_full_authority("old_top24", old_top24(), expected_session=SESSION)
    assert target == "old_top24.json"
    assert obj["session_date"] == "2026-08-10"
    assert obj["target_session_date"] == SESSION
    assert len(obj["session_sequence"]) == 21
    assert len(obj["rows"]) == 24


def test_old_top24_rejects_19_session_sequence():
    payload = old_top24()
    payload["session_sequence"] = payload["session_sequence"][1:]
    payload["session_date"] = payload["session_sequence"][0]
    with pytest.raises(AuthorityContractError):
        validate_full_authority("old_top24", payload, expected_session=SESSION)


def test_old_top24_rejects_duplicate_member():
    payload = old_top24()
    payload["rows"][23] = {"ticker": "T00"}
    with pytest.raises(AuthorityContractError):
        validate_full_authority("old_top24", payload, expected_session=SESSION)


def write(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_authority_manifest_reports_current_authorities(tmp_path: Path):
    write(tmp_path / "state.json", {"session_date": SESSION})
    write(
        tmp_path / "acquisition_manifest.json",
        {
            "session_date": SESSION,
            "generated_at": "2026-09-09T00:00:00Z",
            "coverage": 1.0,
            "source": "fixture",
            "schema_version": "fixture",
            "calculation_version": "fixture",
            "status": "READY",
            "mc57_status": "DATA_REQUIRED",
            "mc57_reason": "OLD_REASON",
        },
    )
    write(tmp_path / "nqsar.json", {"session_date": SESSION, "status": "READY"})
    write(tmp_path / "mc57.json", {"session_date": SESSION, "status": "READY"})
    write(tmp_path / "classifications.json", {"session_date": SESSION, "status": "READY"})
    write(tmp_path / "theme_scores.json", {"session_date": SESSION, "status": "READY"})
    write(tmp_path / "options" / "index.json", {"session_date": SESSION, "status": "READY"})
    write(tmp_path / "positions_ledger.json", {"session_date": SESSION, "status": "READY"})

    sync_acquisition_manifest(tmp_path)
    out = json.loads((tmp_path / "acquisition_manifest.json").read_text(encoding="utf-8"))
    assert out["nqsar_status"] == "READY"
    assert out["mc57_status"] == "READY"
    assert "mc57_reason" not in out
    assert out["structural_clinical_biotech_status"] == "READY"
    assert out["peer_theme_status"] == "READY"
    assert out["options_status"] == "READY"
    assert out["positions_status"] == "READY"


def test_authority_manifest_keeps_stale_and_declared_data_required_closed(tmp_path: Path):
    write(tmp_path / "state.json", {"session_date": SESSION})
    write(
        tmp_path / "acquisition_manifest.json",
        {
            "session_date": SESSION,
            "generated_at": "2026-09-09T00:00:00Z",
            "coverage": 1.0,
            "source": "fixture",
            "schema_version": "fixture",
            "calculation_version": "fixture",
            "status": "READY",
        },
    )
    write(tmp_path / "nqsar.json", {"session_date": "2026-09-04", "status": "READY"})
    write(
        tmp_path / "mc57.json",
        {"session_date": SESSION, "status": "DATA_REQUIRED", "reason": "NO_FIXED57"},
    )

    sync_acquisition_manifest(tmp_path)
    out = json.loads((tmp_path / "acquisition_manifest.json").read_text(encoding="utf-8"))
    assert out["nqsar_status"] == "DATA_REQUIRED"
    assert out["mc57_status"] == "DATA_REQUIRED"
    assert out["mc57_reason"] == "NO_FIXED57"
