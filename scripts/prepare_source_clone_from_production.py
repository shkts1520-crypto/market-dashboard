#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from v38.live_acquisition import (
    MIN_PUBLICATION_STOCK_COVERAGE,
    _download,
    market_rows,
    select_yfinance_symbol_frame,
    write_json,
)

PUBLISH_SECTOR_SYMBOLS = (
    "RSPT", "RSPF", "RSPN", "RSPD", "RSPM", "RSPC",
    "RSPU", "RSPS", "RSPH", "RSPR", "RSPG",
)


class ProductionHandoffError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProductionHandoffError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ProductionHandoffError(f"JSON object required: {path}")
    return obj


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def validate_production_handoff(
    data_dir: str | Path,
    handoff_dir: str | Path,
) -> dict[str, Any]:
    data_root = Path(data_dir)
    handoff_root = Path(handoff_dir)
    state = _load(data_root / "state.json")
    rs = _load(data_root / "rs.json")
    mc57 = _load(data_root / "mc57.json")
    handoff = _load(handoff_root / "handoff.json")
    session = str(state.get("session_date") or "")

    if not session:
        raise ProductionHandoffError("data/state.json session_date missing")
    for name, obj in (("rs", rs), ("mc57", mc57), ("handoff", handoff)):
        if str(obj.get("session_date") or "") != session:
            raise ProductionHandoffError(
                f"{name} session mismatch: {obj.get('session_date')} != {session}"
            )
    if mc57.get("status") != "READY" or float(mc57.get("coverage") or 0.0) != 1.0:
        raise ProductionHandoffError("Production MC57 must be READY with 100% fixed-57 coverage")

    active = int(rs.get("coverage_detail", {}).get("active_universe") or 0)
    current_valid = int(rs.get("coverage_detail", {}).get("current_valid_ohlcv") or 0)
    stock_coverage = float(rs.get("coverage") or 0.0)
    if active <= 0 or current_valid <= 0 or stock_coverage < MIN_PUBLICATION_STOCK_COVERAGE:
        raise ProductionHandoffError(
            f"Production stock coverage invalid: {current_valid}/{active}={stock_coverage:.3f}"
        )
    if int(handoff.get("active_universe") or 0) != active:
        raise ProductionHandoffError("handoff active_universe does not match Production rs.json")
    if int(handoff.get("current_valid_ohlcv") or 0) != current_valid:
        raise ProductionHandoffError("handoff current_valid_ohlcv does not match Production rs.json")

    ohlcv_path = handoff_root / "ohlcv.csv"
    universe_path = handoff_root / "universe.csv"
    if not ohlcv_path.is_file() or ohlcv_path.stat().st_size <= 0:
        raise ProductionHandoffError("handoff ohlcv.csv missing")
    if not universe_path.is_file() or universe_path.stat().st_size <= 0:
        raise ProductionHandoffError("handoff universe.csv missing")

    universe_tickers: set[str] = set()
    with universe_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("session_date") or "") != session:
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker:
                universe_tickers.add(ticker)
    if len(universe_tickers) != active:
        raise ProductionHandoffError(
            f"handoff universe count mismatch: {len(universe_tickers)} != {active}"
        )

    target_tickers: set[str] = set()
    with ohlcv_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("date") or "") != session:
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            close = _finite(row.get("close"))
            if ticker and close is not None and close > 0:
                target_tickers.add(ticker)
    raw_coverage = len(target_tickers) / active
    if len(target_tickers) != current_valid or raw_coverage < MIN_PUBLICATION_STOCK_COVERAGE:
        raise ProductionHandoffError(
            f"handoff raw OHLCV mismatch: {len(target_tickers)}/{active}={raw_coverage:.3f}; "
            f"Production current_valid_ohlcv={current_valid}"
        )

    return {
        "session_date": session,
        "active_universe": active,
        "current_valid_ohlcv": current_valid,
        "stock_coverage": stock_coverage,
        "raw_coverage": raw_coverage,
    }


