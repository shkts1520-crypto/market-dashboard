#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from v38.live_acquisition import choose_completed_session, frame_dates, select_yfinance_symbol_frame


def _download(symbols: list[str]):
    return yf.download(
        tickers=symbols,
        period="1mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
        timeout=30,
    )


def _dates(symbol: str) -> set[str]:
    found: set[str] = set()
    for attempt in range(3):
        try:
            raw = _download([symbol])
            frame = select_yfinance_symbol_frame(raw, symbol)
            found.update(frame_dates(frame))
        except Exception:
            pass
        if attempt < 2:
            time.sleep(2.0 * (attempt + 1))
    return found


def _load_object(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"required session-lock file invalid: {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise SystemExit(f"required session-lock file must be an object: {path}")
    return obj


def validate_benchmark_recency(data_dir: str | Path = "data") -> dict[str, Any]:
    root = Path(data_dir)
    state = _load_object(root / "state.json")
    manifest = _load_object(root / "acquisition_manifest.json")

    published = str(state.get("session_date") or "")
    manifest_session = str(manifest.get("session_date") or "")
    selection = manifest.get("session_selection")
    if not isinstance(selection, dict):
        raise SystemExit("acquisition_manifest.session_selection is required")

    locked = str(selection.get("selected_session") or "")
    observed_at_lock = str(selection.get("benchmark_observed_session") or "")
    if not published or not manifest_session or not locked or not observed_at_lock:
        raise SystemExit("state/manifest session lock fields are required")
    if manifest_session != published or locked != published:
        raise SystemExit(
            "session lock mismatch: "
            f"state={published}, manifest={manifest_session}, selected={locked}"
        )
    if pd.Timestamp(observed_at_lock) > pd.Timestamp(locked):
        raise SystemExit(
            "invalid session lock: "
            f"observed_at_lock={observed_at_lock} > selected={locked}"
        )

    qqq = _dates("QQQ")
    spy = _dates("SPY")
    observed_now = choose_completed_session(qqq, spy) if qqq and spy else None

    status = "READY"
    reason = "SESSION_LOCK_MATCH"
    if observed_now is None:
        status = "READY_SESSION_LOCKED"
        reason = "LIVE_RECHECK_UNAVAILABLE_AFTER_SESSION_LOCK"
    elif pd.Timestamp(observed_now) > pd.Timestamp(locked):
        status = "READY_SESSION_LOCKED"
        reason = "NEWER_SESSION_OBSERVED_AFTER_RUN_LOCK"

    return {
        "status": status,
        "reason": reason,
        "published_session": published,
        "locked_selected_session": locked,
        "benchmark_observed_at_lock": observed_at_lock,
        "independently_observed_session": observed_now,
        "qqq_sessions": len(qqq),
        "spy_sessions": len(spy),
    }


def main() -> int:
    result = validate_benchmark_recency("data")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
