from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from .f123_engine import calculate_f123_from_files
from .freshness import atomic_write_json
from .live_acquisition import (
    TRADINGVIEW_URL,
    _download,
    adjusted_ohlcv_rows,
    select_yfinance_symbol_frame,
    yahoo_symbol,
)
from .stock_adapter import calculate_from_files

CALCULATION_VERSION = "v38-stock-gap-repair-1.2.0"

# Verified corporate-action continuity used only when the new Yahoo symbol is
# temporarily missing. JAB Acquisition Corp I changed its Nasdaq Class A ticker
# from JAB to ATLQ effective 2026-08-31 without a CUSIP change. The mapping never
# creates synthetic prices: pre-change history comes from the prior Yahoo symbol,
# while post-change target-session data must be an exact observed ATLQ/JAB bar.
CORPORATE_ACTION_ALIASES: dict[str, dict[str, Any]] = {
    "ATLQ": {
        "prior_ticker": "JAB",
        "exchange": "NASDAQ",
        "effective_from": "2026-08-31",
        "same_cusip": True,
        "provenance": "Nasdaq issuer notice 2026-08-26; effective 2026-08-31",
    },
}


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


def _yahoo_rows(yf: Any, *, ticker: str, symbol: str, target_session: str) -> list[dict[str, Any]]:
    try:
        raw = _download(yf, [symbol], period="2y", threads=False)
    except Exception:
        raw = pd.DataFrame()
    frame = select_yfinance_symbol_frame(raw, symbol)
    rows = adjusted_ohlcv_rows(frame, ticker=ticker, target_session=target_session)
    if rows:
        return rows
    fallback = _ticker_history_fallback(yf, symbol)
    return adjusted_ohlcv_rows(fallback, ticker=ticker, target_session=target_session)


def _nasdaq_number(value: Any) -> float | None:
    text = str(value if value is not None else "").strip().replace("$", "").replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "NONE", "--", "-"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _nasdaq_historical_current_bar(*, ticker: str, target_session: str) -> dict[str, Any] | None:
    """Fetch one exact target-session daily bar from Nasdaq's public quote history.

    This is deliberately exact-date only. A stale prior close is never rolled
    forward to fabricate a missing current-session observation.
    """
    query = urllib.parse.urlencode(
        {
            "assetclass": "stocks",
            "fromdate": target_session,
            "todate": target_session,
            "limit": "10",
        }
    )
    symbol = urllib.parse.quote(ticker, safe="")
    url = f"https://api.nasdaq.com/api/quote/{symbol}/historical?{query}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/historical",
            "User-Agent": "Mozilla/5.0 (v38-market-dashboard-gap-repair)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            obj = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    data = obj.get("data") if isinstance(obj, dict) else None
    table = data.get("tradesTable") if isinstance(data, dict) else None
    rows = table.get("rows") if isinstance(table, dict) else None
    if not isinstance(rows, list):
        return None

    try:
        target_mdy = pd.Timestamp(target_session).strftime("%m/%d/%Y")
    except Exception:
        return None
    for raw in rows:
        if not isinstance(raw, dict) or str(raw.get("date") or "").strip() != target_mdy:
            continue
        open_ = _nasdaq_number(raw.get("open"))
        high = _nasdaq_number(raw.get("high"))
        low = _nasdaq_number(raw.get("low"))
        close = _nasdaq_number(raw.get("close"))
        volume = _nasdaq_number(raw.get("volume"))
        if None in {open_, high, low, close, volume}:
            return None
        assert open_ is not None and high is not None and low is not None and close is not None and volume is not None
        if close <= 0 or high < low or volume < 0:
            return None
        return {
            "ticker": ticker,
            "date": target_session,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "is_complete": True,
            "split_checked": True,
            "split_anomaly": False,
        }
    return None


