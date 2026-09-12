#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v38.live_acquisition import (
    choose_completed_session,
    fetch_benchmark_frames,
    frame_dates,
    prevent_session_regression,
)
from v38.retained_publication import validate_retained_publication


def _load_state(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


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

    root = Path(args.data_dir)
    benchmarks = fetch_benchmark_frames(yf)
    observed = choose_completed_session(
        frame_dates(benchmarks["QQQ"]),
        frame_dates(benchmarks["SPY"]),
    )
    state = _load_state(root / "state.json")
    previous = str(state.get("session_date")) if state.get("session_date") else None
    selected = prevent_session_regression(observed, previous)

    if selected != observed:
        validation = validate_retained_publication(root, session_date=selected)
        print(
            json.dumps(
                {
                    "mode": "retain",
                    "benchmark_observed_session": observed,
                    "previous_published_session": previous,
                    "selected_session": selected,
                    "validation": validation,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        print("retain")
        return 0

    print(
        json.dumps(
            {
                "mode": "acquire",
                "benchmark_observed_session": observed,
                "previous_published_session": previous,
                "selected_session": selected,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    print("acquire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
