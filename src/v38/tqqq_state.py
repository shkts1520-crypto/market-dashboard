from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json
from .tqqq_engine import panic_position_action, panic_seed, panic_trigger

CALCULATION_VERSION = "v38-tqqq-panic-state-1.0.1"
SCHEMA_VERSION = "v38.tqqq_panic_state.1"
BASE_TARGET_PCT = 30
PANIC_TARGET_PCT = 80
SEED_MAX_AGE_SESSIONS = 30
PERSISTED_HISTORY_NAME = "tqqq_panic_state.json"


class TQQQPanicStateError(RuntimeError):
    pass


def _load(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _series(market_inputs: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    raw = market_inputs.get("series")
    rows = raw.get(symbol) if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str):
            continue
        close = _finite(row.get("close"))
        if close is None:
            continue
        item = dict(row)
        item["close"] = close
        out.append(item)
    out.sort(key=lambda row: row["date"])
    return out


def _true_range(row: dict[str, Any], prior_close: float | None) -> float | None:
    high = _finite(row.get("high"))
    low = _finite(row.get("low"))
    if high is None or low is None or high < low:
        return None
    if prior_close is None:
        return high - low
    return max(high - low, abs(high - prior_close), abs(low - prior_close))


def _wilder_atr14(rows: list[dict[str, Any]]) -> float | None:
    if len(rows) < 15:
        return None
    trs: list[float] = []
    prior: float | None = None
    for row in rows:
        tr = _true_range(row, prior)
        close = _finite(row.get("close"))
        if tr is None or close is None:
            return None
        trs.append(tr)
        prior = close
    if len(trs) < 14:
        return None
    atr = sum(trs[:14]) / 14.0
    for tr in trs[14:]:
        atr = ((13.0 * atr) + tr) / 14.0
    return atr if math.isfinite(atr) and atr > 0 else None


def _seed_inputs(market_inputs: dict[str, Any], session: str) -> dict[str, Any]:
    qqq = [row for row in _series(market_inputs, "QQQ") if row["date"] <= session]
    vix = [row for row in _series(market_inputs, "^VIX") if row["date"] <= session]
    if not qqq or not vix or qqq[-1]["date"] != session or vix[-1]["date"] != session:
        return {"status": "DATA_REQUIRED", "reason": "QQQ_OR_VIX_CURRENT_SESSION_MISSING"}
    closes = [float(row["close"]) for row in qqq]
    if len(closes) < 50:
        return {"status": "DATA_REQUIRED", "reason": "QQQ_SMA50_HISTORY_MISSING"}
    sma50 = sum(closes[-50:]) / 50.0
    atr14 = _wilder_atr14(qqq)
    if atr14 is None:
        return {"status": "DATA_REQUIRED", "reason": "QQQ_ATR14_HISTORY_MISSING"}
    close = closes[-1]
    deviation_atr = (close - sma50) / atr14
    peak10 = max(closes[-10:]) if len(closes) >= 10 else None
    dd10 = close / peak10 - 1.0 if peak10 and peak10 > 0 else None
    vix_close = _finite(vix[-1].get("close"))
    if dd10 is None or vix_close is None:
        return {"status": "DATA_REQUIRED", "reason": "PANIC_SEED_INPUT_MISSING"}
    active = panic_seed(
        vix_close=vix_close,
        qqq_sma50_atr_deviation=deviation_atr,
        qqq_dd10=dd10,
    )
    return {
        "status": "READY",
        "reason": "CURRENT_SESSION",
        "vix_close": vix_close,
        "qqq_close": close,
        "qqq_sma50": sma50,
        "qqq_atr14": atr14,
        "qqq_sma50_atr_deviation": deviation_atr,
        "qqq_dd10": dd10,
        "condition": bool(active),
    }


def _session_age(qqq_rows: list[dict[str, Any]], seed_session: str | None, session: str) -> int | None:
    if not seed_session:
        return None
    dates = [row["date"] for row in qqq_rows if seed_session <= row["date"] <= session]
    if not dates or dates[0] != seed_session or dates[-1] != session:
        return None
    return max(0, len(dates) - 1)


def _rolled_position(prior: dict[str, Any], session: str) -> tuple[bool, int, str | None]:
    prior_session = str(prior.get("session_date") or "")
    in_panic = bool(prior.get("panic_active"))
    holding = int(prior.get("holding_sessions_completed") or 0)
    entry_session = prior.get("panic_entry_session") if isinstance(prior.get("panic_entry_session"), str) else None
    if not prior_session or prior_session >= session:
        return in_panic, holding, entry_session
    pending = str(prior.get("action_next_open") or "")
    if pending == "RAISE_TO_80_NEXT_OPEN":
        return True, 1, session
    if pending == "RETURN_TO_30_NEXT_OPEN":
        return False, 0, None
    if in_panic:
        return True, holding + 1, entry_session or session
    return False, 0, None


def build_tqqq_panic_state(
    *,
    market_inputs: dict[str, Any],
    mc57: dict[str, Any],
    prior_state: dict[str, Any] | None,
    session_date: str,
    generated_at: str,
) -> dict[str, Any]:
    prior = prior_state if isinstance(prior_state, dict) else {}
    if market_inputs.get("session_date") != session_date:
        raise TQQQPanicStateError("market_inputs session mismatch")
    if mc57.get("session_date") != session_date:
        raise TQQQPanicStateError("mc57 session mismatch")

    qqq_rows = [row for row in _series(market_inputs, "QQQ") if row["date"] <= session_date]
    seed_inputs = _seed_inputs(market_inputs, session_date)
    in_panic, holding, entry_session = _rolled_position(prior, session_date)
    prior_same_session = str(prior.get("session_date") or "") == session_date

    current_seed_condition = bool(seed_inputs.get("condition")) if seed_inputs.get("status") == "READY" else False
    prior_seed_condition = bool(prior.get("seed_condition"))
    seed_session = prior.get("seed_session") if isinstance(prior.get("seed_session"), str) else None
    seed_consumed = bool(prior.get("seed_consumed"))

    if prior_same_session:
        seed_session = prior.get("seed_session") if isinstance(prior.get("seed_session"), str) else seed_session
        seed_consumed = bool(prior.get("seed_consumed"))
    elif in_panic:
        seed_session = None
        seed_consumed = True
    else:
        # A seed is an event, not a condition that refreshes every day. A new
        # window begins only on a false->true transition of the combined seed.
        if current_seed_condition and not prior_seed_condition:
            seed_session = session_date
            seed_consumed = False
        elif not current_seed_condition:
            seed_consumed = False

    seed_age = _session_age(qqq_rows, seed_session, session_date)
    if seed_age is not None and seed_age > SEED_MAX_AGE_SESSIONS:
        seed_session = None
        seed_age = None
        seed_consumed = False

    seed_active = bool(seed_session and seed_age is not None and not seed_consumed and not in_panic)
    latest = market_inputs.get("qqq_4h_latest") if isinstance(market_inputs.get("qqq_4h_latest"), dict) else {}
    current_rsi = _finite(latest.get("current_rsi14"))
    prior_rsi = _finite(latest.get("prior_rsi14"))
    mc57_value = _finite(mc57.get("mc57"))

    trigger_result: dict[str, Any]
    if not seed_active:
        trigger_result = {"status": "OK", "trigger": False, "reason": "NO_ACTIVE_SEED"}
    elif market_inputs.get("qqq_4h_trading_gate_eligible") is not True or current_rsi is None:
        trigger_result = {"status": "DATA_REQUIRED", "trigger": None, "reason": "QQQ_4H_CANONICAL_INPUT_NOT_READY"}
    else:
        trigger_result = panic_trigger(
            seed_age_sessions=seed_age,
            qqq_4h_rsi14=current_rsi,
            prior_qqq_4h_rsi14=prior_rsi,
            mc57=mc57_value,
        )

    action = panic_position_action(
        in_panic=in_panic,
        holding_sessions_completed=holding,
        trigger=trigger_result.get("trigger"),
        mc57=mc57_value,
    )

    if prior_same_session and action.get("action") in {None, "BASELINE_30"}:
        pending = prior.get("action_next_open")
        if pending in {"RAISE_TO_80_NEXT_OPEN", "RETURN_TO_30_NEXT_OPEN"}:
            action = {"status": "READY", "action": pending,
                      "target_pct": 80 if pending.startswith("RAISE") else 30,
                      "reason": "PRESERVED_SAME_SESSION_PENDING_ACTION"}

    if trigger_result.get("trigger") is True:
        seed_consumed = True
        seed_active = False
    current_target = PANIC_TARGET_PCT if in_panic else BASE_TARGET_PCT
    next_target = action.get("target_pct") if isinstance(action, dict) else None
    status = "READY"
    reason = "CURRENT_SESSION"
    if seed_inputs.get("status") != "READY":
        status = "DATA_REQUIRED"
        reason = str(seed_inputs.get("reason") or "PANIC_SEED_INPUT_NOT_READY")
    elif action.get("status") == "DATA_REQUIRED":
        status = "DATA_REQUIRED"
        reason = str(action.get("reason") or "PANIC_ACTION_UNRESOLVED")
    elif trigger_result.get("status") == "DATA_REQUIRED":
        status = "DATA_REQUIRED"
        reason = str(trigger_result.get("reason") or "PANIC_TRIGGER_UNRESOLVED")

    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": 1.0 if status == "READY" else None,
        "source": "derived:QQQ daily + VIX daily + canonical QQQ RTH 4H RSI14 + MC57; persistent state machine",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": status,
        "reason": reason,
        "seed_condition": current_seed_condition,
        "seed_active": seed_active,
        "seed_session": seed_session,
        "seed_age_sessions": seed_age,
        "seed_consumed": seed_consumed,
        "seed_inputs": seed_inputs,
        "qqq_4h": {
            "status": market_inputs.get("qqq_4h_status"),
            "trading_gate_eligible": bool(market_inputs.get("qqq_4h_trading_gate_eligible")),
            "prior_rsi14": prior_rsi,
            "current_rsi14": current_rsi,
            "touch30": bool(latest.get("touch30")) if latest else False,
        },
        "trigger": trigger_result,
        "panic_active": in_panic,
        "panic_entry_session": entry_session,
        "holding_sessions_completed": holding,
        "current_target_pct": current_target,
        "action_next_open": action.get("action"),
        "target_pct_next_open": next_target,
        "action_reason": action.get("reason"),
        "mc57": mc57_value,
        "normal_tqqq_pct": BASE_TARGET_PCT,
        "panic_tqqq_pct": PANIC_TARGET_PCT,
        "rules": {
            "seed": "VIX Close>=23 AND (QQQ Close-SMA50)/WilderATR14<=-0.5 AND QQQ Close/10-session max Close-1<=-2%",
            "seed_event": "false->true transition; consecutive qualifying sessions do not refresh the 30-session window",
            "seed_max_age_sessions": 30,
            "trigger": "first canonical QQQ RTH 4H RSI14 cross >30 to <=30 while seed active AND MC57>=20",
            "entry": "30% -> 80% next open",
            "max_hold_sessions": 10,
            "early_exit": "MC57<20 -> 80% -> 30% next open",
            "nqsar_hard_gate": False,
        },
    }


def materialize_tqqq_panic_state(
    data_dir: str | Path,
    *,
    session_date: str,
    generated_at: str,
) -> Path:
    root = Path(data_dir)
    market_inputs = _load(root / "market_inputs.json")
    mc57 = _load(root / "mc57.json")
    prior = _load(root / "tqqq_panic.json")
    if not prior:
        prior = _load(root / "history" / PERSISTED_HISTORY_NAME)
    out = build_tqqq_panic_state(
        market_inputs=market_inputs,
        mc57=mc57,
        prior_state=prior,
        session_date=session_date,
        generated_at=generated_at,
    )
    live_path = atomic_write_json(root / "tqqq_panic.json", out)
    # data/history is already an atomic production-commit path. Persist a canonical
    # copy there so the next Actions run always resumes the prior state even though
    # the root shard is an ephemeral runtime artifact.
    atomic_write_json(root / "history" / PERSISTED_HISTORY_NAME, out)
    return live_path