def _tradingview_current_bar(*, ticker: str, exchange: str, target_session: str) -> dict[str, Any] | None:
    payload = {
        "filter": [],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": [f"{exchange}:{ticker}"]},
        "columns": ["open", "high", "low", "close", "volume"],
        "range": [0, 1],
    }
    req = urllib.request.Request(
        TRADINGVIEW_URL,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (v38-market-dashboard-gap-repair)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            obj = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    data = obj.get("data") if isinstance(obj, dict) else None
    if not isinstance(data, list) or not data:
        return None
    values = data[0].get("d") if isinstance(data[0], dict) else None
    if not isinstance(values, list) or len(values) < 5:
        return None
    try:
        open_, high, low, close, volume = [float(x) for x in values[:5]]
    except (TypeError, ValueError):
        return None
    if not all(pd.notna(x) for x in (open_, high, low, close, volume)):
        return None
    if close <= 0 or high < low or volume < 0:
        return None
    return {
        "ticker": ticker,
        "date": target_session,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "is_complete": True,
        "split_checked": True,
        "split_anomaly": False,
    }


def _corporate_action_rows(
    yf: Any,
    *,
    ticker: str,
    target_session: str,
) -> list[dict[str, Any]]:
    alias = CORPORATE_ACTION_ALIASES.get(ticker)
    if not alias or alias.get("same_cusip") is not True:
        return []
    prior = str(alias["prior_ticker"])
    effective = str(alias["effective_from"])
    exchange = str(alias["exchange"])

    prior_rows = _yahoo_rows(
        yf,
        ticker=ticker,
        symbol=yahoo_symbol(prior),
        target_session=target_session,
    )
    direct_rows = _yahoo_rows(
        yf,
        ticker=ticker,
        symbol=yahoo_symbol(ticker),
        target_session=target_session,
    )
    by_date: dict[str, dict[str, Any]] = {}
    for row in prior_rows:
        if str(row.get("date") or "") < effective:
            by_date[str(row["date"])] = row
    for row in direct_rows:
        if str(row.get("date") or "") >= effective:
            by_date[str(row["date"])] = row

    if target_session not in by_date:
        current = _nasdaq_historical_current_bar(
            ticker=ticker,
            target_session=target_session,
        )
        if current is not None:
            by_date[target_session] = current

    if target_session not in by_date:
        current = _tradingview_current_bar(
            ticker=ticker,
            exchange=exchange,
            target_session=target_session,
        )
        if current is not None:
            by_date[target_session] = current

    if target_session not in by_date:
        # Some data vendors keep the old symbol as an alias after a same-CUSIP
        # rename. Accept it only when the provider returns the exact target date;
        # never roll a pre-change or stale bar forward.
        legacy_current = next(
            (
                row for row in prior_rows
                if str(row.get("date") or "") == target_session
                and row.get("close") is not None
            ),
            None,
        )
        if legacy_current is not None:
            by_date[target_session] = legacy_current
    return [by_date[day] for day in sorted(by_date)]


def isolated_history_rows(
    yf: Any,
    *,
    ticker: str,
    target_session: str,
) -> list[dict[str, Any]]:
    symbol = yahoo_symbol(ticker)
    rows = _yahoo_rows(yf, ticker=ticker, symbol=symbol, target_session=target_session)
    if any(row.get("date") == target_session and row.get("close") is not None for row in rows):
        return rows

    alias_rows = _corporate_action_rows(
        yf,
        ticker=ticker,
        target_session=target_session,
    )
    return alias_rows if any(
        row.get("date") == target_session and row.get("close") is not None
        for row in alias_rows
    ) else []


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
    source = "TradingView america/scan universe + Yahoo Finance/yfinance 0.2.66 adjusted by Adj Close; isolated gap retry; verified corporate-action alias with exact Nasdaq/TradingView target-session fallback when required"
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
    yahoo["isolated_retry_source"] = (
        "Yahoo isolated retry; ATLQ may join verified JAB pre-change history to an exact "
        "Nasdaq historical or completed TradingView ATLQ target-session bar; exact-date "
        "same-CUSIP JAB provider alias is final fallback"
    )
    manifest["yahoo"] = yahoo
    manifest["corporate_action_aliases"] = {
        ticker: CORPORATE_ACTION_ALIASES[ticker]
        for ticker in repaired
        if ticker in CORPORATE_ACTION_ALIASES
    }
    if yahoo.get("target_session_coverage") is not None:
        manifest["coverage"] = yahoo["target_session_coverage"]
        state["coverage"] = yahoo["target_session_coverage"]
    manifest["gap_repair_version"] = CALCULATION_VERSION
    atomic_write_json(manifest_path, manifest)
    atomic_write_json(state_path, state)
    return {"status": "REPAIRED" if not remaining else "PARTIAL", "repaired": sorted(repaired), "remaining": remaining}
