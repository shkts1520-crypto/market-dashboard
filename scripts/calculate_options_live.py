#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

MIN_READY_COVERAGE = 0.25
MIN_READY_ROWS = 3
SYSTEMIC_FAILURE_RATIO = 0.50
REFRESH_GUARD_VERSION = "v38-options-refresh-guard-1.0.0"

# Keep the proven calculator implementation byte-for-byte in the adjacent core
# module. This wrapper only decides whether a degraded refresh is allowed to
# replace a same-session READY snapshot.
_CORE_PATH = Path(__file__).with_name("calculate_options_live_core.py")
_CORE_SPEC = importlib.util.spec_from_file_location("calculate_options_live_core", _CORE_PATH)
if _CORE_SPEC is None or _CORE_SPEC.loader is None:
    raise RuntimeError(f"unable to load options calculator core: {_CORE_PATH}")
_CORE = importlib.util.module_from_spec(_CORE_SPEC)
_CORE_SPEC.loader.exec_module(_CORE)

# Preserve helper imports used by the existing risk-free regression tests.
_rate_from_yahoo_frame = _CORE._rate_from_yahoo_frame
_previous_risk_free_rate = _CORE._previous_risk_free_rate
_fred_risk_free_rate = _CORE._fred_risk_free_rate


def _risk_free_rate(yf, *, session_date: str, previous: dict):
    # Existing tests monkeypatch these helpers on calculate_options_live.py.
    # Mirror those overrides into the unchanged core before delegating.
    _CORE._rate_from_yahoo_frame = _rate_from_yahoo_frame
    _CORE._previous_risk_free_rate = _previous_risk_free_rate
    _CORE._fred_risk_free_rate = _fred_risk_free_rate
    return _CORE._risk_free_rate(yf, session_date=session_date, previous=previous)


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _data_dir_from_args(argv: list[str]) -> Path:
    for index, arg in enumerate(argv):
        if arg == "--data-dir" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if arg.startswith("--data-dir="):
            return Path(arg.split("=", 1)[1])
    return Path("data")


def _target_limit_from_args(argv: list[str]) -> int:
    for index, arg in enumerate(argv):
        value = None
        if arg == "--target-limit" and index + 1 < len(argv):
            value = argv[index + 1]
        elif arg.startswith("--target-limit="):
            value = arg.split("=", 1)[1]
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                break
    return int(_CORE.DEFAULT_TARGET_LIMIT)


def _normalize_targets(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set)):
        return ()
    return tuple(sorted({str(value or "").strip().upper() for value in values if str(value or "").strip()}))


def _current_targets(root: Path, argv: list[str]) -> tuple[str, ...]:
    rs = _load(root / "rs.json")
    core12 = _load(root / "core12.json")
    try:
        targets = _CORE._chart_targets(
            rs,
            core12,
            requested_limit=_target_limit_from_args(argv),
        )
    except Exception:
        return ()
    return _normalize_targets(targets)


def _same_session_ready(previous: dict[str, Any], session: str) -> bool:
    if previous.get("status") != "READY" or previous.get("session_date") != session:
        return False
    try:
        coverage = float(previous.get("coverage"))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(coverage) or coverage < MIN_READY_COVERAGE:
        return False
    rows = previous.get("rows")
    buckets = previous.get("buckets")
    bucket_rows = buckets.get("0-45") if isinstance(buckets, dict) else None
    return (
        isinstance(rows, list)
        and len(rows) >= MIN_READY_ROWS
        and isinstance(bucket_rows, list)
        and len(bucket_rows) >= MIN_READY_ROWS
    )


def _policy_targets(payload: dict[str, Any]) -> tuple[str, ...]:
    policy = payload.get("target_policy")
    return _normalize_targets(policy.get("targets") if isinstance(policy, dict) else None)


def _coverage(payload: dict[str, Any]) -> float:
    try:
        value = float(payload.get("coverage"))
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) and value >= 0 else 0.0


