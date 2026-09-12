#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from v38.historical_reconstruction import DEFAULT_SESSIONS, write_reconstructed_stock_history
from v38.live_acquisition import download_stock_ohlcv


def _load_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return obj


def _universe_tickers(path: Path | None, rs: dict) -> list[str]:
    if path is not None and path.is_file():
        frame = pd.read_csv(path)
        frame.columns = [str(column).strip().lower().replace(" ", "_") for column in frame.columns]
        if "ticker" in frame.columns:
            tickers = sorted({str(value).strip().upper() for value in frame["ticker"].tolist() if str(value).strip()})
            if tickers:
                return tickers
    rows = rs.get("rows")
    if not isinstance(rows, list):
        raise SystemExit("rs.rows is required when an acquisition universe file is unavailable")
    tickers = sorted({
        str(row.get("ticker") or "").strip().upper()
        for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    })
    if not tickers:
        raise SystemExit("current RS universe contains no tickers")
    return tickers


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recompute display-only historical Breadth, RS63/126/189 and F1/F2/F3 from the production OHLC history"
    )
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--ohlcv")
    parser.add_argument("--universe")
    parser.add_argument("--sessions", type=int, default=DEFAULT_SESSIONS)
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    root = Path(args.data_dir)
    state = _load_json(root / "state.json")
    rs = _load_json(root / "rs.json")
    session = state.get("session_date")
    if not isinstance(session, str) or not session:
        raise SystemExit("state.session_date is required")
    if rs.get("session_date") != session:
        raise SystemExit(f"rs/state session mismatch: {rs.get('session_date')} != {session}")

    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    universe_path = Path(args.universe) if args.universe else None
    tickers = _universe_tickers(universe_path, rs)

    supplied = Path(args.ohlcv) if args.ohlcv else None
    if supplied is not None and supplied.is_file() and supplied.stat().st_size > 0:
        ohlcv_path = supplied
        acquisition_mode = "REUSE_PRODUCTION_OHLC"
    else:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise SystemExit("yfinance==0.2.66 is required when --ohlcv is unavailable") from exc
        work = Path(tempfile.mkdtemp(prefix="v38-history-reconstruct-"))
        ohlcv_path = work / "ohlcv.csv"
        stats = download_stock_ohlcv(
            yf,
            tickers,
            target_session=session,
            output_path=ohlcv_path,
        )
        acquisition_mode = "REDOWNLOAD_YAHOO_2Y"
        print(json.dumps({"historical_download": stats}, sort_keys=True))

    output = root / "history" / "reconstructed_stock_metrics.json"
    write_reconstructed_stock_history(
        ohlcv_path,
        tickers,
        output,
        session_date=session,
        generated_at=generated_at,
        sessions=max(22, args.sessions),
    )
    result = _load_json(output)
    print(json.dumps({
        "status": result.get("status"),
        "session_date": session,
        "acquisition_mode": acquisition_mode,
        "current_universe_count": result.get("current_universe_count"),
        "first_session": result.get("first_session"),
        "latest_session": result.get("latest_session"),
        "session_count": result.get("session_count"),
        "survivorship_warning": result.get("survivorship_warning"),
        "trading_gate_eligible": result.get("trading_gate_eligible"),
        "output": output.as_posix(),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
