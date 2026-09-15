#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from v38.freshness import atomic_write_json
from v38.live_acquisition import select_yfinance_symbol_frame
from v38.vix_fear_cycle import HISTORY_START, build_vix_fear_cycle

DISPLAY_SESSIONS = 504
OPTION_CHART_SESSIONS = 126


def _load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return obj


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _merge_dated(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for row in existing + incoming:
        if not isinstance(row, dict):
            continue
        day = str(row.get("date") or row.get("time") or "").strip()
        if not day:
            continue
        by_date[day] = row
    return [by_date[key] for key in sorted(by_date)[-limit:]]


def _history_row(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "ticker", "price", "ddv20", "sma50", "sma200", "ret20", "ret63",
        "ret126", "ret189", "high52", "dist52", "rs63", "rs126", "rs189",
    )
    return {key: row.get(key) for key in keys}


def _ranked(rows: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    observed = [row for row in rows if isinstance(row, dict) and _finite(row.get(key)) is not None]
    observed.sort(key=lambda row: (-float(row[key]), str(row.get("ticker") or "")))
    return [_history_row(row) for row in observed[:limit]]


def _update_stock_history(root: Path, *, session: str, generated_at: str) -> Path:
    path = root / "history" / "reconstructed_stock_metrics.json"
    history = _load(path)
    rs = _load(root / "rs.json")
    breadth = _load(root / "breadth.json")
    f123 = _load(root / "f123.json")
    rows = [row for row in (rs.get("rows") or []) if isinstance(row, dict)]
    detail = breadth.get("coverage_detail") if isinstance(breadth.get("coverage_detail"), dict) else {}
    current = {
        "date": session,
        "coverage": rs.get("coverage"),
        "breadth50": breadth.get("breadth50"),
        "breadth200": breadth.get("breadth200"),
        "breadth50_valid": detail.get("valid_sma50_count"),
        "breadth200_valid": detail.get("valid_sma200_count"),
        "f1": f123.get("f1"),
        "f2": f123.get("f2"),
        "f3": f123.get("f3"),
        "rs_top": _ranked(rows, "rs189", 100),
        "rs_windows": {
            "63": _ranked(rows, "rs63", 10),
            "126": _ranked(rows, "rs126", 10),
        },
    }
    merged = _merge_dated(
        [row for row in (history.get("rows") or []) if isinstance(row, dict)],
        [current],
        limit=DISPLAY_SESSIONS,
    )
    if not merged:
        raise SystemExit("retained stock history is empty")
    history.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": current["coverage"],
        "status": "READY",
        "first_session": merged[0]["date"],
        "latest_session": merged[-1]["date"],
        "session_count": len(merged),
        "current_universe_count": (rs.get("coverage_detail") or {}).get("active_universe"),
        "rows": merged,
    })
    provenance = history.get("provenance") if isinstance(history.get("provenance"), dict) else {}
    provenance.update({
        "update_mode": "PERSISTED_HISTORY_PLUS_CURRENT_SESSION",
        "current_session_source": "authoritative rs.json + breadth.json + f123.json",
        "full_rebuild_policy": "bootstrap_or_recovery_only",
    })
    history["provenance"] = provenance
    atomic_write_json(path, history)
    return path


def _update_diagnostics(root: Path, *, session: str, generated_at: str) -> Path:
    path = root / "history" / "market_diagnostics_2y.json"
    history = _load(path)
    rs = _load(root / "rs.json")
    current = rs.get("market_diagnostics") if isinstance(rs.get("market_diagnostics"), dict) else {}
    incoming = [row for row in (current.get("series") or []) if isinstance(row, dict)]
    merged = _merge_dated(
        [row for row in (history.get("series") or []) if isinstance(row, dict)],
        incoming,
        limit=DISPLAY_SESSIONS,
    )
    history.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": rs.get("coverage"),
        "status": "READY" if merged and merged[-1].get("date") == session else "DATA_REQUIRED",
        "source": "retained two-year diagnostics + current authoritative rs.market_diagnostics",
        "calculation_version": "v38-display-history-retained-1.0.0",
        "trading_gate_eligible": False,
        "series": merged,
        "retention_mode": "PERSISTED_MERGE_BY_DATE",
    })
    atomic_write_json(path, history)
    return path


def _update_market_series(root: Path, *, session: str, generated_at: str) -> Path:
    path = root / "history" / "market_series_2y.json"
    history = _load(path)
    current = _load(root / "market_inputs.json")
    old_series = history.get("series") if isinstance(history.get("series"), dict) else {}
    new_series = current.get("series") if isinstance(current.get("series"), dict) else {}
    symbols = sorted(set(old_series) | set(new_series))
    merged_series: dict[str, list[dict[str, Any]]] = {}
    current_ready = 0
    for symbol in symbols:
        old_rows = [row for row in (old_series.get(symbol) or []) if isinstance(row, dict)]
        new_rows = [row for row in (new_series.get(symbol) or []) if isinstance(row, dict)]
        merged = _merge_dated(old_rows, new_rows, limit=DISPLAY_SESSIONS)
        if merged:
            merged_series[symbol] = merged
        if new_rows and str(new_rows[-1].get("date") or "") == session:
            current_ready += 1
    history.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": current.get("coverage"),
        "status": "READY" if merged_series else "DATA_REQUIRED",
        "source": "retained two-year market series + current market_inputs.json",
        "calculation_version": "v38-display-history-retained-1.0.0",
        "trading_gate_eligible": False,
        "series": merged_series,
        "retention_mode": "PERSISTED_MERGE_BY_DATE",
        "current_ready_count": current_ready,
    })
    atomic_write_json(path, history)
    return path