def _previous_series(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    series = obj.get("series") if isinstance(obj, dict) else None
    return series if isinstance(series, dict) else {}


def refresh_publish_sector_history(
    yf: Any,
    *,
    market_inputs: dict[str, Any],
    session: str,
    previous_market_inputs: Path | None = None,
) -> dict[str, int]:
    try:
        raw = _download(
            yf,
            list(PUBLISH_SECTOR_SYMBOLS),
            period="2y",
            threads=False,
        )
    except Exception:
        raw = pd.DataFrame()

    fresh: dict[str, list[dict[str, Any]]] = {}
    for symbol in PUBLISH_SECTOR_SYMBOLS:
        rows = market_rows(
            select_yfinance_symbol_frame(raw, symbol),
            target_session=session,
            max_rows=520,
        )
        if not rows or rows[-1].get("date") != session:
            try:
                retry = _download(yf, [symbol], period="2y", threads=False)
            except Exception:
                retry = pd.DataFrame()
            retried = market_rows(
                select_yfinance_symbol_frame(retry, symbol),
                target_session=session,
                max_rows=520,
            )
            if retried:
                rows = retried
        fresh[symbol] = rows

    current_series = market_inputs.get("series")
    if not isinstance(current_series, dict):
        current_series = {}
        market_inputs["series"] = current_series
    previous = _previous_series(previous_market_inputs)

    counts: dict[str, int] = {}
    latest: dict[str, str | None] = {}
    for symbol in PUBLISH_SECTOR_SYMBOLS:
        by_date: dict[str, dict[str, Any]] = {}
        for source_rows in (
            previous.get(symbol),
            current_series.get(symbol),
            fresh.get(symbol),
        ):
            if not isinstance(source_rows, list):
                continue
            for row in source_rows:
                if not isinstance(row, dict):
                    continue
                day = str(row.get("date") or "")
                if day and day <= session:
                    by_date[day] = row
        merged = [by_date[day] for day in sorted(by_date)][-520:]
        current_series[symbol] = merged
        counts[symbol] = len(merged)
        latest[symbol] = str(merged[-1].get("date")) if merged else None

    bad = [
        symbol
        for symbol in PUBLISH_SECTOR_SYMBOLS
        if counts[symbol] < 190 or latest[symbol] != session
    ]
    if bad:
        raise ProductionHandoffError(
            "Publish major-sector history incomplete: "
            + json.dumps(
                {"bad": bad, "counts": counts, "latest": latest, "session": session},
                sort_keys=True,
            )
        )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare source-mc57 clone from the already successful Production acquisition"
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--previous-market-inputs")
    args = parser.parse_args()

    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("yfinance==0.2.66 is required") from exc

    data_dir = Path(args.data_dir)
    work_dir = Path(args.work_dir)
    handoff_dir = Path(args.handoff_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    audit = validate_production_handoff(data_dir, handoff_dir)
    shutil.copyfile(handoff_dir / "ohlcv.csv", work_dir / "ohlcv.csv")
    shutil.copyfile(handoff_dir / "universe.csv", work_dir / "universe.csv")

    market_path = data_dir / "market_inputs.json"
    market_inputs = _load(market_path)
    if str(market_inputs.get("session_date") or "") != audit["session_date"]:
        raise ProductionHandoffError("Production market_inputs session mismatch")

    previous = Path(args.previous_market_inputs) if args.previous_market_inputs else None
    counts = refresh_publish_sector_history(
        yf,
        market_inputs=market_inputs,
        session=audit["session_date"],
        previous_market_inputs=previous,
    )
    write_json(market_path, market_inputs)

    print(json.dumps({
        **audit,
        "status": "READY_PRODUCTION_HANDOFF",
        "all_stock_yahoo_redownload": False,
        "production_mc57_reused": True,
        "publish_sector_symbols_refreshed": len(PUBLISH_SECTOR_SYMBOLS),
        "publish_sector_min_history": min(counts.values()) if counts else 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
