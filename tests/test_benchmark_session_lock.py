from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_benchmark_recency.py"
spec = importlib.util.spec_from_file_location("validate_benchmark_recency", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _write_lock(
    root: Path,
    *,
    state_session: str = "2026-09-17",
    manifest_session: str = "2026-09-17",
    selected_session: str = "2026-09-17",
    observed_at_lock: str = "2026-09-17",
) -> None:
    (root / "state.json").write_text(
        json.dumps({"session_date": state_session}),
        encoding="utf-8",
    )
    (root / "acquisition_manifest.json").write_text(
        json.dumps({
            "session_date": manifest_session,
            "session_selection": {
                "benchmark_observed_session": observed_at_lock,
                "selected_session": selected_session,
            },
        }),
        encoding="utf-8",
    )


def test_newer_benchmark_seen_after_lock_is_diagnostic_not_run_failure(tmp_path, monkeypatch):
    _write_lock(tmp_path)
    monkeypatch.setattr(
        module,
        "_dates",
        lambda symbol: {"2026-09-17", "2026-09-18"},
    )

    result = module.validate_benchmark_recency(tmp_path)

    assert result["status"] == "READY_SESSION_LOCKED"
    assert result["reason"] == "NEWER_SESSION_OBSERVED_AFTER_RUN_LOCK"
    assert result["published_session"] == "2026-09-17"
    assert result["locked_selected_session"] == "2026-09-17"
    assert result["independently_observed_session"] == "2026-09-18"


def test_live_recheck_outage_does_not_invalidate_existing_run_lock(tmp_path, monkeypatch):
    _write_lock(tmp_path)
    monkeypatch.setattr(module, "_dates", lambda symbol: set())

    result = module.validate_benchmark_recency(tmp_path)

    assert result["status"] == "READY_SESSION_LOCKED"
    assert result["reason"] == "LIVE_RECHECK_UNAVAILABLE_AFTER_SESSION_LOCK"
    assert result["independently_observed_session"] is None


def test_state_and_manifest_selected_session_must_match(tmp_path, monkeypatch):
    _write_lock(tmp_path, selected_session="2026-09-18")
    monkeypatch.setattr(module, "_dates", lambda symbol: {"2026-09-18"})

    with pytest.raises(SystemExit, match="session lock mismatch"):
        module.validate_benchmark_recency(tmp_path)


def test_observed_session_at_lock_cannot_be_newer_than_selected_session(tmp_path, monkeypatch):
    _write_lock(tmp_path, observed_at_lock="2026-09-18")
    monkeypatch.setattr(module, "_dates", lambda symbol: {"2026-09-18"})

    with pytest.raises(SystemExit, match="invalid session lock"):
        module.validate_benchmark_recency(tmp_path)
