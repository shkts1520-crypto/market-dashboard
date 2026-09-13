from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "calculate_options_live.py"
spec = importlib.util.spec_from_file_location("calculate_options_live_guard", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _ready(session: str) -> dict:
    rows = [{"ticker": ticker} for ticker in ("AAA", "BBB", "CCC")]
    return {
        "session_date": session,
        "generated_at": "2026-09-12T00:00:00Z",
        "status": "READY",
        "coverage": 0.75,
        "rows": rows,
        "buckets": {"0-45": rows},
    }


def _required(session: str) -> dict:
    return {
        "session_date": session,
        "generated_at": "2026-09-13T00:00:00Z",
        "status": "DATA_REQUIRED",
        "coverage": 0.0,
        "reason": "OPTION_CHAIN_COVERAGE_BELOW_MINIMUM",
        "rows": [],
        "buckets": {"0-45": []},
    }


def _prepare(tmp_path: Path, previous: dict, session: str) -> tuple[Path, Path]:
    root = tmp_path / "data"
    options = root / "options" / "index.json"
    options.parent.mkdir(parents=True)
    (root / "state.json").write_text(json.dumps({"session_date": session}), encoding="utf-8")
    options.write_text(json.dumps(previous, sort_keys=True), encoding="utf-8")
    return root, options


def test_same_session_ready_is_restored_when_attempt_degrades(tmp_path, monkeypatch, capsys):
    session = "2026-09-11"
    previous = _ready(session)
    root, options = _prepare(tmp_path, previous, session)
    before = options.read_bytes()

    def fake_run(*_args, **_kwargs):
        options.write_text(json.dumps(_required(session)), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod.main(["--data-dir", str(root), "--target-limit", "24"]) == 0
    assert options.read_bytes() == before
    assert json.loads(options.read_text(encoding="utf-8"))["status"] == "READY"
    assert "options_retained_previous_same_session" in capsys.readouterr().out


def test_prior_session_ready_is_not_rolled_forward(tmp_path, monkeypatch):
    root, options = _prepare(tmp_path, _ready("2026-09-10"), "2026-09-11")

    def fake_run(*_args, **_kwargs):
        options.write_text(json.dumps(_required("2026-09-11")), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod.main(["--data-dir", str(root)]) == 0
    assert json.loads(options.read_text(encoding="utf-8"))["status"] == "DATA_REQUIRED"


def test_fresh_ready_result_replaces_previous(tmp_path, monkeypatch):
    session = "2026-09-11"
    root, options = _prepare(tmp_path, _ready(session), session)
    fresh = _ready(session)
    fresh["generated_at"] = "2026-09-13T01:00:00Z"
    fresh["coverage"] = 1.0

    def fake_run(*_args, **_kwargs):
        options.write_text(json.dumps(fresh, sort_keys=True), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod.main(["--data-dir", str(root)]) == 0
    assert json.loads(options.read_text(encoding="utf-8"))["coverage"] == 1.0
