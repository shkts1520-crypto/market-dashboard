#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from v38.live_acquisition import select_yfinance_symbol_frame, yahoo_symbol
from v38.setup_restore import build_payload as build_setup_payload, pool_rows as setup_pool_rows
from v38.vwap_restore import (
    CALCULATION_VERSION,
    SCHEMA_VERSION,
    add_vwap_columns,
    advance_inception,
    chart_rows,
    classify_vwap,
    inception_from_frame,
    inception_value,
    normalize_ohlcv,
)

CHART_SESSIONS = 320
BOOTSTRAP_MAX_PER_RUN = 80


def read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def download(symbols: list[str], *, period: str, threads: int | bool = 12) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    return yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=threads,
        timeout=30,
    )


def symbol_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    symbol = yahoo_symbol(ticker)
    frame = select_yfinance_symbol_frame(raw, symbol)
    return add_vwap_columns(normalize_ohlcv(frame))


def batch_frames(tickers: list[str], *, period: str, chunk_size: int = 80) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for offset in range(0, len(tickers), chunk_size):
        chunk = tickers[offset:offset + chunk_size]
        symbols = [yahoo_symbol(ticker) for ticker in chunk]
        try:
            raw = download(symbols, period=period)
        except Exception:
            raw = pd.DataFrame()
        for ticker in chunk:
            frame = symbol_frame(raw, ticker) if not raw.empty else pd.DataFrame()
            if frame.empty:
                try:
                    retry = download([yahoo_symbol(ticker)], period=period, threads=False)
                except Exception:
                    retry = pd.DataFrame()
                frame = symbol_frame(retry, ticker) if not retry.empty else pd.DataFrame()
            if not frame.empty:
                out[ticker] = frame
    return out


