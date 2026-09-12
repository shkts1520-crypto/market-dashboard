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

CHART_TARGET_FLOOR = 48


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
    raw = yf.download(
        "^IRX", period="10d", interval="1d", auto_adjust=False,
        actions=False, progress=False, threads=False, timeout=20,
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


def _chart_targets(rs: dict, core12: dict, *, requested_limit: int) -> list[str]:
    """Cover tickers users can actually tap before adding generic liquidity names."""
    limit = max(int(requested_limit), CHART_TARGET_FLOOR)
    out: list[str] = []

    def add(value) -> None:
        ticker = str(value or "").strip().upper()
        if ticker and ticker not in out:
            out.append(ticker)

    ranking = core12.get("ranking") if isinstance(core12, dict) else None
    if isinstance(ranking, list):
        for row in ranking:
            if isinstance(row, dict):
                add(row.get("ticker"))

    rows = [row for row in (rs.get("rows") or []) if isinstance(row, dict)] if isinstance(rs, dict) else []
    for key, count in (("rs63", 10), ("rs126", 10), ("rs189", 24)):
        ranked = sorted(
            (row for row in rows if _finite(row.get(key)) is not None),
            key=lambda row: (-float(row[key]), str(row.get("ticker") or "")),
        )[:count]
        for row in ranked:
            add(row.get("ticker"))

    for ticker in select_targets(rs, core12, limit=limit):
        add(ticker)
    return out[:limit]


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
                contracts.extend(frame_to_contracts(
                    ticker=ticker, frame=chain.calls, side="call",
                    expiry=str(expiry), session_date=session_date,
                ))
                contracts.extend(frame_to_contracts(
                    ticker=ticker, frame=chain.puts, side="put",
                    expiry=str(expiry), session_date=session_date,
                ))
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
    effective_limit = max(int(args.target_limit), CHART_TARGET_FLOOR)
    targets = _chart_targets(rs, core12, requested_limit=effective_limit)
    if not targets:
        raise SystemExit("no option targets resolved")
    spots = _spot_map(rs)

    try:
        rate = _risk_free_rate(yf)
    except Exception as exc:
        previous = _load(root / "options" / "index.json")
        out = {
            "session_date": session,
            "generated_at": generated_at,
            "coverage": 0.0,
            "source": "Yahoo Finance option chains via yfinance 0.2.66",
            "schema_version": "v38.options.1",
            "calculation_version": "v38-options-live-1.0.1",
            "status": "DATA_REQUIRED",
            "reason": f"RISK_FREE_RATE_UNAVAILABLE:{str(exc)[:160]}",
            "rows": [], "buckets": {},
            "history": previous.get("history", {}) if isinstance(previous, dict) else {},
        }
        atomic_write_json(root / "options" / "index.json", out)
        print(json.dumps({"session_date": session, "status": "DATA_REQUIRED", "reason": out["reason"]}, sort_keys=True))
        return 0

    snapshots: dict[str, dict] = {}
    fetch_errors: dict[str, str] = {}
    for index, ticker in enumerate(targets, start=1):
        spot = spots.get(ticker)
        if spot is None:
            fetch_errors[ticker] = "CURRENT_SPOT_MISSING"
            continue
        try:
            snapshots[ticker] = _fetch_ticker_snapshot(
                yf, ticker, spot=spot, session_date=session,
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
    out["chart_overlay_contract"] = {
        "requested_cli_limit": int(args.target_limit),
        "effective_target_floor": CHART_TARGET_FLOOR,
        "target_priority": "Core12, RS63 Top10, RS126 Top10, RS189 Top24, then deterministic standard targets",
        "chart_bucket_default": "0-45",
    }
    out["coverage_detail"] = {
        "target_count": len(targets),
        "ticker_snapshots": len(snapshots),
        "ticker_snapshot_coverage": len(snapshots) / len(targets),
        "bucket_row_counts": {key: len(rows) for key, rows in out.get("buckets", {}).items()},
    }
    path = atomic_write_json(root / "options" / "index.json", out)
    print(json.dumps({
        "path": str(path), "session_date": session, "status": out.get("status"),
        "coverage": out.get("coverage"), "targets": len(targets),
        "requested_target_limit": int(args.target_limit),
        "effective_target_floor": CHART_TARGET_FLOOR,
        "rows_0_45": len(out.get("buckets", {}).get("0-45", [])),
        "risk_free_rate": rate,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
