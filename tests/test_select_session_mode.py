from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from v38.retained_publication import RetainedPublicationError


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "select_session_mode.py"
SPEC = importlib.util.spec_from_file_location("select_session_mode", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _state(root: Path, session: str) -> None:
    (root / "state.json").write_text(json.dumps({"session_date": session}), encoding="utf-8")


def _benchmarks(monkeypatch, session: str = "2026-09-18") -> None:
    monkeypatch.setattr(module, "fetch_benchmark_frames", lambda yf: {"QQQ": object(), "SPY": object()})
    monkeypatch.setattr(module, "frame_dates", lambda frame: [session])
    monkeypatch.setattr(module, "choose_completed_session", lambda q, s: session)


def test_same_session_ready_is_retained_without_reacquisition(tmp_path, monkeypatch):
    _state(tmp_path, "2026-09-18")
    _benchmarks(monkeypatch)
    monkeypatch.setattr(
        module,
        "validate_retained_publication",
        lambda root, session_date: {"session_date": session_date, "stock_coverage": 1.0},
    )

    mode, diagnostic = module.select_mode(object(), tmp_path)

    assert mode == "retain"
    assert diagnostic["reason"] == "SAME_SESSION_ALREADY_READY"
    assert diagnostic["selected_session"] == "2026-09-18"


def test_same_session_invalid_retained_data_reacquires(tmp_path, monkeypatch):
    _state(tmp_path, "2026-09-18")
    _benchmarks(monkeypatch)

    def fail(*args, **kwargs):
        raise RetainedPublicationError("coverage below publication guard")

    monkeypatch.setattr(module, "validate_retained_publication", fail)

    mode, diagnostic = module.select_mode(object(), tmp_path)

    assert mode == "acquire"
    assert diagnostic["reason"] == "SAME_SESSION_RETAIN_VALIDATION_FAILED_REACQUIRE"


def test_benchmark_outage_retains_last_valid_publication(tmp_path, monkeypatch):
    _state(tmp_path, "2026-09-18")
    monkeypatch.setattr(module, "fetch_benchmark_frames", lambda yf: (_ for _ in ()).throw(RuntimeError("rate limited")))
    monkeypatch.setattr(
        module,
        "validate_retained_publication",
        lambda root, session_date: {"session_date": session_date, "stock_coverage": 1.0},
    )

    mode, diagnostic = module.select_mode(object(), tmp_path)

    assert mode == "retain"
    assert diagnostic["reason"] == "BENCHMARK_TEMPORARILY_UNAVAILABLE_RETAIN_VALIDATED"
    assert diagnostic["benchmark_observed_session"] is None


def test_newer_completed_session_acquires(tmp_path, monkeypatch):
    _state(tmp_path, "2026-09-17")
    _benchmarks(monkeypatch, "2026-09-18")

    mode, diagnostic = module.select_mode(object(), tmp_path)

    assert mode == "acquire"
    assert diagnostic["reason"] == "NEW_COMPLETED_SESSION"
    assert diagnostic["selected_session"] == "2026-09-18"
