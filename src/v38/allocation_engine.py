from __future__ import annotations

import math
from typing import Any

CALCULATION_VERSION = "v38-allocation-engine-1.0.0"
GROSS_MAX_PCT = 100.0
TQQQ_PROTECTED_MAX_PCT = 80.0
DATA_REQUIRED = "DATA_REQUIRED"
READY = "READY"


class AllocationError(RuntimeError):
    pass


def _pct(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AllocationError(f"{field} must be a finite non-negative number")
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise AllocationError(f"{field} must be a finite non-negative number")
    return x


def allocate_percentages(
    *,
    reset_desired_pct: float,
    tqqq_desired_pct: float,
    normal_stock_desired_pct: float,
) -> dict[str, Any]:
    """Apply the recovered Gross100 sleeve priority at percentage level only.

    Priority is:
      1. RSI30 Panic Reset
      2. TQQQ protected allocation up to 80%
      3. Normal Stock/Core
      4. TQQQ extra above the protected sleeve

    Share selection, rounding, cash residuals and which existing normal-stock lots
    are reduced are intentionally not inferred; those remain DATA_REQUIRED until a
    share-level golden allocation ledger is recovered.
    """
    reset_desired = _pct(reset_desired_pct, "reset_desired_pct")
    tqqq_desired = _pct(tqqq_desired_pct, "tqqq_desired_pct")
    normal_desired = _pct(normal_stock_desired_pct, "normal_stock_desired_pct")

    reset_allocated = min(reset_desired, GROSS_MAX_PCT)
    remaining = GROSS_MAX_PCT - reset_allocated

    tqqq_protected = min(tqqq_desired, TQQQ_PROTECTED_MAX_PCT, remaining)
    remaining -= tqqq_protected

    normal_allocated = min(normal_desired, remaining)
    remaining -= normal_allocated

    tqqq_extra_desired = max(tqqq_desired - tqqq_protected, 0.0)
    tqqq_extra = min(tqqq_extra_desired, remaining)
    remaining -= tqqq_extra

    tqqq_allocated = tqqq_protected + tqqq_extra
    gross = reset_allocated + tqqq_allocated + normal_allocated
    if gross > GROSS_MAX_PCT + 1e-9:
        raise AllocationError("internal gross allocation exceeded 100%")

    return {
        "status": READY,
        "calculation_version": CALCULATION_VERSION,
        "requested": {
            "reset_pct": reset_desired,
            "tqqq_pct": tqqq_desired,
            "normal_stock_pct": normal_desired,
        },
        "allocated": {
            "reset_pct": reset_allocated,
            "tqqq_protected_pct": tqqq_protected,
            "normal_stock_pct": normal_allocated,
            "tqqq_extra_pct": tqqq_extra,
            "tqqq_total_pct": tqqq_allocated,
            "cash_pct": remaining,
            "gross_pct": gross,
        },
        "priority": [
            "RSI30_PANIC_RESET",
            "TQQQ_PROTECTED_UP_TO_80",
            "NORMAL_STOCK",
            "TQQQ_EXTRA",
        ],
        "share_level": {
            "status": DATA_REQUIRED,
            "reason": "SHARE_LEVEL_GOLDEN_ALLOCATION_LEDGER_NOT_RECOVERED",
            "unresolved": [
                "lot_selection",
                "share_rounding",
                "cash_residual_handling",
                "same_open_order_sequence",
            ],
        },
    }
