from __future__ import annotations

import json
import math
from datetime import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-qqq-intraday-1.1.0"
NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
FOUR_HOUR_SPLIT = time(13, 30)
EXPECTED_BUCKET_STARTS = {
    0: (time(9, 30), time(10, 30), time(11, 30), time(12, 30)),
    1: (time(13, 30), time(14, 30), time(15, 30)),
}
QQQ_4H_DEFINITION = {
    "instrument": "QQQ",
    "timezone": "America/New_York",
    "session": "RTH_ONLY",
    "session_open": "09:30",
    "session_close": "16:00",
    "extended_hours": False,
    "anchor": "09:30",
    "bars": [
        {"bucket": "09:30-13:30", "kind": "FULL_4H", "source_60m_bars": 4},
        {"bucket": "13:30-16:00", "kind": "SESSION_TAIL", "source_60m_bars": 3},
    ],
    "rsi": "WILDER_RSI14",
    "trigger": "prior RSI14 > 30 AND current RSI14 <= 30",
    "completion_policy": "COMPLETED_STANDARD_RTH_BARS_ONLY",
    "nonstandard_session_policy": "FAIL_CLOSED",
}


class IntradayInputError(RuntimeError):
    pass


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [str(col).strip().lower().replace(" ", "_") for col in out.columns]
    return out


def normalise_qqq_60m(frame: pd.DataFrame, *, target_session: str) -> list[dict[str, Any]]:
    """Normalize Yahoo QQQ 60m bars to New York RTH only.

    The production job runs after the completed-session cutoff, so no unfinished
    current-session bar is allowed into the canonical 4H series.
    """
    if frame is None or frame.empty:
        return []
    f = _normalise_columns(frame)
    if not {"open", "high", "low", "close", "volume"}.issubset(f.columns):
        return []
    index = pd.DatetimeIndex(f.index)
    if index.tz is None:
        index = index.tz_localize(NY)
    else:
        index = index.tz_convert(NY)
    f = f.copy()
    f.index = index
    rows: list[dict[str, Any]] = []
    for stamp, raw in f.iterrows():
        day = stamp.strftime("%Y-%m-%d")
        clock = stamp.timetz().replace(tzinfo=None)
        if day > target_session or clock < RTH_OPEN or clock >= RTH_CLOSE:
            continue
        values = {key: _finite(raw.get(key)) for key in ("open", "high", "low", "close", "volume")}
        if any(values[key] is None for key in ("open", "high", "low", "close")):
            continue
        rows.append({
            "timestamp": stamp.isoformat(),
            "date": day,
            "open": values["open"],
            "high": values["high"],
            "low": values["low"],
            "close": values["close"],
            "volume": values["volume"],
        })
    rows.sort(key=lambda row: row["timestamp"])
    return rows


