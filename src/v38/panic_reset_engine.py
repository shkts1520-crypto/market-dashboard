from __future__ import annotations

import math
from typing import Any

CALCULATION_VERSION = "v38-panic-reset-rules-1.0.0"
POSITION_PCT = 2.9
MAX_TOTAL_SLOTS = 4
MAX_SAME_THEME_SLOTS = 2
HOLD_SESSIONS = 20
COOLDOWN_SESSIONS = 20

class PanicResetRuleError(RuntimeError):
    pass


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PanicResetRuleError(f"{field} must be finite")
    x = float(value)
    if not math.isfinite(x):
        raise PanicResetRuleError(f"{field} must be finite")
    return x


def activation(*, theme_rs_pct: float, rank_improvement_20d: float, theme_above_ema21_pct: float) -> bool:
    return bool(
        _finite(theme_rs_pct, "theme_rs_pct") >= 80.0
        and _finite(rank_improvement_20d, "rank_improvement_20d") >= 15.0
        and _finite(theme_above_ema21_pct, "theme_above_ema21_pct") >= 60.0
    )


def entry_signal(
    *,
    activation_ok: bool,
    rsi30_touched_within_20: bool,
    first_rsi_up_day_after_touch: bool,
    theme_rs63_rank: int,
) -> bool:
    if not all(isinstance(x, bool) for x in (activation_ok, rsi30_touched_within_20, first_rsi_up_day_after_touch)):
        raise PanicResetRuleError("signal flags must be bool")
    if isinstance(theme_rs63_rank, bool) or not isinstance(theme_rs63_rank, int) or theme_rs63_rank < 1:
        raise PanicResetRuleError("theme_rs63_rank must be a positive int")
    return bool(
        activation_ok
        and rsi30_touched_within_20
        and first_rsi_up_day_after_touch
        and theme_rs63_rank <= 3
    )


def admission(
    *,
    signal: bool,
    current_total_slots: int,
    current_same_theme_slots: int,
    sessions_since_exit: int | None,
) -> dict[str, Any]:
    if not isinstance(signal, bool):
        raise PanicResetRuleError("signal must be bool")
    for field, value in (
        ("current_total_slots", current_total_slots),
        ("current_same_theme_slots", current_same_theme_slots),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PanicResetRuleError(f"{field} must be a non-negative int")
    if sessions_since_exit is not None and (
        isinstance(sessions_since_exit, bool)
        or not isinstance(sessions_since_exit, int)
        or sessions_since_exit < 0
    ):
        raise PanicResetRuleError("sessions_since_exit must be non-negative int or None")

    if not signal:
        return {"admit": False, "reason": "NO_ENTRY_SIGNAL", "position_pct": 0.0}
    if current_total_slots >= MAX_TOTAL_SLOTS:
        return {"admit": False, "reason": "TOTAL_SLOT_CAP", "position_pct": 0.0}
    if current_same_theme_slots >= MAX_SAME_THEME_SLOTS:
        return {"admit": False, "reason": "SAME_THEME_SLOT_CAP", "position_pct": 0.0}
    if sessions_since_exit is not None and sessions_since_exit < COOLDOWN_SESSIONS:
        return {"admit": False, "reason": "COOLDOWN_20_SESSIONS", "position_pct": 0.0}
    return {"admit": True, "reason": "PANIC_RESET_ENTRY_NEXT_OPEN", "position_pct": POSITION_PCT}


def holding_action(*, holding_sessions_completed: int) -> dict[str, Any]:
    if isinstance(holding_sessions_completed, bool) or not isinstance(holding_sessions_completed, int) or holding_sessions_completed < 0:
        raise PanicResetRuleError("holding_sessions_completed must be non-negative int")
    if holding_sessions_completed >= HOLD_SESSIONS:
        return {"action": "EXIT_NEXT_OPEN", "reason": "FIXED_20_SESSION_HOLD"}
    return {
        "action": "HOLD",
        "reason": "FIXED_HOLD_ACTIVE",
        "initial_stop_enabled": False,
        "averaging_enabled": False,
    }
