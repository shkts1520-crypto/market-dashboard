#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import calculate_options_live_legacy as _legacy
import calculate_options_resilient as _resilient

main = _resilient.main

# Options acquisition is deliberately narrower than the upstream active stock
# universe. The stock universe already enforces market cap >= $200M in
# v38.live_acquisition; Options additionally require a current price >= $5.
# This keeps the expensive chain scan focused on the investable price floor
# without changing the stock universe, V38 eligibility/ranking, or UI logic.
OPTIONS_MIN_PRICE_USD = 5.0
UPSTREAM_MIN_MARKET_CAP_USD = 200_000_000.0


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _investable_options_targets(rs: dict) -> list[str]:
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


# Keep the existing --all-universe execution path for compatibility, but define
# its Options target set as every ticker in the upstream active universe that
# satisfies the $5 price floor. There is still no Core12/RS rank pre-filter.
_resilient._all_universe_targets = _investable_options_targets


# Keep the target contract truthful while retaining the legacy status/mode token
# expected by the existing production workflow. Reject a stale same-session
# preserved file if its target list is from the old unfiltered universe.
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
                expected = _investable_options_targets(rs)
                actual = sorted({
                    str(ticker or "").strip().upper()
                    for ticker in (policy.get("targets") or [])
                    if str(ticker or "").strip()
                })
                if actual != expected:
                    raise RuntimeError(
                        "refusing stale Options target contract: expected "
                        f"{len(expected)} price>=$5 targets, got {len(actual)}"
                    )
            policy["scope"] = "INVESTABLE_PRICE_FILTERED"
            policy["method"] = (
                "Every current active-universe ticker with current price >= $5; "
                "the upstream TradingView universe already enforces market cap >= $200M; "
                "no Core12/RS pre-filter"
            )
            policy["min_price_usd"] = OPTIONS_MIN_PRICE_USD
            policy["upstream_min_market_cap_usd"] = UPSTREAM_MIN_MARKET_CAP_USD
            overlay = payload.get("chart_overlay_contract")
            if isinstance(overlay, dict):
                overlay["target_priority"] = "FULL_INVESTABLE_UNIVERSE"
            scan = payload.get("universe_scan")
            if isinstance(scan, dict):
                scan["scope"] = "INVESTABLE_PRICE_FILTERED"
                scan["min_price_usd"] = OPTIONS_MIN_PRICE_USD
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

# The former 25% readiness floor belonged to the small priority universe. Full
# investable-universe acquisition is READY only after the scan contract is >=98% resolved.
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
    # Production scans the complete investable Options universe: upstream market
    # cap >= $200M plus current price >= $5. Keep --target-limit accepted for
    # compatibility and continue using the all-universe execution path.
    if "--all-universe" not in sys.argv:
        sys.argv.append("--all-universe")
    raise SystemExit(main())
