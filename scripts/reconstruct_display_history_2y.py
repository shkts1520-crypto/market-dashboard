#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from v38.freshness import atomic_write_json
from v38.historical_reconstruction import write_reconstructed_stock_history
from v38.live_acquisition import (
    MARKET_SYMBOLS,
    adjusted_ohlcv_rows,
    market_rows,
    select_yfinance_symbol_frame,
    yahoo_symbol,
)

DISPLAY_SESSIONS = 504
STOCK_DOWNLOAD_PERIOD = "3y"  # 2y display + >=200-session indicator pre-roll
MARKET_DOWNLOAD_PERIOD = "2y"


def _load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return obj


def _active_tickers(rs: dict[str, Any]) -> list[str]:
    names = {
        str(row.get("ticker") or "").strip().upper()
        for row in (rs.get("rows") or [])
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }
    names.update(
        str(row.get("ticker") or "").strip().upper()
        for row in (rs.get("excluded") or [])
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    )
    return sorted(name for name in names if name)


def _download(symbols: list[str], *, period: str, threads: int | bool = 16) -> pd.DataFrame:
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


def _write_stock_ohlcv(path: Path, tickers: list[str], target_session: str, chunk_size: int = 100) -> dict[str, Any]:
    fields = ("ticker", "date", "open", "high", "low", "close", "volume", "is_complete", "split_checked", "split_anomaly")
    path.parent.mkdir(parents=True, exist_ok=True)
    target_ok = 0
    history_ok = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for offset in range(0, len(tickers), chunk_size):
            originals = tickers[offset:offset + chunk_size]
            symbol_map = {ticker: yahoo_symbol(ticker) for ticker in originals}
            try:
                raw = _download(list(symbol_map.values()), period=STOCK_DOWNLOAD_PERIOD)
            except Exception:
                raw = pd.DataFrame()
            for ticker, symbol in symbol_map.items():
                rows = adjusted_ohlcv_rows(
                    select_yfinance_symbol_frame(raw, symbol),
                    ticker=ticker,
                    target_session=target_session,
                )
                if not rows or not any(row["date"] == target_session and row["close"] is not None for row in rows):
                    try:
                        retry = _download([symbol], period=STOCK_DOWNLOAD_PERIOD, threads=False)
                    except Exception:
                        retry = pd.DataFrame()
                    rows = adjusted_ohlcv_rows(
                        select_yfinance_symbol_frame(retry, symbol),
                        ticker=ticker,
                        target_session=target_session,
                    )
                if rows:
                    history_ok += 1
                    writer.writerows(rows)
                if any(row["date"] == target_session and row["close"] is not None for row in rows):
                    target_ok += 1
    return {
        "requested": len(tickers),
        "history_ok": history_ok,
        "target_ok": target_ok,
        "target_coverage": target_ok / len(tickers) if tickers else 0.0,
        "period": STOCK_DOWNLOAD_PERIOD,
    }


def _diagnostics(frame: pd.DataFrame, tickers: list[str], session: str) -> dict[str, Any]:
    d = frame.copy()
    d.columns = [str(column).strip().lower().replace(" ", "_") for column in d.columns]
    if d.empty:
        return {"status": "DATA_REQUIRED", "series": []}
    d["ticker"] = d["ticker"].astype(str).str.strip().str.upper()
    parsed = pd.to_datetime(d["date"], errors="coerce", utc=True)
    d = d.loc[parsed.notna()].copy()
    d["date"] = parsed.loc[parsed.notna()].dt.strftime("%Y-%m-%d")
    for column in ("close", "volume"):
        d[column] = pd.to_numeric(d[column], errors="coerce")
    for flag in ("is_complete", "split_checked"):
        d[flag] = d[flag].astype(str).str.lower().isin({"true", "1", "yes", "ok", "checked", "complete", "completed"})
    d["split_anomaly"] = d["split_anomaly"].astype(str).str.lower().isin({"true", "1", "yes"})
    d = d[
        d["ticker"].isin(tickers)
        & (d["date"] <= session)
        & d["is_complete"]
        & d["split_checked"]
        & (~d["split_anomaly"])
    ].dropna(subset=["close", "volume"])
    d = d[(d["close"] > 0) & (d["volume"] >= 0)].sort_values(["ticker", "date"], kind="mergesort")
    if d.empty:
        return {"status": "DATA_REQUIRED", "series": []}

    d["prior_close"] = d.groupby("ticker", sort=False)["close"].shift(1)
    d["advance"] = d["close"] > d["prior_close"]
    d["decline"] = d["close"] < d["prior_close"]
    d["dollar_volume"] = d["close"] * d["volume"]
    d["advance_dollar_volume"] = d["dollar_volume"].where(d["advance"], 0.0)
    d["decline_dollar_volume"] = d["dollar_volume"].where(d["decline"], 0.0)
    daily = d.groupby("date", sort=True).agg(
        observed=("ticker", "nunique"),
        advances=("advance", "sum"),
        declines=("decline", "sum"),
        total_volume=("volume", "sum"),
        advance_dollar_volume=("advance_dollar_volume", "sum"),
        decline_dollar_volume=("decline_dollar_volume", "sum"),
    )
    daily["ad_net"] = daily["advances"] - daily["declines"]
    daily["ad_line"] = daily["ad_net"].cumsum()
    daily["mcclellan"] = daily["ad_net"].ewm(span=19, adjust=False).mean() - daily["ad_net"].ewm(span=39, adjust=False).mean()
    daily["volume_participation"] = daily["total_volume"] / daily["total_volume"].shift(1).rolling(200, min_periods=20).mean()
    daily["up_down_dollar_ratio"] = daily["advance_dollar_volume"] / daily["decline_dollar_volume"].replace(0, np.nan)
    daily["advancing_pct"] = 100.0 * daily["advances"] / daily["observed"].replace(0, np.nan)

    def number(value: Any) -> float | None:
        return float(value) if pd.notna(value) and math.isfinite(float(value)) else None

    rows = []
    for day, row in daily.tail(DISPLAY_SESSIONS).iterrows():
        rows.append({
            "date": str(day),
            "observed": int(row["observed"]),
            "advances": int(row["advances"]),
            "declines": int(row["declines"]),
            "advancing_pct": number(row["advancing_pct"]),
            "volume_participation": number(row["volume_participation"]),
            "up_down_dollar_ratio": number(row["up_down_dollar_ratio"]),
            "ad_line": number(row["ad_line"]),
            "mcclellan": number(row["mcclellan"]),
        })
    return {
        "status": "READY" if rows and rows[-1]["date"] == session else "DATA_REQUIRED",
        "series": rows,
    }