def _runner_ohlcv_path() -> Path | None:
    runner_temp = str(os.environ.get("RUNNER_TEMP") or "").strip()
    if not runner_temp:
        return None
    path = Path(runner_temp) / "v38-live" / "ohlcv.csv"
    return path if path.is_file() and path.stat().st_size > 0 else None


def _update_option_chart(root: Path, *, session: str) -> dict[str, Any]:
    options_path = root / "options" / "index.json"
    source_path = _runner_ohlcv_path()
    if not options_path.is_file() or source_path is None:
        return {"status": "SKIPPED", "reason": "CURRENT_RUNNER_OHLCV_UNAVAILABLE"}
    options = _load(options_path)
    if options.get("session_date") != session:
        return {"status": "SKIPPED", "reason": "OPTIONS_SESSION_MISMATCH"}
    policy = options.get("target_policy") if isinstance(options.get("target_policy"), dict) else {}
    targets = [str(value or "").strip().upper() for value in (policy.get("targets") or []) if str(value or "").strip()]
    if not targets:
        targets = sorted({
            str(row.get("ticker") or "").strip().upper()
            for row in (options.get("rows") or [])
            if isinstance(row, dict) and str(row.get("ticker") or "").strip()
        })
    wanted = set(targets)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker not in wanted:
                continue
            day = str(row.get("date") or "").strip()
            if not day or day > session:
                continue
            values = {key: _finite(row.get(key)) for key in ("open", "high", "low", "close", "volume")}
            if any(values[key] is None or values[key] <= 0 for key in ("open", "high", "low", "close")):
                continue
            grouped[ticker].append({
                "time": day,
                "open": round(float(values["open"]), 6),
                "high": round(float(values["high"]), 6),
                "low": round(float(values["low"]), 6),
                "close": round(float(values["close"]), 6),
                "volume": round(float(values["volume"]), 3) if values["volume"] is not None else None,
            })
    chart = {
        ticker: sorted(rows, key=lambda row: row["time"])[-OPTION_CHART_SESSIONS:]
        for ticker, rows in grouped.items() if rows
    }
    options["chart_ohlc"] = chart
    options["chart_ohlc_contract"] = {
        "status": "READY" if chart else "DATA_REQUIRED",
        "source": "current production OHLCV already acquired in Step 7; no historical re-download",
        "sessions_per_ticker": OPTION_CHART_SESSIONS,
        "target_count": len(targets),
        "ready_count": len(chart),
        "coverage": len(chart) / len(targets) if targets else 0.0,
        "renderer": "TradingView Lightweight Charts candlestick-only",
        "retention_mode": "CURRENT_RUNNER_OHLCV",
    }
    atomic_write_json(options_path, options)
    return options["chart_ohlc_contract"]


def _refresh_vix(root: Path, *, session: str, generated_at: str) -> Path:
    path = root / "history" / "vix_fear_cycle.json"
    end = (pd.Timestamp(session) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        raw = yf.download(
            tickers=["^VIX"], start=HISTORY_START, end=end, interval="1d",
            group_by="ticker", auto_adjust=False, actions=False, progress=False,
            threads=False, timeout=30,
        )
        frame = select_yfinance_symbol_frame(raw, "^VIX")
        out = build_vix_fear_cycle(frame, session_date=session, generated_at=generated_at)
        if out.get("status") == "READY":
            atomic_write_json(path, out)
            return path
    except Exception:
        pass
    if path.is_file():
        return path
    raise SystemExit("VIX fear-cycle history unavailable")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Retain two-year display history and merge the current session")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    root = Path(args.data_dir)
    state = _load(root / "state.json")
    session = str(state.get("session_date") or "")
    if not session:
        raise SystemExit("state.session_date is required")
    generated_at = args.generated_at or str(state.get("generated_at") or "") or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    required = (
        root / "history" / "reconstructed_stock_metrics.json",
        root / "history" / "market_diagnostics_2y.json",
        root / "history" / "market_series_2y.json",
    )
    missing = [path.as_posix() for path in required if not path.is_file() or path.stat().st_size <= 0]
    if missing:
        raise SystemExit("retained display history missing: " + ", ".join(missing))

    stock = _update_stock_history(root, session=session, generated_at=generated_at)
    diagnostics = _update_diagnostics(root, session=session, generated_at=generated_at)
    market = _update_market_series(root, session=session, generated_at=generated_at)
    option_chart = _update_option_chart(root, session=session)
    vix = _refresh_vix(root, session=session, generated_at=generated_at)

    print(json.dumps({
        "session_date": session,
        "mode": "PERSISTED_HISTORY_PLUS_CURRENT_SESSION",
        "stock_history": stock.as_posix(),
        "market_diagnostics": diagnostics.as_posix(),
        "market_series": market.as_posix(),
        "option_chart": option_chart,
        "vix_fear_cycle": vix.as_posix(),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
