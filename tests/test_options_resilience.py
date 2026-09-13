from __future__ import annotations

import json
from pathlib import Path
import subprocess

from v38.options_resilience import (
    find_last_good_same_session,
    is_ready_same_session,
    recover_options_if_transient_failure,
    transient_error_count,
)


def _options(*, status="READY", rows=4, coverage=1.0, error=None):
    obj = {
        "session_date": "2026-09-11",
        "generated_at": "2026-09-13T00:00:00Z",
        "status": status,
        "coverage": coverage,
        "rows": [{"ticker": f"T{i}"} for i in range(rows)],
        "target_policy": {"targets": ["AAA", "BBB", "CCC", "DDD"]},
        "fetch_errors": {},
        "source": "test",
        "schema_version": "v38.options.1",
        "calculation_version": "test",
    }
    if error:
        obj["fetch_errors"] = {"AAA": error}
    return obj


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_ready_same_session_requires_ready_coverage_and_rows():
    assert is_ready_same_session(_options(), "2026-09-11")
    assert not is_ready_same_session(_options(status="DATA_REQUIRED"), "2026-09-11")
    assert not is_ready_same_session(_options(rows=2), "2026-09-11")
    assert not is_ready_same_session(_options(coverage=0.20), "2026-09-11")
    assert not is_ready_same_session(_options(), "2026-09-10")


def test_transient_error_count_detects_rate_limit_and_timeout():
    obj = _options(status="DATA_REQUIRED", rows=0, coverage=0.0)
    obj["fetch_errors"] = {
        "AAA": "Too Many Requests. Rate limited. Try after a while.",
        "BBB": "operation timed out",
        "CCC": "no contracts",
    }
    assert transient_error_count(obj) == 2


def test_find_last_good_same_session_from_git_history(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    path = repo / "data" / "options" / "index.json"
    path.parent.mkdir(parents=True)

    good = _options()
    path.write_text(json.dumps(good), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "good")
    good_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    bad = _options(status="DATA_REQUIRED", rows=0, coverage=0.0, error="Too Many Requests")
    path.write_text(json.dumps(bad), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "bad")

    found, sha = find_last_good_same_session(
        repo, path, session_date="2026-09-11", candidate=bad,
    )
    assert found is not None
    assert sha == good_sha
    assert found["status"] == "READY"


def test_recover_preserves_same_session_ready_on_rate_limit(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    path = repo / "data" / "options" / "index.json"
    path.parent.mkdir(parents=True)

    good = _options(rows=4, coverage=1.0)
    path.write_text(json.dumps(good), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "good")

    bad = _options(
        status="DATA_REQUIRED", rows=0, coverage=0.0,
        error="Too Many Requests. Rate limited. Try after a while.",
    )
    bad["generated_at"] = "2026-09-13T01:00:00Z"
    path.write_text(json.dumps(bad), encoding="utf-8")

    result = recover_options_if_transient_failure(
        repo / "data", session_date="2026-09-11", repo_root=repo,
    )
    restored = json.loads(path.read_text(encoding="utf-8"))
    assert result["mode"] == "PRESERVED_LAST_GOOD_SAME_SESSION"
    assert restored["status"] == "READY"
    assert restored["coverage"] == 1.0
    assert len(restored["rows"]) == 4
    assert restored["generated_at"] == good["generated_at"]
    assert restored["resilience"]["attempted_rows"] == 0
    assert restored["resilience"]["transient_error_count"] == 1


def test_recover_does_not_mask_non_transient_failure(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = repo / "data" / "options" / "index.json"
    path.parent.mkdir(parents=True)
    bad = _options(status="DATA_REQUIRED", rows=0, coverage=0.0, error="no valid contracts")
    path.write_text(json.dumps(bad), encoding="utf-8")
    result = recover_options_if_transient_failure(
        repo / "data", session_date="2026-09-11", repo_root=repo,
    )
    assert result == {"mode": "NOOP", "reason": "NO_TRANSIENT_FAILURE"}
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "DATA_REQUIRED"
