from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .f123_engine import calculate_f123_from_files
from .freshness import atomic_write_json
from .live_acquisition import (
    _download,
    adjusted_ohlcv_rows,
    select_yfinance_symbol_frame,
    yahoo_symbol,
)
from .stock_adapter import calculate_from_files

CALCULATION_VERSION = "v38-stock-gap-repair-1.0.0"


class StockGapRepairError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _ticker_history_fallback(yf: Any, symbol: str) -> pd.DataFrame:
    try:
        raw = yf.Ticker(symbol).history(
            period="2y",
            interval="1d",
            auto_adjust=True,
            actions=False,
        )
    except Exception:
        return pd.DataFrame()
    if raw is None or raw.empty:
        return pd.DataFrame()
    frame = raw.copy()
    if "Close" in frame.columns and "Adj Close" not in frame.columns:
        frame["Adj Close"] = frame["Close"]
    return frame


def isolated_history_rows(
    yf: Any,
    *,
    ticker: str,
    target_session: str,
) -> list[dict[str, Any]]:
    symbol = yahoo_symbol(ticker)
    try:
        raw = _download(yf, [symbol], period="2y", threads=False)
    except Exception:
        raw = pd.DataFrame()
    frame = select_yfinance_symbol_frame(raw, symbol)
    rows = adjusted_ohlcv_rows(frame, ticker=ticker, target_session=target_session)
    if any(row.get("date") == target_session and row.get("close") is not None for row in rows):
        return rows

    fallback = _ticker_history_fallback(yf, symbol)
    rows = adjusted_ohlcv_rows(fallback, ticker=ticker, target_session=target_session)
    return rows if any(row.get("date") == target_session and row.get("close") is not None for row in rows) else []


def _rewrite_ohlcv(path: Path, repaired: dict[str, list[dict[str, Any]]]) -> None:
    frame = pd.read_csv(path)
    if not repaired:
        return
    tickers = set(repaired)
    frame["ticker"] = frame["ticker"].astype(str).str.strip().str.upper()
    frame = frame[~frame["ticker"].isin(tickers)].copy()
    append_rows = [row for rows in repaired.values() for row in rows]
    combined = pd.concat([frame, pd.DataFrame(append_rows)], ignore_index=True, sort=False)
    combined = combined.sort_values(["ticker", "date"], kind="mergesort").drop_duplicates(["ticker", "date"], keep="last")
    fields = ["ticker", "date", "open", "high", "low", "close", "volume", "is_complete", "split_checked", "split_anomaly"]
    combined.to_csv(path, index=False, columns=fields, quoting=csv.QUOTE_MINIMAL)


def repair_failed_live_tickers(
    data_dir: str | Path,
    work_dir: str | Path,
    *,
    generated_at: str,
) -> dict[str, Any]:
    root = Path(data_dir)
    work = Path(work_dir)
    manifest_path = root / "acquisition_manifest.json"
    state_path = root / "state.json"
    manifest = _load(manifest_path)
    state = _load(state_path)
    session = str(state.get("session_date") or manifest.get("session_date") or "")
    yahoo = manifest.get("yahoo") if isinstance(manifest.get("yahoo"), dict) else {}
    failed = [str(x).strip().upper() for x in yahoo.get("failed_tickers", []) if str(x).strip()]
    if not failed:
        return {"status": "NO_GAPS", "repaired": [], "remaining": []}
    ohlcv_path = work / "ohlcv.csv"
    universe_path = work / "universe.csv"
    if not session or not ohlcv_path.is_file() or not universe_path.is_file():
        return {"status": "WORK_INPUT_UNAVAILABLE", "repaired": [], "remaining": failed}

    try:
        import yfinance as yf
    except ImportError as exc:
        raise StockGapRepairError("yfinance is required") from exc

    repaired: dict[str, list[dict[str, Any]]] = {}
    for ticker in failed:
        rows = isolated_history_rows(yf, ticker=ticker, target_session=session)
        if rows:
            repaired[ticker] = rows
    if not repaired:
        return {"status": "UNRESOLVED", "repaired": [], "remaining": failed}

    _rewrite_ohlcv(ohlcv_path, repaired)
    source = "TradingView america/scan universe + Yahoo Finance/yfinance 0.2.66 adjusted by Adj Close; isolated gap retry"
    calculate_from_files(
        ohlcv_path,
        universe_path,
        root,
        session_date=session,
        generated_at=generated_at,
        source=source,
    )
    old_top24 = root / "old_top24.json"
    calculate_f123_from_files(
        root / "rs.json",
        root / "f123.json",
        generated_at=generated_at,
        old_top24_path=old_top24 if old_top24.is_file() else None,
    )

    remaining = [ticker for ticker in failed if ticker not in repaired]
    requested = int(yahoo.get("requested") or 0)
    current_received = int(yahoo.get("target_session_received") or 0)
    history_received = int(yahoo.get("history_received") or 0)
    added = len(repaired)
    yahoo["target_session_received"] = min(requested, current_received + added) if requested else current_received + added
    yahoo["history_received"] = min(requested, history_received + added) if requested else history_received + added
    yahoo["target_session_coverage"] = yahoo["target_session_received"] / requested if requested else None
    yahoo["failed_tickers"] = remaining
    yahoo["isolated_retry_repaired"] = sorted(repaired)
    manifest["yahoo"] = yahoo
    if yahoo.get("target_session_coverage") is not None:
        manifest["coverage"] = yahoo["target_session_coverage"]
        state["coverage"] = yahoo["target_session_coverage"]
    manifest["gap_repair_version"] = CALCULATION_VERSION
    atomic_write_json(manifest_path, manifest)
    atomic_write_json(state_path, state)
    return {"status": "REPAIRED" if not remaining else "PARTIAL", "repaired": sorted(repaired), "remaining": remaining}
