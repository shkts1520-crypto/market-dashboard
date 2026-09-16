#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

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


def main() -> int:
    state_path = Path("data/state.json")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    published = str(state.get("session_date") or "")
    if not published:
        raise SystemExit("state.session_date is required")

    qqq = _dates("QQQ")
    spy = _dates("SPY")
    if not qqq or not spy:
        raise SystemExit("benchmark recency guard could not observe QQQ/SPY")
    observed = choose_completed_session(qqq, spy)
    if pd.Timestamp(observed) > pd.Timestamp(published):
        raise SystemExit(
            f"publication session regression: state={published}, independently observed={observed}"
        )
    print(json.dumps({
        "status": "READY",
        "published_session": published,
        "independently_observed_session": observed,
        "qqq_sessions": len(qqq),
        "spy_sessions": len(spy),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
