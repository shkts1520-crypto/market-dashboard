from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from . import stock_gap_repair as base

CALCULATION_VERSION = "v38-stock-gap-repair-exact-1.0.0"


def _existing_history_rows(path: Path, ticker: str) -> list[dict[str, Any]]:
    try:
        frame = pd.read_csv(path)
    except Exception:
        return []
    if "ticker" not in frame.columns:
        return []
    symbols = frame["ticker"].astype(str).str.strip().str.upper()
    rows = frame.loc[symbols.eq(ticker)].copy()
    if rows.empty:
        return []
    out: list[dict[str, Any]] = []
    for row in rows.to_dict("records"):
        item = {
            "ticker": ticker,
            "date": str(row.get("date") or ""),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
            "is_complete": bool(row.get("is_complete", True)),
            "split_checked": bool(row.get("split_checked", True)),
            "split_anomaly": bool(row.get("split_anomaly", False)),
        }
        if item["date"] and base._valid_observed_row(item):
            out.append(item)
    return out


def _repair_remaining_with_exact_nasdaq(
    data_dir: str | Path,
    work_dir: str | Path,
    *,
    generated_at: str,
    remaining: list[str],
) -> dict[str, Any]:
    root = Path(data_dir)
    work = Path(work_dir)
    ohlcv_path = work / "ohlcv.csv"
    universe_path = work / "universe.csv"
    manifest_path = root / "acquisition_manifest.json"
    state_path = root / "state.json"
    manifest = base._load(manifest_path)
    state = base._load(state_path)
    session = str(state.get("session_date") or manifest.get("session_date") or "")
    if not session or not ohlcv_path.is_file() or not universe_path.is_file():
        return {"status": "WORK_INPUT_UNAVAILABLE", "repaired": [], "remaining": remaining}

    repaired: dict[str, list[dict[str, Any]]] = {}
    for ticker in remaining:
        current = base._nasdaq_historical_current_bar(
            ticker=ticker,
            target_session=session,
        )
        if current is None or not base._valid_observed_row(current):
            continue
        history = _existing_history_rows(ohlcv_path, ticker)
        by_date = {
            str(row["date"]): row
            for row in history
            if str(row.get("date") or "") != session
        }
        by_date[session] = current
        repaired[ticker] = [by_date[day] for day in sorted(by_date)]

    if not repaired:
        return {"status": "UNRESOLVED", "repaired": [], "remaining": remaining}

    base._rewrite_ohlcv(ohlcv_path, repaired)
    source = (
        "TradingView america/scan universe + Yahoo Finance/yfinance 0.2.66 adjusted by Adj Close; "
        "isolated Yahoo retry; exact-date Nasdaq historical target-session fallback; "
        "verified corporate-action alias fallback only when required"
    )
    base.calculate_from_files(
        ohlcv_path,
        universe_path,
        root,
        session_date=session,
        generated_at=generated_at,
        source=source,
    )
    old_top24 = root / "old_top24.json"
    base.calculate_f123_from_files(
        root / "rs.json",
        root / "f123.json",
        generated_at=generated_at,
        old_top24_path=old_top24 if old_top24.is_file() else None,
    )

    manifest = base._load(manifest_path)
    state = base._load(state_path)
    yahoo = manifest.get("yahoo") if isinstance(manifest.get("yahoo"), dict) else {}
    current_failed = [
        str(value).strip().upper()
        for value in yahoo.get("failed_tickers", remaining)
        if str(value).strip()
    ]
    newly_repaired = sorted(repaired)
    unresolved = [ticker for ticker in current_failed if ticker not in repaired]
    requested = int(yahoo.get("requested") or 0)
    current_received = int(yahoo.get("target_session_received") or 0)
    history_received = int(yahoo.get("history_received") or 0)
    yahoo["target_session_received"] = min(requested, current_received + len(newly_repaired)) if requested else current_received + len(newly_repaired)
    yahoo["history_received"] = min(requested, history_received) if requested else history_received
    yahoo["target_session_coverage"] = yahoo["target_session_received"] / requested if requested else None
    yahoo["failed_tickers"] = unresolved
    prior_repaired = [str(value).strip().upper() for value in yahoo.get("isolated_retry_repaired", []) if str(value).strip()]
    yahoo["isolated_retry_repaired"] = sorted(set(prior_repaired) | set(newly_repaired))
    yahoo["isolated_retry_source"] = (
        "Yahoo isolated retry; remaining target-session gaps use Nasdaq historical only when an exact-date "
        "OHLCV row exists; stale prior closes are never rolled forward. Verified same-CUSIP corporate-action "
        "alias handling remains available for explicitly mapped symbols."
    )
    manifest["yahoo"] = yahoo
    manifest["gap_repair_version"] = CALCULATION_VERSION
    if yahoo.get("target_session_coverage") is not None:
        manifest["coverage"] = yahoo["target_session_coverage"]
        state["coverage"] = yahoo["target_session_coverage"]
    base.atomic_write_json(manifest_path, manifest)
    base.atomic_write_json(state_path, state)
    return {
        "status": "REPAIRED" if not unresolved else "PARTIAL",
        "repaired": newly_repaired,
        "remaining": unresolved,
    }


def repair_failed_live_tickers(
    data_dir: str | Path,
    work_dir: str | Path,
    *,
    generated_at: str,
) -> dict[str, Any]:
    """Run existing repair first, then exact-date Nasdaq for generic residual gaps."""
    first = base.repair_failed_live_tickers(
        data_dir,
        work_dir,
        generated_at=generated_at,
    )
    remaining = [str(value).strip().upper() for value in first.get("remaining", []) if str(value).strip()]
    if not remaining:
        return first
    second = _repair_remaining_with_exact_nasdaq(
        data_dir,
        work_dir,
        generated_at=generated_at,
        remaining=remaining,
    )
    combined = sorted(set(first.get("repaired", [])) | set(second.get("repaired", [])))
    unresolved = list(second.get("remaining", remaining))
    status = "REPAIRED" if not unresolved else ("PARTIAL" if combined else "UNRESOLVED")
    return {"status": status, "repaired": combined, "remaining": unresolved}
