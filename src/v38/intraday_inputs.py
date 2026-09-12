from __future__ import annotations

import json
import math
from datetime import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-qqq-intraday-1.0.0"
NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
FOUR_HOUR_SPLIT = time(13, 30)


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


def aggregate_rth_4h_candidate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        try:
            stamp = pd.Timestamp(row["timestamp"])
            clock = stamp.tz_convert(NY).timetz().replace(tzinfo=None) if stamp.tzinfo else stamp.time()
        except Exception:
            continue
        bucket = 0 if clock < FOUR_HOUR_SPLIT else 1
        grouped.setdefault((str(row["date"]), bucket), []).append(row)

    output: list[dict[str, Any]] = []
    for (day, bucket), chunk in sorted(grouped.items()):
        chunk = sorted(chunk, key=lambda row: row["timestamp"])
        if len(chunk) < 2:
            continue
        opens = [_finite(row.get("open")) for row in chunk]
        highs = [_finite(row.get("high")) for row in chunk]
        lows = [_finite(row.get("low")) for row in chunk]
        closes = [_finite(row.get("close")) for row in chunk]
        volumes = [_finite(row.get("volume")) for row in chunk]
        if any(value is None for value in (opens[0], closes[-1])) or not all(value is not None for value in highs + lows):
            continue
        output.append({
            "timestamp": chunk[0]["timestamp"],
            "date": day,
            "bucket": "09:30-13:30" if bucket == 0 else "13:30-16:00",
            "open": opens[0],
            "high": max(float(value) for value in highs if value is not None),
            "low": min(float(value) for value in lows if value is not None),
            "close": closes[-1],
            "volume": sum(float(value) for value in volumes if value is not None),
            "source_bar_count": len(chunk),
        })
    return output


def _wilder_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    if not closes:
        return []
    series = pd.Series(closes, dtype=float)
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    avg_up = up.ewm(alpha=1 / period, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / period, adjust=False).mean()
    values: list[float | None] = []
    for gain, loss in zip(avg_up, avg_down):
        if pd.isna(gain) or pd.isna(loss):
            values.append(None)
        elif float(loss) == 0.0 and float(gain) > 0.0:
            values.append(100.0)
        elif float(gain) == 0.0 and float(loss) == 0.0:
            values.append(50.0)
        elif float(loss) == 0.0:
            values.append(100.0)
        else:
            rs = float(gain) / float(loss)
            value = 100.0 - 100.0 / (1.0 + rs)
            values.append(value if math.isfinite(value) else None)
    return values


def add_candidate_rsi(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closes = [float(row["close"]) for row in rows if _finite(row.get("close")) is not None]
    if len(closes) != len(rows):
        return [dict(row) for row in rows]
    rsi = _wilder_rsi(closes)
    return [{**row, "rsi14": rsi[index]} for index, row in enumerate(rows)]


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
    candidate = add_candidate_rsi(aggregate_rth_4h_candidate(hourly))
    latest_for_session = [row for row in candidate if row.get("date") == target_session]
    enough_rsi = [row for row in candidate if _finite(row.get("rsi14")) is not None]
    current_rsi = _finite(enough_rsi[-1].get("rsi14")) if enough_rsi else None
    prior_rsi = _finite(enough_rsi[-2].get("rsi14")) if len(enough_rsi) >= 2 else None

    obj["qqq_intraday_60m"] = hourly
    obj["qqq_4h_candidate"] = candidate
    obj["qqq_4h_status"] = "READY_DISPLAY_ONLY" if hourly and latest_for_session and current_rsi is not None else "DATA_REQUIRED"
    obj["qqq_4h_reason"] = (
        "RTH_60M_AGGREGATED_PENDING_STAGE56_4H_FIXTURE"
        if obj["qqq_4h_status"] == "READY_DISPLAY_ONLY"
        else "QQQ_INTRADAY_60M_INCOMPLETE"
    )
    obj["qqq_4h_trading_gate_eligible"] = False
    obj["qqq_4h_source"] = "Yahoo Finance QQQ 60m RTH; 09:30/13:30 candidate aggregation"
    obj["qqq_4h_calculation_version"] = CALCULATION_VERSION
    obj["qqq_4h_generated_at"] = generated_at
    obj["qqq_4h_latest"] = {
        "prior_rsi14": prior_rsi,
        "current_rsi14": current_rsi,
        "touch30_candidate": bool(prior_rsi is not None and current_rsi is not None and prior_rsi > 30.0 and current_rsi <= 30.0),
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
