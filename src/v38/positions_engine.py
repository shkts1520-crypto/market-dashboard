from __future__ import annotations

import math
from typing import Any

CALCULATION_VERSION = "v38-positions-rules-1.0.0"
INITIAL_STOP_PCT = 0.92
PARTIAL_TRIGGER_PCT = 1.24
PARTIAL_SELL_FRACTION = 0.25
WINNER_TRAIL_PCT = 0.70

class PositionsRuleError(RuntimeError):
    pass


def _positive(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PositionsRuleError(f"{field} must be a finite positive number")
    x = float(value)
    if not math.isfinite(x) or x <= 0:
        raise PositionsRuleError(f"{field} must be a finite positive number")
    return x


def stop_levels(*, entry: float, peak_close: float) -> dict[str, float]:
    e = _positive(entry, "entry")
    p = _positive(peak_close, "peak_close")
    if p < e:
        raise PositionsRuleError("peak_close must be >= entry")
    initial = e * INITIAL_STOP_PCT
    trail = p * WINNER_TRAIL_PCT
    return {
        "initial_stop": initial,
        "winner_trail": trail,
        "final_stop": max(initial, trail),
    }


def normal_stock_next_open_action(
    *,
    entry: float,
    close: float,
    peak_close: float,
    partial_taken: bool,
    nqsar_state: str,
) -> dict[str, Any]:
    e = _positive(entry, "entry")
    c = _positive(close, "close")
    p = _positive(peak_close, "peak_close")
    if p < max(e, c):
        raise PositionsRuleError("peak_close must be >= entry and close")
    if not isinstance(partial_taken, bool):
        raise PositionsRuleError("partial_taken must be bool")
    if nqsar_state not in {"Blue", "Green", "Yellow", "Red"}:
        raise PositionsRuleError("invalid NQSAR state")

    levels = stop_levels(entry=e, peak_close=p)

    if nqsar_state == "Red":
        return {
            "action": "EXIT_ALL_NEXT_OPEN",
            "reason": "NQSAR_RED_PORTFOLIO_EXIT",
            "sell_fraction": 1.0,
            "levels": levels,
        }

    active_stop = levels["final_stop"] if partial_taken else levels["initial_stop"]
    if c <= active_stop:
        return {
            "action": "EXIT_REMAINDER_NEXT_OPEN" if partial_taken else "EXIT_ALL_NEXT_OPEN",
            "reason": "WINNER_TRAIL_OR_INITIAL_STOP" if partial_taken else "INITIAL_STOP_CLOSE",
            "sell_fraction": 1.0,
            "levels": levels,
        }

    if not partial_taken and c >= e * PARTIAL_TRIGGER_PCT:
        return {
            "action": "SELL_25_PCT_NEXT_OPEN",
            "reason": "FIRST_CLOSE_GE_ENTRY_X_1_24",
            "sell_fraction": PARTIAL_SELL_FRACTION,
            "levels": levels,
        }

    return {
        "action": "HOLD",
        "reason": "NO_CONFIRMED_EXIT",
        "sell_fraction": 0.0,
        "levels": levels,
        "yellow_forces_exit": False,
        "breadth_forces_trim": False,
        "rank_decline_exit": False,
        "theme_decline_exit": False,
    }
