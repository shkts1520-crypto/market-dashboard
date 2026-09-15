#!/usr/bin/env python3
from __future__ import annotations

import calculate_options_live_legacy as _legacy
from calculate_options_resilient import main

# Keep the measured-rate contract visible at this public entrypoint for existing
# static authority tests. FRED:DGS3MO remains the non-Yahoo measured fallback.
_rate_from_yahoo_frame = _legacy._rate_from_yahoo_frame
_previous_risk_free_rate = _legacy._previous_risk_free_rate
_fred_risk_free_rate = _legacy._fred_risk_free_rate


def _risk_free_rate(yf, *, session_date: str, previous: dict):
    original_fred = _legacy._fred_risk_free_rate
    _legacy._fred_risk_free_rate = _fred_risk_free_rate
    try:
        return _legacy._risk_free_rate(yf, session_date=session_date, previous=previous)
    finally:
        _legacy._fred_risk_free_rate = original_fred


if __name__ == "__main__":
    raise SystemExit(main())
