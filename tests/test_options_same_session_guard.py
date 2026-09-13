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

TARGETS = ("AAA", "BBB", "CCC", "DDD")


def _ready(session: str, *, coverage: float = 0.75, targets=TARGETS) -> dict:
    rows = [{"ticker": ticker} for ticker in ("AAA", "BBB", "CCC")]
    return {
        "session_date": session,
        "generated_at": "2026-09-12T00:00:00Z",
        "status": "READY",
        "coverage": coverage,
        "rows": rows,
        "buckets": {"0-45": rows},
        "target_policy": {"targets": list(targets)},
    }


def _candidate(
    session: str,
    *,
    status: str = "DATA_REQUIRED",
    coverage: float = 0.0,
    failures=TARGETS,
    reason: str = "OPTION_CHAIN_COVERAGE_BELOW_MINIMUM",
    include_targets: bool = True,
) -> dict:
    payload = {
        "session_date": session,
        "generated_at": "2026-09-13T00:00:00Z",
        "status": status,
        "coverage": coverage,
        "reason": reason,
        "rows": [],
        "buckets": {"0-45": []},
        "failures": {ticker: "OPTION_CHAIN_UNAVAILABLE" for ticker in failures},
        "fetch_errors": {ticker: "Too Many Requests. Rate limited." for ticker in failures},
    }
    if include_targets:
        payload["target_policy"] = {"targets": list(TARGETS)}
    return payload


def _prepare(tmp_path: Path, previous: dict, session: str) -> tuple[Path, Path]:
    root = tmp_path / "data"
    options = root / "options" / "index.json"
    options.parent.mkdir(parents=True)
    (root / "state.json").write_text(json.dumps({"session_date": session}), encoding="utf-8")
    rows = [
        {
            "ticker": ticker,
            "price": 100.0 + index,
            "rs63": 100.0 - index,
            "rs126": 100.0 - index,
            "rs189": 100.0 - index,
            "ddv20": 10_000_000.0 - index,
        }
        for index, ticker in enumerate(TARGETS)
    ]
    (root / "rs.json").write_text(json.dumps({"session_date": session, "rows": rows}), encoding="utf-8")
    (root / "core12.json").write_text(
        json.dumps({"ranking": [{"ticker": ticker} for ticker in TARGETS]}),
        encoding="utf-8",
    )
    options.write_text(json.dumps(previous, sort_keys=True), encoding="utf-8")
    return root, options


def _run_with_candidate(monkeypatch, options: Path, candidate: dict):
    def fake_run(*_args, **_kwargs):
        options.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)


def test_same_session_ready_is_preserved_on_systemic_fetch_failure(tmp_path, monkeypatch, capsys):
    session = "2026-09-11"
    root, options = _prepare(tmp_path, _ready(session), session)
    _run_with_candidate(monkeypatch, options, _candidate(session))

    assert mod.main(["--data-dir", str(root), "--target-limit", "4"]) == 0
    published = json.loads(options.read_text(encoding="utf-8"))
    assert published["status"] == "READY"
    assert published["coverage"] == 0.75
    assert len(published["rows"]) == 3
    guard = published["refresh_guard"]
    assert guard["mode"] == "PRESERVED_SAME_SESSION_READY"
    assert guard["reason"] == "SYSTEMIC_OPTION_FETCH_DEGRADATION"
    assert guard["failure_ratio"] == 1.0
    assert "options_retained_previous_same_session" in capsys.readouterr().out


def test_ready_but_systemically_degraded_refresh_is_also_preserved(tmp_path, monkeypatch):
    session = "2026-09-11"
    root, options = _prepare(tmp_path, _ready(session, coverage=1.0), session)
    degraded = _candidate(
        session,
        status="READY",
        coverage=0.25,
        failures=("AAA", "BBB", "CCC"),
        reason=None,
    )
    _run_with_candidate(monkeypatch, options, degraded)

    assert mod.main(["--data-dir", str(root), "--target-limit", "4"]) == 0
    published = json.loads(options.read_text(encoding="utf-8"))
    assert published["coverage"] == 1.0
    assert published["refresh_guard"]["failure_ratio"] == 0.75


def test_risk_free_total_failure_preserves_same_session_ready(tmp_path, monkeypatch):
    session = "2026-09-11"
    root, options = _prepare(tmp_path, _ready(session), session)
    rate_failure = _candidate(
        session,
        failures=(),
        reason="RISK_FREE_RATE_UNAVAILABLE:all measured sources unavailable",
        include_targets=False,
    )
    _run_with_candidate(monkeypatch, options, rate_failure)

    assert mod.main(["--data-dir", str(root), "--target-limit", "4"]) == 0
    published = json.loads(options.read_text(encoding="utf-8"))
    assert published["status"] == "READY"
    assert published["refresh_guard"]["reason"] == "RISK_FREE_RATE_UNAVAILABLE"


def test_prior_session_ready_is_not_rolled_forward(tmp_path, monkeypatch):
    root, options = _prepare(tmp_path, _ready("2026-09-10"), "2026-09-11")
    _run_with_candidate(monkeypatch, options, _candidate("2026-09-11"))

    assert mod.main(["--data-dir", str(root), "--target-limit", "4"]) == 0
    assert json.loads(options.read_text(encoding="utf-8"))["status"] == "DATA_REQUIRED"


def test_target_universe_mismatch_is_not_hidden(tmp_path, monkeypatch):
    session = "2026-09-11"
    root, options = _prepare(
        tmp_path,
        _ready(session, targets=("AAA", "BBB", "CCC", "ZZZ")),
        session,
    )
    _run_with_candidate(monkeypatch, options, _candidate(session))

    assert mod.main(["--data-dir", str(root), "--target-limit", "4"]) == 0
    assert json.loads(options.read_text(encoding="utf-8"))["status"] == "DATA_REQUIRED"


def test_non_systemic_refresh_is_not_rolled_back(tmp_path, monkeypatch):
    session = "2026-09-11"
    root, options = _prepare(tmp_path, _ready(session, coverage=0.75), session)
    non_systemic = _candidate(
        session,
        status="READY",
        coverage=0.50,
        failures=("AAA",),
        reason=None,
    )
    _run_with_candidate(monkeypatch, options, non_systemic)

    assert mod.main(["--data-dir", str(root), "--target-limit", "4"]) == 0
    assert json.loads(options.read_text(encoding="utf-8"))["coverage"] == 0.50


def test_fresh_better_ready_result_replaces_previous(tmp_path, monkeypatch):
    session = "2026-09-11"
    root, options = _prepare(tmp_path, _ready(session, coverage=0.75), session)
    fresh = _candidate(
        session,
        status="READY",
        coverage=1.0,
        failures=(),
        reason=None,
    )
    fresh["rows"] = [{"ticker": ticker} for ticker in TARGETS]
    fresh["buckets"] = {"0-45": fresh["rows"]}
    _run_with_candidate(monkeypatch, options, fresh)

    assert mod.main(["--data-dir", str(root), "--target-limit", "4"]) == 0
    published = json.loads(options.read_text(encoding="utf-8"))
    assert published["coverage"] == 1.0
    assert "refresh_guard" not in published
