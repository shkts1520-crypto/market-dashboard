#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from v38.live_acquisition import (
    LiveAcquisitionError,
    choose_completed_session,
    fetch_benchmark_frames,
    frame_dates,
    prevent_session_regression,
)
from v38.retained_publication import RetainedPublicationError, validate_retained_publication


def _load_state(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def select_mode(yf: Any, root: Path) -> tuple[str, dict[str, Any]]:
    state = _load_state(root / "state.json")
    previous = str(state.get("session_date")) if state.get("session_date") else None

    try:
        benchmarks = fetch_benchmark_frames(yf)
        observed = choose_completed_session(
            frame_dates(benchmarks["QQQ"]),
            frame_dates(benchmarks["SPY"]),
        )
    except Exception as exc:
        if not previous:
            raise LiveAcquisitionError(
                f"benchmark session discovery failed and no retained publication exists: {exc}"
            ) from exc
        try:
            validation = validate_retained_publication(root, session_date=previous)
        except Exception as retained_exc:
            raise LiveAcquisitionError(
                "benchmark session discovery failed and retained publication also failed validation: "
                f"benchmark={exc}; retained={retained_exc}"
            ) from retained_exc
        return "retain", {
            "mode": "retain",
            "reason": "BENCHMARK_TEMPORARILY_UNAVAILABLE_RETAIN_VALIDATED",
            "benchmark_observed_session": None,
            "previous_published_session": previous,
            "selected_session": previous,
            "validation": validation,
        }

    selected = prevent_session_regression(observed, previous)

    if previous and selected == previous:
        try:
            validation = validate_retained_publication(root, session_date=previous)
        except RetainedPublicationError as exc:
            if observed == previous:
                return "acquire", {
                    "mode": "acquire",
                    "reason": "SAME_SESSION_RETAIN_VALIDATION_FAILED_REACQUIRE",
                    "benchmark_observed_session": observed,
                    "previous_published_session": previous,
                    "selected_session": observed,
                    "retained_validation_error": str(exc),
                }
            raise
        return "retain", {
            "mode": "retain",
            "reason": (
                "SAME_SESSION_ALREADY_READY"
                if observed == previous
                else "BENCHMARK_REGRESSION_RETAIN_VALIDATED"
            ),
            "benchmark_observed_session": observed,
            "previous_published_session": previous,
            "selected_session": previous,
            "validation": validation,
        }

    return "acquire", {
        "mode": "acquire",
        "reason": "NEW_COMPLETED_SESSION",
        "benchmark_observed_session": observed,
        "previous_published_session": previous,
        "selected_session": selected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Choose live acquisition or strict retained-session revalidation"
    )
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("yfinance==0.2.66 is required for session selection") from exc

    mode, diagnostic = select_mode(yf, Path(args.data_dir))
    print(json.dumps(diagnostic, sort_keys=True), file=sys.stderr)
    print(mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
