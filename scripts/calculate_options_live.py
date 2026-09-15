#!/usr/bin/env python3
from __future__ import annotations

import math
import sys

import calculate_options_live_legacy as _legacy
import calculate_options_resilient as _resilient

main = _resilient.main

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
# active-universe acquisition is READY only after the scan contract is >=98% resolved.
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
    # Production no longer pre-filters Options to Core12/RS leaders. Keep the
    # legacy --target-limit argument accepted for compatibility, but default the
    # public entrypoint to the complete active stock universe.
    if "--all-universe" not in sys.argv:
        sys.argv.append("--all-universe")
    raise SystemExit(main())
