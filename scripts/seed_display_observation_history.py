#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from reconstruct_display_history_2y import _active_tickers, _write_stock_ohlcv
from v38.display_observation_history import exact_old_top20, write_histories


def _load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description="One-time seed for exact recovered display observation histories")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    root = Path(args.data_dir)
    state = _load(root / "state.json")
    rs = _load(root / "rs.json")
    session = str(state.get("session_date") or "")
    generated_at = args.generated_at or str(state.get("generated_at") or "") or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if not session or rs.get("session_date") != session:
        raise SystemExit("state/rs session mismatch")
    tickers = _active_tickers(rs)
    if not tickers:
        raise SystemExit("no active tickers")

    work = Path(tempfile.mkdtemp(prefix="v38-observation-seed-"))
    ohlcv = work / "ohlcv_3y.csv"
    stats = _write_stock_ohlcv(ohlcv, tickers, session)
    history_coverage = stats["history_ok"] / stats["requested"] if stats["requested"] else 0.0
    if stats["target_coverage"] < 0.99 or history_coverage < 0.99:
        raise SystemExit(f"display history seed coverage too low: target={stats['target_coverage']:.4f}, history={history_coverage:.4f}")

    frame = pd.read_csv(ohlcv)
    reversal_path, parabolic_path = write_histories(
        frame,
        tickers,
        root,
        session=session,
        generated_at=generated_at,
    )
    old_date, top20 = exact_old_top20(root, lag=42)
    if len(top20) != 20:
        raise SystemExit(f"lag42 exact RS63 top20 incomplete: {len(top20)}")
    parabolic = _load(parabolic_path)
    parabolic_rows = parabolic.get("series") or []
    print(json.dumps({
        "status": "READY",
        "session_date": session,
        "target_coverage": stats["target_coverage"],
        "history_coverage": history_coverage,
        "reversal_history": reversal_path.as_posix(),
        "parabolic_history": parabolic_path.as_posix(),
        "lag42_date": old_date,
        "lag42_top20": top20,
        "parabolic_points": len(parabolic_rows),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