def option_targets(options: dict[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    policy = options.get("target_policy")
    if isinstance(policy, dict) and isinstance(policy.get("targets"), list):
        for value in policy["targets"]:
            ticker = str(value or "").strip().upper()
            if ticker and ticker not in seen:
                seen.add(ticker)
                found.append(ticker)
    for row in options.get("rows") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            found.append(ticker)
    buckets = options.get("buckets")
    if isinstance(buckets, dict):
        for rows in buckets.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                ticker = str(row.get("ticker") or "").strip().upper()
                if ticker and ticker not in seen:
                    seen.add(ticker)
                    found.append(ticker)
    return found


def leader_candidates(rs: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for row in rs.get("rows") or []:
        if not isinstance(row, dict):
            continue
        try:
            rs189 = float(row.get("rs189"))
            price = float(row.get("price"))
            sma50 = float(row.get("sma50"))
            sma200 = float(row.get("sma200"))
        except (TypeError, ValueError):
            continue
        if rs189 < 85 or price < 5 or not (sma50 > sma200 and price > sma200):
            continue
        output.append(row)
    output.sort(key=lambda row: (-float(row.get("rs189") or 0), str(row.get("ticker") or "")))
    return output


def theme_lookup(rotation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rotation.get("rows") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        out[ticker] = {
            "theme_id": str(row.get("theme_id") or row.get("theme_name") or ""),
            "theme_name": str(row.get("theme_name") or row.get("theme_id") or ""),
            "major_theme": str(row.get("major_theme") or ""),
            "peer_theme_score": row.get("peer_theme_score"),
        }
    return out


def search_rows(rs: dict[str, Any], rotation: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    themes = theme_lookup(rotation)
    for row in rs.get("rows") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        item = {
            "ticker": ticker,
            "exchange": str(row.get("exchange") or "").strip().upper(),
            "name": str(row.get("name") or ""),
            "sector": str(row.get("sector") or ""),
            "industry": str(row.get("industry") or ""),
            "price": row.get("price"),
            "ret20": row.get("ret20"),
            "ret63": row.get("ret63"),
            "rs63": row.get("rs63"),
            "rs126": row.get("rs126"),
            "rs189": row.get("rs189"),
        }
        item.update(themes.get(ticker, {}))
        rows.append(item)
    return rows


def setup_row(raw: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    ticker = str(raw.get("ticker") or "").strip().upper()
    v63 = classify_vwap(frame, "vwap63")
    v252 = classify_vwap(frame, "vwap252")
    return {
        "ticker": ticker,
        "name": str(raw.get("name") or ""),
        "major": str(raw.get("sector") or ""),
        "industry": str(raw.get("industry") or ""),
        "rs189": raw.get("rs189"),
        "price": raw.get("price"),
        "vwap63": v63,
        "vwap252": v252,
    }


def setup_triggered(row: dict[str, Any]) -> bool:
    for key in ("vwap63", "vwap252"):
        item = row.get(key) or {}
        if item.get("break") or item.get("touch") or item.get("near"):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore search, VWAP, setup and chart data used by the pre-v5 dashboard")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    root = Path(args.data_dir)
    state = read_json(root / "state.json")
    rs = read_json(root / "rs.json")
    rotation = read_json(root / "rotation.json")
    options_path = root / "options" / "index.json"
    options = read_json(options_path)
    session = str(state.get("session_date") or "")
    if not session:
        raise SystemExit("state.json session_date required")
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    search = search_rows(rs, rotation)
    write_json(root / "history" / "search_index.json", {
        "session_date": session,
        "generated_at": generated_at,
        "status": "READY" if search else "DATA_REQUIRED",
        "source": "data/rs.json current universe",
        "schema_version": "v38.search_index.1",
        "calculation_version": CALCULATION_VERSION,
        "rows": search,
    })

    options_targets = option_targets(options)
    leaders = leader_candidates(rs)
    leaders_by_ticker = {str(row.get("ticker") or "").strip().upper(): row for row in leaders}
    setup_pool = setup_pool_rows(rs)
    setup_by_ticker = {str(row.get("ticker") or "").strip().upper(): row for row in setup_pool}
    two_year_tickers = sorted(set(options_targets) | set(leaders_by_ticker) | set(setup_by_ticker))
    frames = batch_frames(two_year_tickers, period="2y")

    setup_rows = []
    for ticker, raw in leaders_by_ticker.items():
        frame = frames.get(ticker)
        if frame is None or frame.empty:
            continue
        setup_rows.append(setup_row(raw, frame))

    setup_payload = build_setup_payload(
        session=session,
        generated_at=generated_at,
        pool=setup_pool,
        frames=frames,
        failed=[ticker for ticker in setup_by_ticker if ticker not in frames],
    )
    write_json(root / "history" / "setup_restore.json", setup_payload)

    trigger_tickers = [row["ticker"] for row in setup_rows if setup_triggered(row)]
    chart_targets = sorted(set(options_targets) | set(trigger_tickers))
    chart = dict(options.get("chart_ohlc") or {}) if isinstance(options.get("chart_ohlc"), dict) else {}
    for ticker in chart_targets:
        frame = frames.get(ticker)
        if frame is not None and not frame.empty:
            chart[ticker] = chart_rows(frame, CHART_SESSIONS)
    options["chart_ohlc"] = chart
    options["chart_ohlc_contract"] = {
        "status": "READY" if chart else "DATA_REQUIRED",
        "source": "Yahoo Finance 2y adjusted daily bars for restored Options/VWAP experience",
        "sessions_per_ticker": CHART_SESSIONS,
        "target_count": len(chart_targets),
        "ready_count": sum(1 for ticker in chart_targets if chart.get(ticker)),
        "coverage": (sum(1 for ticker in chart_targets if chart.get(ticker)) / len(chart_targets)) if chart_targets else 0.0,
        "renderer": "TradingView Lightweight Charts candlestick + VWAP overlays",
    }
    write_json(options_path, options)

    inception_path = root / "history" / "inception_vwap.json"
    inception = read_json(inception_path)
    if inception.get("schema_version"):
        inception = inception.get("rows") if isinstance(inception.get("rows"), dict) else {}
    inception = {str(k).upper(): v for k, v in inception.items() if isinstance(v, dict)}
    for ticker, old in list(inception.items()):
        frame = frames.get(ticker)
        if frame is not None and not frame.empty:
            inception[ticker] = advance_inception(old, frame)

    life_priority = []
    for ticker in options_targets + trigger_tickers:
        if ticker not in life_priority and ticker not in inception:
            life_priority.append(ticker)
    bootstrap = life_priority[:BOOTSTRAP_MAX_PER_RUN]
    max_frames = batch_frames(bootstrap, period="max", chunk_size=20) if bootstrap else {}
    inception_series: dict[str, list[dict[str, Any]]] = {}
    for ticker, frame in max_frames.items():
        record, series = inception_from_frame(frame)
        if record:
            inception[ticker] = record
            inception_series[ticker] = series[-CHART_SESSIONS:]
    write_json(inception_path, inception)

    for row in setup_rows:
        ticker = row["ticker"]
        life = inception_value(inception.get(ticker))
        price = row.get("price")
        try:
            dist = float(price) / life - 1.0 if life and float(price) > 0 else None
        except (TypeError, ValueError):
            dist = None
        row["vwap_life"] = {
            "value": life,
            "dist": dist,
            "valid": life is not None,
            "through": inception.get(ticker, {}).get("through") if ticker in inception else None,
        }

    setup_rows.sort(key=lambda row: (
        0 if (row["vwap63"].get("break") or row["vwap252"].get("break")) else
        1 if (row["vwap63"].get("touch") or row["vwap252"].get("touch")) else
        2 if (row["vwap63"].get("near") or row["vwap252"].get("near")) else 3,
        -(float(row.get("rs189") or 0.0)),
        row["ticker"],
    ))

    vwap_payload = {
        "session_date": session,
        "generated_at": generated_at,
        "status": "READY" if setup_rows else "DATA_REQUIRED",
        "source": "Yahoo Finance adjusted daily HLC3×Volume; inception records persisted incrementally",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "definitions": {
            "rolling": "HLC3 rolling PV / rolling Volume",
            "periods": [63, 252],
            "break": "previous close below previous VWAP and current close at/above current VWAP",
            "touch": "previous close at/above previous VWAP; current low touches VWAP and close holds above",
            "near": "close above VWAP and within 0.5 ATR14",
            "all_time": "HLC3 cumulative PV / cumulative Volume from first available listing bar",
            "trading_gate_eligible": False,
        },
        "eligible_count": len(leaders),
        "setup_count": sum(1 for row in setup_rows if setup_triggered(row)),
        "rows": setup_rows,
        "inception_ready": len(inception),
        "inception_bootstrap_attempted": len(bootstrap),
        "inception_bootstrap_ready": len(max_frames),
        "inception_pending": max(0, len(life_priority) - len(bootstrap)),
        "chart_ohlc": {ticker: chart[ticker] for ticker in trigger_tickers if ticker in chart},
        "inception_series": inception_series,
        "inception_values": {
            ticker: {"value": inception_value(record), "first": record.get("first"), "through": record.get("through"), "n": record.get("n")}
            for ticker, record in inception.items()
            if inception_value(record) is not None
        },
    }
    write_json(root / "history" / "vwap_restore.json", vwap_payload)

    print(json.dumps({
        "session_date": session,
        "search_rows": len(search),
        "leader_candidates": len(leaders),
        "two_year_frames": len(frames),
        "setup_rows": len(setup_rows),
        "setup_restore_requested": setup_payload.get("requested"),
        "setup_restore_received": setup_payload.get("received"),
        "setup_restore_coverage": setup_payload.get("coverage"),
        "trigger_rows": len(trigger_tickers),
        "option_targets": len(options_targets),
        "chart_ready": sum(1 for ticker in chart_targets if chart.get(ticker)),
        "inception_ready": len(inception),
        "inception_bootstrap_attempted": len(bootstrap),
        "inception_pending": max(0, len(life_priority) - len(bootstrap)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
