from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
from typing import Any

from v38.freshness import atomic_write_json

RESILIENCE_VERSION = "v38-options-resilience-1.0.0"
MIN_READY_COVERAGE = 0.25
MIN_READY_ROWS = 3
TRANSIENT_MARKERS = (
    "too many requests",
    "rate limit",
    "ratelimit",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
    "remote disconnected",
)


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _rows(obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows = obj.get("rows") if isinstance(obj, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _targets(obj: dict[str, Any]) -> list[str]:
    policy = obj.get("target_policy") if isinstance(obj, dict) else None
    values = policy.get("targets") if isinstance(policy, dict) else None
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        ticker = str(value or "").strip().upper()
        if ticker and ticker not in out:
            out.append(ticker)
    return out


def is_ready_same_session(obj: dict[str, Any], session_date: str) -> bool:
    if not isinstance(obj, dict) or obj.get("session_date") != session_date:
        return False
    if obj.get("status") != "READY":
        return False
    try:
        coverage = float(obj.get("coverage") or 0.0)
    except (TypeError, ValueError):
        return False
    return coverage >= MIN_READY_COVERAGE and len(_rows(obj)) >= MIN_READY_ROWS


def transient_error_count(obj: dict[str, Any]) -> int:
    values: list[str] = []
    errors = obj.get("fetch_errors") if isinstance(obj, dict) else None
    if isinstance(errors, dict):
        values.extend(str(value or "") for value in errors.values())
    reason = obj.get("reason") if isinstance(obj, dict) else None
    if reason:
        values.append(str(reason))
    count = 0
    for value in values:
        lowered = value.lower()
        if any(marker in lowered for marker in TRANSIENT_MARKERS):
            count += 1
    return count


def _compatible_targets(candidate: dict[str, Any], fallback: dict[str, Any]) -> bool:
    candidate_targets = _targets(candidate)
    fallback_targets = _targets(fallback)
    if not candidate_targets or not fallback_targets:
        return False
    return candidate_targets == fallback_targets


def _git(repo_root: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _history_commits(repo_root: Path, relative_path: str, *, limit: int) -> list[str]:
    commits: list[str] = []
    for ref in ("origin/main", "HEAD"):
        exists = _git(repo_root, "rev-parse", "--verify", ref)
        if exists.returncode != 0:
            continue
        result = _git(
            repo_root,
            "log",
            ref,
            f"-n{limit}",
            "--format=%H",
            "--",
            relative_path,
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            sha = line.strip()
            if sha and sha not in commits:
                commits.append(sha)
                if len(commits) >= limit:
                    return commits
    return commits


def _deepen_history(repo_root: Path, *, depth: int = 50) -> None:
    # actions/checkout persists credentials. Fetch main explicitly so this also
    # works from a shallow PR checkout whose HEAD cannot traverse main ancestry.
    # Failure is deliberately non-fatal: without a verified same-session fallback
    # the caller remains fail-closed.
    _git(
        repo_root,
        "fetch",
        "--no-tags",
        f"--depth={depth}",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
        timeout=45,
    )


def find_last_good_same_session(
    repo_root: Path,
    options_path: Path,
    *,
    session_date: str,
    candidate: dict[str, Any],
    limit: int = 50,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        relative_path = options_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None, None

    commits = _history_commits(repo_root, relative_path, limit=limit)
    # A shallow checkout can contain only the bad current commit (or no path
    # history at all when the current code commit did not touch the data file).
    if len(commits) < 2:
        _deepen_history(repo_root, depth=max(limit, 50))
        commits = _history_commits(repo_root, relative_path, limit=limit)

    for sha in commits:
        shown = _git(repo_root, "show", f"{sha}:{relative_path}", timeout=30)
        if shown.returncode != 0 or not shown.stdout:
            continue
        try:
            obj = json.loads(shown.stdout)
        except Exception:
            continue
        if not isinstance(obj, dict) or not is_ready_same_session(obj, session_date):
            continue
        if _compatible_targets(candidate, obj):
            return obj, sha
    return None, None


def recover_options_if_transient_failure(
    data_root: Path,
    *,
    session_date: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    options_path = data_root / "options" / "index.json"
    candidate = _load(options_path)
    if candidate.get("session_date") != session_date:
        return {"mode": "NOOP", "reason": "SESSION_MISMATCH"}

    transient_count = transient_error_count(candidate)
    if transient_count <= 0:
        return {"mode": "NOOP", "reason": "NO_TRANSIENT_FAILURE"}

    candidate_rows = len(_rows(candidate))
    root = (repo_root or Path.cwd()).resolve()
    fallback, sha = find_last_good_same_session(
        root,
        options_path,
        session_date=session_date,
        candidate=candidate,
    )
    if fallback is None or sha is None:
        return {
            "mode": "FAIL_CLOSED",
            "reason": "NO_COMPATIBLE_SAME_SESSION_READY_FALLBACK",
            "attempted_status": candidate.get("status"),
            "attempted_rows": candidate_rows,
            "transient_error_count": transient_count,
        }

    fallback_rows = len(_rows(fallback))
    # Never replace an equal-or-better successful refresh. The guard only prevents
    # a transient degradation from destroying an already-good same-session shard.
    if is_ready_same_session(candidate, session_date) and candidate_rows >= fallback_rows:
        return {
            "mode": "ACCEPTED_CURRENT",
            "attempted_rows": candidate_rows,
            "fallback_rows": fallback_rows,
            "transient_error_count": transient_count,
        }

    restored = deepcopy(fallback)
    restored["resilience_version"] = RESILIENCE_VERSION
    restored["resilience"] = {
        "mode": "PRESERVED_LAST_GOOD_SAME_SESSION",
        "trigger": "TRANSIENT_OPTIONS_ACQUISITION_DEGRADATION",
        "fallback_git_sha": sha,
        "preserved_generated_at": fallback.get("generated_at"),
        "preserved_status": fallback.get("status"),
        "preserved_coverage": fallback.get("coverage"),
        "preserved_rows": fallback_rows,
        "attempted_generated_at": candidate.get("generated_at"),
        "attempted_status": candidate.get("status"),
        "attempted_reason": candidate.get("reason"),
        "attempted_coverage": candidate.get("coverage"),
        "attempted_rows": candidate_rows,
        "attempted_fetch_error_count": len(candidate.get("fetch_errors") or {})
        if isinstance(candidate.get("fetch_errors"), dict)
        else 0,
        "transient_error_count": transient_count,
        "note": "Same-session READY options were preserved because the current acquisition degraded due to transient provider/network errors. No option metrics were fabricated.",
    }
    atomic_write_json(options_path, restored)
    return dict(restored["resilience"])
