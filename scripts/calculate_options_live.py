#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
from collections import deque
from pathlib import Path
import sys

import calculate_options_live_legacy as _legacy
import calculate_options_resilient as _resilient

main = _resilient.main

# Options acquisition is deliberately narrower than the upstream active stock
# universe. The stock universe already enforces market cap >= $200M in
# v38.live_acquisition. For Options, use the union of the strongest 50 stocks by
# 21/63/189-session return inside the same liquid price universe.
OPTIONS_MIN_PRICE_USD = 5.0
OPTIONS_MIN_DDV20_USD = 10_000_000.0
UPSTREAM_MIN_MARKET_CAP_USD = 200_000_000.0
RS_LEADER_PERIODS = (21, 63, 189)
RS_LEADER_TOP_N = 50


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _investable_options_targets(rs: dict) -> list[str]:
    """Legacy helper retained for compatibility with existing authority tests."""
    out: set[str] = set()
    rows = rs.get("rows") if isinstance(rs, dict) else None
    if not isinstance(rows, list):
        return []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        price = _finite(row.get("price"))
        if ticker and price is not None and price >= OPTIONS_MIN_PRICE_USD:
            out.add(ticker)
    return sorted(out)


def _liquid_rs_rows(rs: dict) -> dict[str, dict]:
    rows = rs.get("rows") if isinstance(rs, dict) else None
    if not isinstance(rows, list):
        return {}
    eligible: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        price = _finite(row.get("price"))
        ddv20 = _finite(row.get("ddv20"))
        if (
            ticker
            and price is not None
            and price >= OPTIONS_MIN_PRICE_USD
            and ddv20 is not None
            and ddv20 >= OPTIONS_MIN_DDV20_USD
        ):
            eligible[ticker] = row
    return eligible


def _runner_ohlcv_path() -> Path:
    runner_temp = str(os.environ.get("RUNNER_TEMP") or "").strip()
    if not runner_temp:
        raise RuntimeError("RUNNER_TEMP is required to calculate exact RS21 Options targets")
    path = Path(runner_temp) / "v38-live" / "ohlcv.csv"
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"current-session OHLCV is required for RS21 Options targets: {path}")
    return path


def _ret21_from_current_ohlcv(tickers: set[str]) -> dict[str, float]:
    """Calculate exact 21-session returns from the already-acquired production OHLCV.

    fetch_live_data.py writes each ticker's two-year rows in chronological order.
    Keeping only the latest 22 closes per ticker is therefore sufficient and avoids
    a second Yahoo download or an RS schema change.
    """
    if not tickers:
        return {}
    closes: dict[str, deque[tuple[str, float]]] = {
        ticker: deque(maxlen=22) for ticker in tickers
    }
    with _runner_ohlcv_path().open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker not in closes:
                continue
            close = _finite(row.get("close"))
            day = str(row.get("date") or "").strip()
            if close is None or close <= 0 or not day:
                continue
            closes[ticker].append((day, close))

    out: dict[str, float] = {}
    for ticker, observations in closes.items():
        if len(observations) < 22:
            continue
        ordered = sorted(observations, key=lambda item: item[0])
        start = ordered[-22][1]
        end = ordered[-1][1]
        if start > 0:
            value = end / start - 1.0
            if math.isfinite(value):
                out[ticker] = float(value)
    return out


def _rank_top(values: dict[str, float], limit: int = RS_LEADER_TOP_N) -> list[str]:
    ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    return [ticker for ticker, _ in ranked[:limit]]


def _rs_leader_target_details(rs: dict) -> tuple[list[str], dict[str, list[str]]]:
    eligible = _liquid_rs_rows(rs)
    if not eligible:
        return [], {str(period): [] for period in RS_LEADER_PERIODS}

    ret21 = _ret21_from_current_ohlcv(set(eligible))
    values_by_period: dict[str, dict[str, float]] = {
        "21": ret21,
        "63": {},
        "189": {},
    }
    for ticker, row in eligible.items():
        for period in (63, 189):
            value = _finite(row.get(f"ret{period}"))
            if value is not None:
                values_by_period[str(period)][ticker] = value

    leaders = {
        period: _rank_top(values_by_period[period])
        for period in ("21", "63", "189")
    }
    targets = sorted({ticker for period in leaders.values() for ticker in period})
    if len(leaders["21"]) < RS_LEADER_TOP_N:
        raise RuntimeError(
            f"RS21 target universe incomplete: {len(leaders['21'])}/{RS_LEADER_TOP_N}"
        )
    if len(leaders["63"]) < RS_LEADER_TOP_N:
        raise RuntimeError(
            f"RS63 target universe incomplete: {len(leaders['63'])}/{RS_LEADER_TOP_N}"
        )
    if len(leaders["189"]) < RS_LEADER_TOP_N:
        raise RuntimeError(
            f"RS189 target universe incomplete: {len(leaders['189'])}/{RS_LEADER_TOP_N}"
        )
    return targets, leaders


def _rs_leader_options_targets(rs: dict) -> list[str]:
    targets, _ = _rs_leader_target_details(rs)
    return targets


# Keep the existing --all-universe execution path/token for compatibility, but
# replace the expensive full-universe chain scan with the user-approved target:
# RS21 Top50 U RS63 Top50 U RS189 Top50. No stock ranking or UI logic changes.
_resilient._all_universe_targets = _rs_leader_options_targets


# Keep the legacy status/mode token expected by the existing production workflow,
# while making the actual scope explicit and verifiable. Reject a stale preserved
# file if its target list does not exactly match the current RS leader union.
_original_atomic_write_json = _resilient.atomic_write_json