def _market_series(session: str) -> dict[str, list[dict[str, Any]]]:
    series: dict[str, list[dict[str, Any]]] = {}
    for offset in range(0, len(MARKET_SYMBOLS), 10):
        symbols = list(MARKET_SYMBOLS[offset:offset + 10])
        try:
            raw = _download(symbols, period=MARKET_DOWNLOAD_PERIOD, threads=False)
        except Exception:
            raw = pd.DataFrame()
        for symbol in symbols:
            rows = market_rows(
                select_yfinance_symbol_frame(raw, symbol),
                target_session=session,
                max_rows=DISPLAY_SESSIONS,
            )
            if not rows or rows[-1]["date"] != session:
                try:
                    retry = _download([symbol], period=MARKET_DOWNLOAD_PERIOD, threads=False)
                except Exception:
                    retry = pd.DataFrame()
                rows = market_rows(
                    select_yfinance_symbol_frame(retry, symbol),
                    target_session=session,
                    max_rows=DISPLAY_SESSIONS,
                )
            if rows:
                series[symbol] = rows[-DISPLAY_SESSIONS:]
    return series


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild original two-year display trends")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    root = Path(args.data_dir)
    state = _load(root / "state.json")
    rs = _load(root / "rs.json")
    session = str(state.get("session_date") or "")
    if not session or rs.get("session_date") != session:
        raise SystemExit("state/rs session mismatch")
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    tickers = _active_tickers(rs)
    if not tickers:
        raise SystemExit("no current-universe tickers")

    work = Path(tempfile.mkdtemp(prefix="v38-display-history-"))
    ohlcv_path = work / "ohlcv_3y.csv"
    stats = _write_stock_ohlcv(ohlcv_path, tickers, session)
    if stats["target_coverage"] < 0.80:
        raise SystemExit(f"three-year display-history coverage too low: {stats['target_coverage']:.3f}")

    reconstructed = root / "history" / "reconstructed_stock_metrics.json"
    write_reconstructed_stock_history(
        ohlcv_path,
        tickers,
        reconstructed,
        session_date=session,
        generated_at=generated_at,
        sessions=DISPLAY_SESSIONS,
    )

    frame = pd.read_csv(ohlcv_path)
    diagnostics = _diagnostics(frame, tickers, session)
    diagnostics.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": stats["target_coverage"],
        "source": "Yahoo Finance 3y current-universe display reconstruction",
        "schema_version": "v38.display_diagnostics_2y.1",
        "calculation_version": "v38-display-history-2y-1.0.0",
        "trading_gate_eligible": False,
    })
    atomic_write_json(root / "history" / "market_diagnostics_2y.json", diagnostics)

    market = {
        "session_date": session,
        "generated_at": generated_at,
        "coverage": None,
        "source": "Yahoo Finance 2y daily market series",
        "schema_version": "v38.market_series_2y.1",
        "calculation_version": "v38-display-history-2y-1.0.0",
        "status": "READY",
        "trading_gate_eligible": False,
        "series": _market_series(session),
    }
    market["coverage"] = len(market["series"]) / len(MARKET_SYMBOLS)
    atomic_write_json(root / "history" / "market_series_2y.json", market)

    rebuilt = _load(reconstructed)
    print(json.dumps({
        "session_date": session,
        "stock_download": stats,
        "stock_history_sessions": rebuilt.get("session_count"),
        "stock_history_first": rebuilt.get("first_session"),
        "diagnostic_sessions": len(diagnostics.get("series") or []),
        "market_symbols": len(market["series"]),
        "display_sessions": DISPLAY_SESSIONS,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
