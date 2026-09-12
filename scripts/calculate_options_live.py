#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import time
from pathlib import Path

import pandas as pd

from v38.freshness import atomic_write_json
from v38.options_engine import (
    DEFAULT_TARGET_LIMIT,
    build_options_index,
    expiry_dte,
    frame_to_contracts,
    select_targets,
)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if pd.notna(x) else None


def _risk_free_rate(yf) -> float:
    """Observed short Treasury proxy; fail closed rather than invent a rate."""
    raw = yf.download(
        "^IRX",
        period="10d",
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
        timeout=20,
    )
    if raw is None or raw.empty:
        raise RuntimeError("^IRX short Treasury rate unavailable")
    if isinstance(raw.columns, pd.MultiIndex):
        closes = None
        for key in (("Close", "^IRX"), ("^IRX", "Close")):
            if key in raw.columns:
                closes = raw[key]
                break
        if closes is None:
            raise RuntimeError("^IRX Close column unavailable")
    else:
        closes = raw["Close"] if "Close" in raw.columns else None
    if closes is None:
        raise RuntimeError("^IRX Close column unavailable")
    values = pd.to_numeric(closes, errors="coerce").dropna()
    if values.empty:
        raise RuntimeError("^IRX has no finite close")
    rate = float(values.iloc[-1]) / 100.0
    if not (0.0 <= rate <= 0.25):
        raise RuntimeError(f"^IRX rate out of range: {rate}")
    return rate


def _spot_map(rs: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    rows = rs.get("rows") if isinstance(rs, dict) else None
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        price = _finite(row.get("price"))
        if ticker and price is not None and price > 0:
            out[ticker] = price
    return out


def _fetch_ticker_snapshot(yf, ticker: str, *, spot: float, session_date: str) -> dict:
    symbol = ticker.replace(".", "-")
    last_error = None
    for attempt in range(2):
        try:
            obj = yf.Ticker(symbol)
            expiries = [
                exp for exp in (obj.options or ())
                if 0 <= expiry_dte(str(exp), session_date) <= 45
            ]
            contracts = []
            fetched_expiries = []
            for expiry in expiries:
                try:
                    chain = obj.option_chain(expiry)
                except Exception:
                    continue
                fetched_expiries.append(str(expiry))
                contracts.extend(
                    frame_to_contracts(
                        ticker=ticker,
                        frame=chain.calls,
                        side="call",
                        expiry=str(expiry),
                        session_date=session_date,
                    )
                )
                contracts.extend(
                    frame_to_contracts(
                        ticker=ticker,
                        frame=chain.puts,
                        side="put",
                        expiry=str(expiry),
                        session_date=session_date,
                    )
                )
                time.sleep(0.05)
            return {
                "spot": spot,
                "contracts": contracts,
                "available_expiries": expiries,
                "fetched_expiries": fetched_expiries,
            }
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.8)
    raise RuntimeError(f"{ticker}: option fetch failed: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate live V38 option positioning from Yahoo chains")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--target-limit", type=int, default=DEFAULT_TARGET_LIMIT)
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("yfinance==0.2.66 is required") from exc

    root = Path(args.data_dir)
    state = _load(root / "state.json")
    rs = _load(root / "rs.json")
    core12 = _load(root / "core12.json")
    session = str(state.get("session_date") or "")
    if not session:
        raise SystemExit("state.json session_date is required")
    if rs.get("session_date") != session:
        raise SystemExit("rs.json is not current session")

    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    targets = select_targets(rs, core12, limit=args.target_limit)
    if not targets:
        raise SystemExit("no option targets resolved")
    spots = _spot_map(rs)
    rate = _risk_free_rate(yf)

    snapshots: dict[str, dict] = {}
    fetch_errors: dict[str, str] = {}
    for index, ticker in enumerate(targets, start=1):
        spot = spots.get(ticker)
        if spot is None:
            fetch_errors[ticker] = "CURRENT_SPOT_MISSING"
            continue
        try:
            snapshots[ticker] = _fetch_ticker_snapshot(
                yf,
                ticker,
                spot=spot,
                session_date=session,
            )
        except Exception as exc:
            fetch_errors[ticker] = str(exc)[:240]
        print(f"options {index}/{len(targets)} {ticker} {'ok' if ticker in snapshots else 'failed'}")
        time.sleep(0.10)

    previous = _load(root / "options" / "index.json")
    out = build_options_index(
        session_date=session,
        generated_at=generated_at,
        targets=targets,
        snapshots=snapshots,
        rate=rate,
        previous=previous,
    )
    out["fetch_errors"] = fetch_errors
    out["coverage_detail"] = {
        "target_count": len(targets),
        "ticker_snapshots": len(snapshots),
        "ticker_snapshot_coverage": len(snapshots) / len(targets),
        "bucket_row_counts": {key: len(rows) for key, rows in out.get("buckets", {}).items()},
    }
    path = atomic_write_json(root / "options" / "index.json", out)
    print(json.dumps({
        "path": str(path),
        "session_date": session,
        "status": out.get("status"),
        "coverage": out.get("coverage"),
        "targets": len(targets),
        "rows_0_45": len(out.get("buckets", {}).get("0-45", [])),
        "risk_free_rate": rate,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
