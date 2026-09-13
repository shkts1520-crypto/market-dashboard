from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any, Iterable

import numpy as np
import pandas as pd


CALCULATION_VERSION = "v38-vix-fear-cycle-1.0.0"
SCHEMA_VERSION = "v38.vix_fear_cycle.1"
HISTORY_START = "1990-01-01"
CHART_SESSIONS = 2520  # about ten trading years


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalise_daily(frame: pd.DataFrame, *, session_date: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["date", "high", "close"])
    out = frame.copy()
    out.columns = [str(column).strip().lower().replace(" ", "_") for column in out.columns]
    if "high" not in out.columns or "close" not in out.columns:
        return pd.DataFrame(columns=["date", "high", "close"])
    parsed = pd.to_datetime(out.index, errors="coerce", utc=True)
    out = out.loc[parsed.notna()].copy()
    parsed = parsed[parsed.notna()]
    out["date"] = parsed.strftime("%Y-%m-%d")
    out["high"] = pd.to_numeric(out["high"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out[(out["date"] >= HISTORY_START) & (out["date"] <= session_date)]
    out = out.dropna(subset=["high", "close"])
    out = out[(out["high"] > 0) & (out["close"] > 0)]
    out = out.sort_values("date", kind="mergesort").drop_duplicates("date", keep="last")
    return out[["date", "high", "close"]].reset_index(drop=True)


def _lwma(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1, dtype=float)
    denominator = float(weights.sum())
    return series.rolling(window, min_periods=window).apply(
        lambda values: float(np.dot(values, weights) / denominator), raw=True
    )


def _completed_month_highs(daily: pd.DataFrame, *, session_date: str) -> pd.Series:
    if daily.empty:
        return pd.Series(dtype=float)
    session = pd.Timestamp(session_date)
    current_period = session.to_period("M")
    work = daily.copy()
    work["month"] = pd.to_datetime(work["date"]).dt.to_period("M")
    completed = work[work["month"] < current_period]
    if completed.empty:
        return pd.Series(dtype=float)
    return completed.groupby("month", sort=True)["high"].max().astype(float)


def _sigma_thresholds(monthly_highs: pd.Series) -> tuple[float, float, float, float]:
    values = pd.to_numeric(monthly_highs, errors="coerce").dropna()
    values = values[values > 0]
    if len(values) < 24:
        raise ValueError("at least 24 completed monthly VIX highs are required")
    logged = np.log10(values.to_numpy(float))
    mu = float(np.mean(logged))
    sigma = float(np.std(logged, ddof=0))
    plus1 = float(10 ** (mu + sigma))
    plus2 = float(10 ** (mu + 2.0 * sigma))
    return mu, sigma, plus1, plus2


def _marker(day: str, kind: str, value: float | None) -> dict[str, Any]:
    return {"date": day, "kind": kind, "value": value}


def _scan_cycle(daily: pd.DataFrame) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    if daily.empty:
        return "NORMAL", [], []

    state = "NORMAL"
    armed = True
    active: dict[str, Any] | None = None
    completed: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []

    for index, row in daily.iterrows():
        day = str(row["date"])
        high = _finite(row["high"])
        plus1 = _finite(row.get("plus1_sigma"))
        plus2 = _finite(row.get("plus2_sigma"))
        lw5 = _finite(row["lwma5"])
        lw10 = _finite(row["lwma10"])
        previous_lw5 = _finite(daily.iloc[index - 1]["lwma5"]) if index > 0 else None
        previous_lw10 = _finite(daily.iloc[index - 1]["lwma10"]) if index > 0 else None
        if high is None or plus1 is None or plus2 is None:
            continue

        if active is None and high <= plus1:
            armed = True
            state = "NORMAL"

        if active is None and armed and high >= plus2:
            active = {
                "event": day,
                "event_index": int(index),
                "roll": None,
                "bottom": None,
                "peak": high,
                "peak_date": day,
                "re_extreme": [],
            }
            armed = False
            state = "EVENT"
            markers.append(_marker(day, "EVENT", high))
            continue

        if active is None:
            continue

        if high > float(active["peak"]):
            active["peak"] = high
            active["peak_date"] = day

        if active["roll"] is None:
            if lw5 is not None and previous_lw5 is not None and lw5 < previous_lw5:
                active["roll"] = day
                state = "ROLLOVER"
                markers.append(_marker(day, "ROLLOVER", lw5))
        elif active["bottom"] is None:
            crossed = (
                lw5 is not None and lw10 is not None
                and previous_lw5 is not None and previous_lw10 is not None
                and previous_lw5 >= previous_lw10 and lw5 < lw10
            )
            if crossed:
                active["bottom"] = day
                active["bottom_index"] = int(index)
                state = "BOTTOM"
                markers.append(_marker(day, "BOTTOM", lw5))
                completed.append({
                    "event": active["event"],
                    "roll": active["roll"],
                    "bottom": active["bottom"],
                    "days": int(index) - int(active["event_index"]),
                    "peak": float(active["peak"]),
                    "peak_date": active["peak_date"],
                })
        else:
            if high >= plus2:
                prior = active.get("re_extreme") or []
                if not prior or prior[-1] != day:
                    prior.append(day)
                    active["re_extreme"] = prior
                    state = "RE-EXTREME"
                    markers.append(_marker(day, "RE-EXTREME", high))
            if high <= plus1:
                active = None
                armed = True
                state = "NORMAL"

    return state, completed[-10:], markers


def build_vix_fear_cycle(frame: pd.DataFrame, *, session_date: str, generated_at: str) -> dict[str, Any]:
    daily = _normalise_daily(frame, session_date=session_date)
    if daily.empty or str(daily.iloc[-1]["date"]) != session_date:
        return {
            "session_date": session_date,
            "generated_at": generated_at,
            "status": "DATA_REQUIRED",
            "reason": "VIX_DAILY_HISTORY_MISSING_CURRENT_SESSION",
            "source": "Yahoo Finance ^VIX daily High/Close",
            "schema_version": SCHEMA_VERSION,
            "calculation_version": CALCULATION_VERSION,
            "trading_gate_eligible": False,
            "series": [],
            "events": [],
            "markers": [],
        }

    monthly = _completed_month_highs(daily, session_date=session_date)
    try:
        mu, sigma, plus1, plus2 = _sigma_thresholds(monthly)
    except ValueError as exc:
        return {
            "session_date": session_date,
            "generated_at": generated_at,
            "status": "DATA_REQUIRED",
            "reason": str(exc),
            "source": "Yahoo Finance ^VIX daily High/Close",
            "schema_version": SCHEMA_VERSION,
            "calculation_version": CALCULATION_VERSION,
            "trading_gate_eligible": False,
            "series": [],
            "events": [],
            "markers": [],
        }

    daily["lwma5"] = _lwma(daily["high"], 5)
    daily["lwma10"] = _lwma(daily["high"], 10)

    month_highs_all = daily.assign(month=pd.to_datetime(daily["date"]).dt.to_period("M")).groupby("month", sort=True)["high"].max().astype(float)
    threshold_by_month: dict[pd.Period, tuple[float, float]] = {}
    history_values: list[float] = []
    for month, month_high in month_highs_all.items():
        if len(history_values) >= 24:
            logged = np.log10(np.asarray(history_values, dtype=float))
            hist_mu = float(np.mean(logged))
            hist_sigma = float(np.std(logged, ddof=0))
            threshold_by_month[month] = (float(10 ** (hist_mu + hist_sigma)), float(10 ** (hist_mu + 2.0 * hist_sigma)))
        history_values.append(float(month_high))
    periods = pd.to_datetime(daily["date"]).dt.to_period("M")
    daily["plus1_sigma"] = [threshold_by_month.get(period, (None, None))[0] for period in periods]
    daily["plus2_sigma"] = [threshold_by_month.get(period, (None, None))[1] for period in periods]
    current_period = pd.Timestamp(session_date).to_period("M")
    daily.loc[periods == current_period, "plus1_sigma"] = plus1
    daily.loc[periods == current_period, "plus2_sigma"] = plus2
    state, events, markers = _scan_cycle(daily)

    def number(value: Any) -> float | None:
        x = _finite(value)
        return round(x, 6) if x is not None else None

    series = [
        {
            "date": str(row.date),
            "close": number(row.close),
            "high": number(row.high),
            "lwma5": number(row.lwma5),
            "lwma10": number(row.lwma10),
        }
        for row in daily.tail(CHART_SESSIONS).itertuples(index=False)
    ]
    chart_start = series[0]["date"] if series else session_date
    visible_markers = [item for item in markers if str(item.get("date") or "") >= chart_start]
    latest = daily.iloc[-1]
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "status": "READY",
        "reason": "OBSERVATIONAL_PANIC_BOTTOM_SEQUENCE_NOT_TRADING_GATE",
        "source": "Yahoo Finance ^VIX daily High/Close from 1990; completed-month log10 distribution",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "trading_gate_eligible": False,
        "state": state,
        "current": {
            "vix": number(latest["close"]),
            "high": number(latest["high"]),
            "lwma5": number(latest["lwma5"]),
            "lwma10": number(latest["lwma10"]),
            "plus1_sigma": round(plus1, 6),
            "plus2_sigma": round(plus2, 6),
        },
        "distribution": {
            "kind": "log10_completed_month_high",
            "history_start": HISTORY_START,
            "completed_months": int(len(monthly)),
            "mu": round(mu, 9),
            "sigma": round(sigma, 9),
        },
        "rules": {
            "event": "daily High >= +2 sigma",
            "rollover": "after EVENT, LWMA5 declines versus prior session",
            "bottom": "after ROLLOVER, LWMA5 crosses below LWMA10",
            "re_extreme": "after BOTTOM, daily High >= +2 sigma before rearm",
            "rearm": "daily High <= +1 sigma",
        },
        "series": series,
        "events": events,
        "markers": visible_markers,
    }
