#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

MIN_READY_COVERAGE = 0.25
MIN_READY_ROWS = 3


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


def _restore_exact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".retain.tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = _data_dir_from_args(args)
    options_path = root / "options" / "index.json"
    state = _load(root / "state.json")
    session = str(state.get("session_date") or "")

    previous_raw = options_path.read_bytes() if options_path.exists() else b""
    previous = _load(options_path)

    core = Path(__file__).with_name("calculate_options_live_core.py")
    completed = subprocess.run([sys.executable, str(core), *args], check=False)
    if completed.returncode != 0:
        return int(completed.returncode)

    candidate = _load(options_path)
    candidate_status = str(candidate.get("status") or "")
    candidate_session = str(candidate.get("session_date") or "")
    if candidate_status == "READY":
        return 0

    if (
        previous_raw
        and session
        and candidate_session == session
        and _same_session_ready(previous, session)
    ):
        _restore_exact(options_path, previous_raw)
        print(json.dumps({
            "options_retained_previous_same_session": True,
            "session_date": session,
            "attempt_status": candidate_status or None,
            "attempt_reason": candidate.get("reason"),
            "retained_status": previous.get("status"),
            "retained_coverage": previous.get("coverage"),
            "retained_rows": len(previous.get("rows") or []),
        }, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