def _write_investable_options_contract(path, payload):
    path_obj = Path(path)
    if (
        path_obj.name == "index.json"
        and path_obj.parent.name == "options"
        and isinstance(payload, dict)
    ):
        policy = payload.get("target_policy")
        if isinstance(policy, dict) and policy.get("status") == "FULL_ACTIVE_UNIVERSE":
            rs_path = path_obj.parent.parent / "rs.json"
            if rs_path.is_file():
                rs = json.loads(rs_path.read_text(encoding="utf-8"))
                expected, leaders = _rs_leader_target_details(rs)
                actual = sorted({
                    str(ticker or "").strip().upper()
                    for ticker in (policy.get("targets") or [])
                    if str(ticker or "").strip()
                })
                if actual != expected:
                    raise RuntimeError(
                        "refusing stale Options target contract: expected "
                        f"{len(expected)} RS21/63/189 leader-union targets, got {len(actual)}"
                    )
                policy["period_counts"] = {
                    period: len(items) for period, items in leaders.items()
                }
            policy["scope"] = "RS_21_63_189_TOP50_UNION"
            policy["method"] = (
                "Union of the top 50 stocks by 21-, 63-, and 189-completed-session "
                "total return among current active-universe stocks with price >= $5 "
                "and DDV20 >= $10M; 21-session return uses the same current-session "
                "OHLCV already acquired by the production stock pipeline"
            )
            policy["periods"] = list(RS_LEADER_PERIODS)
            policy["top_n_per_period"] = RS_LEADER_TOP_N
            policy["min_price_usd"] = OPTIONS_MIN_PRICE_USD
            policy["min_ddv20_usd"] = OPTIONS_MIN_DDV20_USD
            policy["upstream_min_market_cap_usd"] = UPSTREAM_MIN_MARKET_CAP_USD
            overlay = payload.get("chart_overlay_contract")
            if isinstance(overlay, dict):
                overlay["target_priority"] = "RS_21_63_189_TOP50_UNION"
            scan = payload.get("universe_scan")
            if isinstance(scan, dict):
                scan["scope"] = "RS_21_63_189_TOP50_UNION"
                scan["periods"] = list(RS_LEADER_PERIODS)
                scan["top_n_per_period"] = RS_LEADER_TOP_N
                scan["min_price_usd"] = OPTIONS_MIN_PRICE_USD
                scan["min_ddv20_usd"] = OPTIONS_MIN_DDV20_USD
                scan["upstream_min_market_cap_usd"] = UPSTREAM_MIN_MARKET_CAP_USD
    return _original_atomic_write_json(path, payload)


_resilient.atomic_write_json = _write_investable_options_contract


# Keep the measured-rate contract visible at this public entrypoint for existing
# static authority tests. FRED:DGS3MO remains the non-Yahoo measured fallback.
# Published provenance fields retained by the resilient path. A recent measured
# rate may be reused with CACHED: provenance; there is no invented fixed fallback.
RISK_FREE_SOURCE_FIELD = "risk_free_rate_source"
RISK_FREE_OBSERVED_DATE_FIELD = "risk_free_rate_observed_date"
RISK_FREE_MAX_AGE_DAYS = _legacy.RISK_FREE_MAX_AGE_DAYS
CACHED_PROVENANCE_PREFIX = "CACHED:"
_rate_from_yahoo_frame = _legacy._rate_from_yahoo_frame
_previous_risk_free_rate = _legacy._previous_risk_free_rate
_fred_risk_free_rate = _legacy._fred_risk_free_rate

# Preserve the existing >=98% READY contract. Narrowing the requested target set
# must not lower the quality threshold or hide missing Option chains.
_resilient.MIN_READY_TARGET_COVERAGE = _resilient.FULL_UNIVERSE_SCAN_READY_COVERAGE


def _risk_free_rate(yf, *, session_date: str, previous: dict):
    original_fred = _legacy._fred_risk_free_rate
    _legacy._fred_risk_free_rate = _fred_risk_free_rate
    try:
        return _legacy._risk_free_rate(yf, session_date=session_date, previous=previous)
    finally:
        _legacy._fred_risk_free_rate = original_fred


# atomic_write_json intentionally rejects NaN/Infinity. If a chain contains Call
# GEX but zero measurable Put GEX, the ratio is undefined rather than infinite.
_original_upward_structure = _resilient._upward_structure


def _json_safe_upward_structure(row: dict) -> dict:
    result = _original_upward_structure(row)
    ratio = result.get("call_put_gex_ratio")
    if isinstance(ratio, (int, float)) and not math.isfinite(float(ratio)):
        result["call_put_gex_ratio"] = None
    return result


_resilient._upward_structure = _json_safe_upward_structure


# A ticker is not considered complete if some 0-45DTE expiries failed only due
# to a transient Yahoo/network condition. Put the whole ticker back through the
# normal retry/cooldown path instead of freezing an incomplete same-session row.
_original_fetch_ticker_snapshot_once = _resilient._fetch_ticker_snapshot_once


def _complete_transient_expiry_snapshot(yf, ticker: str, *, spot: float, session_date: str) -> dict:
    result = _original_fetch_ticker_snapshot_once(
        yf,
        ticker,
        spot=spot,
        session_date=session_date,
    )
    transient_warnings = [
        warning for warning in (result.get("fetch_warnings") or [])
        if _resilient._is_transient_option_error(warning)
    ]
    if transient_warnings:
        raise RuntimeError(
            f"{ticker}: transient partial-expiry option fetch: "
            + "; ".join(transient_warnings)[:500]
        )
    return result


_resilient._fetch_ticker_snapshot_once = _complete_transient_expiry_snapshot


if __name__ == "__main__":
    # Retain --all-universe as the resilient execution-mode token, but the target
    # resolver above now returns only the RS21/63/189 Top50 union.
    if "--all-universe" not in sys.argv:
        sys.argv.append("--all-universe")
    raise SystemExit(main())
