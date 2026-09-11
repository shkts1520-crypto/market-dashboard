from __future__ import annotations

import math
from typing import Any

CALCULATION_VERSION = "v38-tqqq-panic-rules-1.2.0"
BASE_TARGET_PCT = 30
PANIC_TARGET_PCT = 80
SEED_MAX_AGE_SESSIONS = 30
PANIC_MAX_HOLD_SESSIONS = 10
MC57_MIN_TRIGGER = 20.0


class TQQQRuleError(RuntimeError):
    pass


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TQQQRuleError(f"{field} must be finite")
    x = float(value)
    if not math.isfinite(x):
        raise TQQQRuleError(f"{field} must be finite")
    return x


def panic_seed(*, vix_close: float, qqq_sma50_atr_deviation: float, qqq_dd10: float) -> bool:
    return bool(
        _finite(vix_close, "vix_close") >= 23.0
        and _finite(qqq_sma50_atr_deviation, "qqq_sma50_atr_deviation") <= -0.5
        and _finite(qqq_dd10, "qqq_dd10") <= -0.02
    )


def qqq_4h_rsi30_touch(*, prior_rsi14: float, current_rsi14: float) -> bool:
    """Return True only for the first downward touch/cross of RSI14=30.

    The audited Stage56 contract is TOUCH30, not merely "RSI currently <=30".
    Remaining below 30 on subsequent 4H bars must not create a new trigger.
    """
    prior = _finite(prior_rsi14, "prior_rsi14")
    current = _finite(current_rsi14, "current_rsi14")
    return prior > 30.0 and current <= 30.0


def panic_trigger(
    *,
    seed_age_sessions: int | None,
    qqq_4h_rsi14: float,
    prior_qqq_4h_rsi14: float | None = None,
    mc57: float | None,
) -> dict[str, Any]:
    if seed_age_sessions is None:
        return {"status": "OK", "trigger": False, "reason": "NO_ACTIVE_SEED"}
    if isinstance(seed_age_sessions, bool) or not isinstance(seed_age_sessions, int):
        raise TQQQRuleError("seed_age_sessions must be int or None")
    if seed_age_sessions < 0:
        raise TQQQRuleError("seed_age_sessions must be >=0")

    current = _finite(qqq_4h_rsi14, "qqq_4h_rsi14")
    if seed_age_sessions > SEED_MAX_AGE_SESSIONS:
        return {"status": "OK", "trigger": False, "reason": "SEED_EXPIRED"}
    if current > 30.0:
        return {"status": "OK", "trigger": False, "reason": "QQQ_4H_RSI_ABOVE_30"}
    if prior_qqq_4h_rsi14 is None:
        return {
            "status": "DATA_REQUIRED",
            "trigger": None,
            "reason": "PRIOR_QQQ_4H_RSI_REQUIRED_FOR_TOUCH30",
        }

    prior = _finite(prior_qqq_4h_rsi14, "prior_qqq_4h_rsi14")
    if not qqq_4h_rsi30_touch(prior_rsi14=prior, current_rsi14=current):
        return {
            "status": "OK",
            "trigger": False,
            "reason": "NO_NEW_QQQ_4H_RSI30_TOUCH",
        }

    if mc57 is None:
        return {
            "status": "DATA_REQUIRED",
            "trigger": None,
            "reason": "MC57_REQUIRED_FOR_PANIC_TRIGGER",
        }

    m = _finite(mc57, "mc57")
    return {
        "status": "OK",
        "trigger": m >= MC57_MIN_TRIGGER,
        "reason": "TRIGGER_CONFIRMED" if m >= MC57_MIN_TRIGGER else "MC57_BELOW_20",
    }


def panic_position_action(
    *,
    in_panic: bool,
    holding_sessions_completed: int,
    trigger: bool | None,
    mc57: float | None,
) -> dict[str, Any]:
    if not isinstance(in_panic, bool):
        raise TQQQRuleError("in_panic must be bool")
    if trigger is not None and not isinstance(trigger, bool):
        raise TQQQRuleError("trigger must be bool or None")
    if isinstance(holding_sessions_completed, bool) or not isinstance(holding_sessions_completed, int) or holding_sessions_completed < 0:
        raise TQQQRuleError("holding_sessions_completed must be a non-negative int")

    if in_panic and holding_sessions_completed >= PANIC_MAX_HOLD_SESSIONS:
        return {
            "status": "OK",
            "action": "RETURN_TO_30_NEXT_OPEN",
            "target_pct": BASE_TARGET_PCT,
            "reason": "PANIC_MAX_10_SESSIONS",
        }

    if in_panic:
        if mc57 is None:
            return {
                "status": "DATA_REQUIRED",
                "action": None,
                "target_pct": None,
                "reason": "MC57_REQUIRED_FOR_EARLY_EXIT_CHECK",
            }
        m = _finite(mc57, "mc57")
        if m < MC57_MIN_TRIGGER:
            return {
                "status": "OK",
                "action": "RETURN_TO_30_NEXT_OPEN",
                "target_pct": BASE_TARGET_PCT,
                "reason": "MC57_LT_20",
            }
        return {
            "status": "OK",
            "action": "HOLD_80",
            "target_pct": PANIC_TARGET_PCT,
            "reason": "PANIC_ACTIVE",
        }

    if trigger is None:
        return {
            "status": "DATA_REQUIRED",
            "action": None,
            "target_pct": None,
            "reason": "PANIC_TRIGGER_UNRESOLVED",
        }
    if trigger:
        return {
            "status": "OK",
            "action": "RAISE_TO_80_NEXT_OPEN",
            "target_pct": PANIC_TARGET_PCT,
            "reason": "SEED_RSI30_TOUCH_MC57_GE_20",
        }
    return {
        "status": "OK",
        "action": "BASELINE_30",
        "target_pct": BASE_TARGET_PCT,
        "reason": "NO_PANIC_TRIGGER",
    }
