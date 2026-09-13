#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import io
import json
import time
from pathlib import Path
import urllib.request

import pandas as pd

from v38.freshness import atomic_write_json
from v38.options_engine import (
    DEFAULT_TARGET_LIMIT,
    build_options_index,
    expiry_dte,
    frame_to_contracts,
    select_targets,
)

CHART_TARGET_FLOOR = 0
RISK_FREE_MAX_AGE_DAYS = 10
FRED_DGS3MO_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO&cosd={start}&coed={end}"


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


def _validate_rate(value) -> float:
    rate = _finite(value)
    if rate is None or not (0.0 <= rate <= 0.25):
        raise RuntimeError(f"risk-free rate out of range: {value}")
    return float(rate)


def _observed_date_from_index(index, fallback: str) -> str:
    if index is None or len(index) == 0:
        return fallback
    try:
        stamp = pd.Timestamp(index[-1])
        if pd.isna(stamp):
            return fallback
        return stamp.date().isoformat()
    except Exception:
        return fallback


def _rate_from_yahoo_frame(raw, *, session_date: str) -> tuple[float, str]:
    if raw is None or raw.empty:
        raise RuntimeError("empty frame")
    closes = None
    if isinstance(raw.columns, pd.MultiIndex):
        for key in (("Close", "^IRX"), ("^IRX", "Close")):
            if key in raw.columns:
                closes = raw[key]
                break
    elif "Close" in raw.columns:
        closes = raw["Close"]
    if closes is None:
        raise RuntimeError("Close column unavailable")
    values = pd.to_numeric(closes, errors="coerce").dropna()
    if values.empty:
        raise RuntimeError("no finite close")
    rate = _validate_rate(float(values.iloc[-1]) / 100.0)
    observed = _observed_date_from_index(values.index, session_date)
    return rate, observed


def _fred_risk_free_rate(session_date: str) -> tuple[float, str]:
    end = date.fromisoformat(session_date)
    start = end - timedelta(days=35)
    url = FRED_DGS3MO_URL.format(start=start.isoformat(), end=end.isoformat())
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "V38-market-dashboard/1.0 (+GitHub Actions)"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8", errors="replace")
    latest: tuple[str, float] | None = None
    for row in csv.DictReader(io.StringIO(payload)):
        observed = str(row.get("DATE") or row.get("observation_date") or "").strip()
        value = _finite(row.get("DGS3MO"))
        if not observed or value is None:
            continue
        try:
            age = (end - date.fromisoformat(observed)).days
        except ValueError:
            continue
        if 0 <= age <= RISK_FREE_MAX_AGE_DAYS:
            latest = (observed, value)
    if latest is None:
        raise RuntimeError("FRED DGS3MO has no recent finite observation")
    observed, percent = latest
    return _validate_rate(percent / 100.0), observed


def _previous_risk_free_rate(previous: dict, session_date: str) -> tuple[float, str, str]:
    rate = _validate_rate(previous.get("risk_free_rate"))
    observed = str(previous.get("risk_free_rate_observed_date") or "")
    if not observed:
        raise RuntimeError("previous observation date unavailable")
    end = date.fromisoformat(session_date)
    age = (end - date.fromisoformat(observed)).days
    if age < 0 or age > RISK_FREE_MAX_AGE_DAYS:
        raise RuntimeError(f"previous risk-free observation stale: {observed}")
    source = str(previous.get("risk_free_rate_source") or "previous observed rate")
    return rate, observed, "CACHED:" + source.removeprefix("CACHED:")


def _risk_free_rate(yf, *, session_date: str, previous: dict) -> tuple[float, str, str]:
    """Resolve a measured short Treasury rate without inventing a fixed fallback.

    Yahoo ^IRX remains first choice. If that endpoint is temporarily unavailable,
    use a second Yahoo history path, then the Federal Reserve/FRED DGS3MO series,
    and finally a recently persisted measured rate. Every successful path records
    its source and observation date in the published options shard.
    """
    errors: list[str] = []
    try:
        raw = yf.download(
            "^IRX", period="10d", interval="1d", auto_adjust=False,
            actions=False, progress=False, threads=False, timeout=20,
        )
        rate, observed = _rate_from_yahoo_frame(raw, session_date=session_date)
        return rate, "YAHOO:^IRX:download", observed
    except Exception as exc:
        errors.append("Yahoo download=" + str(exc)[:120])

    try:
        raw = yf.Ticker("^IRX").history(
            period="1mo", interval="1d", auto_adjust=False, actions=False,
        )
        rate, observed = _rate_from_yahoo_frame(raw, session_date=session_date)
        return rate, "YAHOO:^IRX:history", observed
    except Exception as exc:
        errors.append("Yahoo history=" + str(exc)[:120])

    try:
        rate, observed = _fred_risk_free_rate(session_date)
        return rate, "FRED:DGS3MO", observed
    except Exception as exc:
        errors.append("FRED DGS3MO=" + str(exc)[:120])

    try:
        return _previous_risk_free_rate(previous, session_date)
    except Exception as exc:
        errors.append("previous=" + str(exc)[:120])

    raise RuntimeError("; ".join(errors))


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
    # Never truncate the explicit clickable priority union.
    priority_count = len(out)
    for ticker in select_targets(rs, core12, limit=limit):
        add(ticker)
    return out[:max(priority_count, limit)]


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
    previous = _load(root / "options" / "index.json")
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
        rate, rate_source, rate_observed_date = _risk_free_rate(
            yf, session_date=session, previous=previous,
        )
    except Exception as exc:
        out = {
            "session_date": session,
            "generated_at": generated_at,
            "coverage": 0.0,
            "source": "Yahoo Finance option chains via yfinance 0.2.66",
            "schema_version": "v38.options.1",
            "calculation_version": "v38-options-live-1.0.2",
            "status": "DATA_REQUIRED",
            "reason": f"RISK_FREE_RATE_UNAVAILABLE:{str(exc)[:400]}",
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

    out = build_options_index(
        session_date=session,
        generated_at=generated_at,
        targets=targets,
        snapshots=snapshots,
        rate=rate,
        previous=previous,
    )
    out["calculation_version"] = "v38-options-live-1.0.2"
    out["risk_free_rate"] = rate
    out["risk_free_rate_source"] = rate_source
    out["risk_free_rate_observed_date"] = rate_observed_date
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
        "risk_free_rate_source": rate_source,
        "risk_free_rate_observed_date": rate_observed_date,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