def aggregate_rth_4h(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the adopted V38 QQQ RTH 4H series.

    A normal 6.5-hour cash session necessarily produces one full four-hour bar
    (09:30-13:30) and one session-tail bar (13:30-16:00).  We require the exact
    standard 60m starts in each bucket.  Early-close or otherwise incomplete
    sessions are retained as diagnostics but are not trading-gate eligible.
    """
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        try:
            stamp = pd.Timestamp(row["timestamp"])
            if stamp.tzinfo is not None:
                stamp = stamp.tz_convert(NY)
            clock = stamp.timetz().replace(tzinfo=None)
        except Exception:
            continue
        bucket = 0 if clock < FOUR_HOUR_SPLIT else 1
        grouped.setdefault((str(row["date"]), bucket), []).append(row)

    output: list[dict[str, Any]] = []
    for (day, bucket), chunk in sorted(grouped.items()):
        chunk = sorted(chunk, key=lambda row: row["timestamp"])
        if not chunk:
            continue
        opens = [_finite(row.get("open")) for row in chunk]
        highs = [_finite(row.get("high")) for row in chunk]
        lows = [_finite(row.get("low")) for row in chunk]
        closes = [_finite(row.get("close")) for row in chunk]
        volumes = [_finite(row.get("volume")) for row in chunk]
        if any(value is None for value in (opens[0], closes[-1])) or not all(value is not None for value in highs + lows):
            continue

        starts: list[time] = []
        for row in chunk:
            try:
                stamp = pd.Timestamp(row["timestamp"])
                if stamp.tzinfo is not None:
                    stamp = stamp.tz_convert(NY)
                starts.append(stamp.timetz().replace(tzinfo=None))
            except Exception:
                starts = []
                break
        expected = list(EXPECTED_BUCKET_STARTS[bucket])
        complete = starts == expected
        output.append({
            "timestamp": chunk[0]["timestamp"],
            "date": day,
            "bucket": "09:30-13:30" if bucket == 0 else "13:30-16:00",
            "bar_kind": "FULL_4H" if bucket == 0 else "SESSION_TAIL",
            "open": opens[0],
            "high": max(float(value) for value in highs if value is not None),
            "low": min(float(value) for value in lows if value is not None),
            "close": closes[-1],
            "volume": sum(float(value) for value in volumes if value is not None),
            "source_bar_count": len(chunk),
            "expected_source_bar_count": len(expected),
            "complete": complete,
        })
    return output


# Backward-compatible name used by the first recovery pass.  It now delegates to
# the adopted canonical bar construction rather than a provisional definition.
def aggregate_rth_4h_candidate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return aggregate_rth_4h(rows)


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_gain == 0.0 and avg_loss == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    if avg_gain == 0.0:
        return 0.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _wilder_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Textbook Wilder RSI with SMA seed, then Wilder recursive smoothing."""
    if period <= 0:
        raise IntradayInputError("RSI period must be positive")
    values: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return values

    deltas = [float(closes[index]) - float(closes[index - 1]) for index in range(1, len(closes))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    values[period] = _rsi_value(avg_gain, avg_loss)

    for close_index in range(period + 1, len(closes)):
        delta_index = close_index - 1
        avg_gain = ((period - 1) * avg_gain + gains[delta_index]) / period
        avg_loss = ((period - 1) * avg_loss + losses[delta_index]) / period
        values[close_index] = _rsi_value(avg_gain, avg_loss)
    return values


def add_wilder_rsi(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closes = [float(row["close"]) for row in rows if _finite(row.get("close")) is not None]
    if len(closes) != len(rows):
        return [{**row, "rsi14": None} for row in rows]
    rsi = _wilder_rsi(closes)
    return [{**row, "rsi14": rsi[index]} for index, row in enumerate(rows)]


def add_candidate_rsi(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return add_wilder_rsi(rows)


def patch_market_inputs_with_qqq_intraday(
    market_inputs_path: str | Path,
    *,
    frame: pd.DataFrame,
    target_session: str,
    generated_at: str,
) -> dict[str, Any]:
    path = Path(market_inputs_path)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise IntradayInputError("market_inputs.json is invalid") from exc
    if not isinstance(obj, dict) or obj.get("session_date") != target_session:
        raise IntradayInputError("market_inputs session mismatch")

    hourly = normalise_qqq_60m(frame, target_session=target_session)
    aggregated = aggregate_rth_4h(hourly)
    canonical = add_wilder_rsi([row for row in aggregated if row.get("complete") is True])
    rejected = [row for row in aggregated if row.get("complete") is not True]
    target_rows = [row for row in canonical if row.get("date") == target_session]
    target_complete = (
        len(target_rows) == 2
        and [row.get("bucket") for row in target_rows] == ["09:30-13:30", "13:30-16:00"]
    )

    current_row = canonical[-1] if canonical and canonical[-1].get("date") == target_session else None
    prior_row = canonical[-2] if current_row is not None and len(canonical) >= 2 else None
    current_rsi = _finite(current_row.get("rsi14")) if current_row else None
    prior_rsi = _finite(prior_row.get("rsi14")) if prior_row else None
    gate_ready = bool(target_complete and current_rsi is not None and prior_rsi is not None)
    touch30 = bool(gate_ready and prior_rsi > 30.0 and current_rsi <= 30.0)

    obj["qqq_intraday_60m"] = hourly
    obj["qqq_4h"] = canonical
    # Keep the old key for one compatibility cycle.  Values are now canonical.
    obj["qqq_4h_candidate"] = canonical
    obj["qqq_4h_rejected_partial_count"] = len(rejected)
    obj["qqq_4h_status"] = "READY" if gate_ready else "DATA_REQUIRED"
    obj["qqq_4h_reason"] = "V38_CANONICAL_RTH_4H" if gate_ready else "QQQ_CANONICAL_4H_INCOMPLETE"
    obj["qqq_4h_trading_gate_eligible"] = gate_ready
    obj["qqq_4h_source"] = (
        "V38 canonical QQQ RTH 4H from Yahoo Finance 60m: "
        "09:30-13:30 full bar + 13:30-16:00 session-tail; extended hours excluded"
    )
    obj["qqq_4h_definition"] = dict(QQQ_4H_DEFINITION)
    obj["qqq_4h_calculation_version"] = CALCULATION_VERSION
    obj["qqq_4h_generated_at"] = generated_at
    obj["qqq_4h_latest"] = {
        "prior_rsi14": prior_rsi,
        "current_rsi14": current_rsi,
        "touch30": touch30,
        "touch30_candidate": touch30,
        "current_bucket": current_row.get("bucket") if current_row else None,
    }
    atomic_write_json(path, obj)
    return obj


def fetch_and_patch_qqq_intraday(
    market_inputs_path: str | Path,
    *,
    target_session: str,
    generated_at: str,
) -> dict[str, Any]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise IntradayInputError("yfinance is required") from exc
    try:
        frame = yf.Ticker("QQQ").history(
            period="60d",
            interval="60m",
            auto_adjust=False,
            actions=False,
            prepost=False,
        )
    except Exception as exc:
        raise IntradayInputError(f"QQQ 60m fetch failed: {exc}") from exc
    return patch_market_inputs_with_qqq_intraday(
        market_inputs_path,
        frame=frame,
        target_session=target_session,
        generated_at=generated_at,
    )