def _failure_stats(candidate: dict[str, Any], targets: tuple[str, ...]) -> tuple[int, float]:
    target_set = set(targets)
    failed: set[str] = set()
    for key in ("failures", "fetch_errors"):
        mapping = candidate.get(key)
        if isinstance(mapping, dict):
            failed.update(str(ticker or "").strip().upper() for ticker in mapping)
    failed.discard("")
    if target_set:
        failed &= target_set
    count = len(failed)
    return count, (count / len(target_set) if target_set else 0.0)


def _retention_decision(
    previous: dict[str, Any],
    candidate: dict[str, Any],
    *,
    session: str,
    targets: tuple[str, ...],
) -> tuple[bool, str | None, int, float]:
    if not session or not targets or not _same_session_ready(previous, session):
        return False, None, 0, 0.0
    if _policy_targets(previous) != targets:
        return False, None, 0, 0.0
    if str(candidate.get("session_date") or "") != session:
        return False, None, 0, 0.0

    candidate_targets = _policy_targets(candidate)
    if candidate_targets and candidate_targets != targets:
        return False, None, 0, 0.0

    failure_count, failure_ratio = _failure_stats(candidate, targets)
    reason = str(candidate.get("reason") or "")
    if reason.startswith("RISK_FREE_RATE_UNAVAILABLE:"):
        return True, "RISK_FREE_RATE_UNAVAILABLE", failure_count, failure_ratio

    if (
        failure_ratio >= SYSTEMIC_FAILURE_RATIO
        and _coverage(candidate) < _coverage(previous)
    ):
        return True, "SYSTEMIC_OPTION_FETCH_DEGRADATION", failure_count, failure_ratio
    return False, None, failure_count, failure_ratio


def _retained_payload(
    previous: dict[str, Any],
    candidate: dict[str, Any],
    *,
    session: str,
    targets: tuple[str, ...],
    reason: str,
    failure_count: int,
    failure_ratio: float,
) -> dict[str, Any]:
    retained = dict(previous)
    fetch_errors = candidate.get("fetch_errors")
    retained["refresh_guard"] = {
        "guard_version": REFRESH_GUARD_VERSION,
        "mode": "PRESERVED_SAME_SESSION_READY",
        "session_date": session,
        "reason": reason,
        "attempted_at": candidate.get("generated_at"),
        "attempt_status": candidate.get("status"),
        "attempt_reason": candidate.get("reason"),
        "attempt_coverage": _coverage(candidate),
        "retained_generated_at": previous.get("generated_at"),
        "retained_coverage": _coverage(previous),
        "target_count": len(targets),
        "failure_count": failure_count,
        "failure_ratio": failure_ratio,
        "fetch_error_count": len(fetch_errors) if isinstance(fetch_errors, dict) else 0,
    }
    return retained


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = _data_dir_from_args(args)
    options_path = root / "options" / "index.json"
    state = _load(root / "state.json")
    session = str(state.get("session_date") or "")
    previous = _load(options_path)
    targets = _current_targets(root, args)

    completed = subprocess.run([sys.executable, str(_CORE_PATH), *args], check=False)
    if completed.returncode != 0:
        return int(completed.returncode)

    candidate = _load(options_path)
    retain, guard_reason, failure_count, failure_ratio = _retention_decision(
        previous,
        candidate,
        session=session,
        targets=targets,
    )
    if not retain or guard_reason is None:
        return 0

    retained = _retained_payload(
        previous,
        candidate,
        session=session,
        targets=targets,
        reason=guard_reason,
        failure_count=failure_count,
        failure_ratio=failure_ratio,
    )
    _CORE.atomic_write_json(options_path, retained)
    print(json.dumps({
        "options_retained_previous_same_session": True,
        "guard_version": REFRESH_GUARD_VERSION,
        "session_date": session,
        "reason": guard_reason,
        "attempt_status": candidate.get("status"),
        "attempt_coverage": _coverage(candidate),
        "failure_ratio": failure_ratio,
        "retained_status": retained.get("status"),
        "retained_coverage": retained.get("coverage"),
        "retained_rows": len(retained.get("rows") or []),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
