from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

CALCULATION_VERSION = "v38-vwap-restore-1.0.0"
SCHEMA_VERSION = "v38.vwap_restore.1"


def finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    out = frame.copy()
    if isinstance(out.columns, pd.MultiIndex):
        raise ValueError("normalize_ohlcv expects a single-symbol frame")
    out.columns = [str(column).strip().lower().replace(" ", "_") for column in out.columns]
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(out.columns):
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    out = out.reset_index()
    date_column = next((c for c in out.columns if c in {"date", "datetime", "index"}), out.columns[0])
    parsed = pd.to_datetime(out[date_column], errors="coerce", utc=True)
    out["date"] = parsed.dt.strftime("%Y-%m-%d")
    for column in required:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["date", "high", "low", "close", "volume"])
    out = out[(out["high"] > 0) & (out["low"] > 0) & (out["close"] > 0) & (out["volume"] >= 0)]
    out = out.sort_values("date", kind="mergesort").drop_duplicates("date", keep="last")
    return out[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def add_vwap_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if out.empty:
        return out
    source = (out["high"] + out["low"] + out["close"]) / 3.0
    pv = source * out["volume"]
    for length in (63, 252):
        volume_sum = out["volume"].rolling(length, min_periods=length).sum()
        pv_sum = pv.rolling(length, min_periods=length).sum()
        out[f"vwap{length}"] = pv_sum / volume_sum.replace(0, np.nan)
    previous_close = out["close"].shift(1)
    true_range = pd.concat([
        out["high"] - out["low"],
        (out["high"] - previous_close).abs(),
        (out["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    out["atr14"] = true_range.ewm(alpha=1 / 14.0, adjust=False, min_periods=14).mean()
    return out


def classify_vwap(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    if frame is None or len(frame) < 2 or column not in frame.columns:
        return {"value": None, "dist": None, "break": False, "touch": False, "near": False, "label": "対象外"}
    current = frame.iloc[-1]
    previous = frame.iloc[-2]
    value = finite(current.get(column))
    previous_value = finite(previous.get(column))
    close = finite(current.get("close"))
    previous_close = finite(previous.get("close"))
    low = finite(current.get("low"))
    atr = finite(current.get("atr14"))
    if value is None or close is None:
        return {"value": None, "dist": None, "break": False, "touch": False, "near": False, "label": "対象外"}
    dist = close / value - 1.0 if value > 0 else None
    broke = bool(previous_value is not None and previous_close is not None and previous_close < previous_value and close >= value)
    touched = bool(previous_value is not None and previous_close is not None and low is not None and previous_close >= previous_value and low <= value and close >= value)
    near = bool(atr is not None and atr > 0 and close >= value and close - value <= 0.5 * atr)
    label = "下から回復" if broke else "タッチ維持" if touched else "近接" if near else "—"
    return {"value": value, "dist": dist, "break": broke, "touch": touched, "near": near, "label": label}


def inception_from_frame(frame: pd.DataFrame) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if frame is None or frame.empty:
        return None, []
    source = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    volume = frame["volume"].astype(float)
    valid = np.isfinite(source.to_numpy(float)) & np.isfinite(volume.to_numpy(float)) & (volume.to_numpy(float) >= 0)
    if not valid.any():
        return None, []
    f = frame.loc[valid].copy().reset_index(drop=True)
    s = source.loc[valid].reset_index(drop=True)
    v = volume.loc[valid].reset_index(drop=True)
    pv = s * v
    cum_pv = pv.cumsum()
    cum_v = v.cumsum()
    series = []
    for index, row in f.iterrows():
        total_v = float(cum_v.iloc[index])
        if total_v <= 0:
            continue
        series.append({"time": str(row["date"]), "value": float(cum_pv.iloc[index]) / total_v})
    total_v = float(cum_v.iloc[-1])
    state = {
        "first": str(f.iloc[0]["date"]),
        "through": str(f.iloc[-1]["date"]),
        "sum_pv": float(cum_pv.iloc[-1]),
        "sum_v": total_v,
        "n": int(len(f)),
        "anchor_close": float(f.iloc[-1]["close"]),
    }
    return state, series


def advance_inception(state: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    if not state or frame is None or frame.empty:
        return dict(state or {})
    through = str(state.get("through") or "")
    fresh = frame[frame["date"] > through].copy()
    if fresh.empty:
        return dict(state)
    source = (fresh["high"] + fresh["low"] + fresh["close"]) / 3.0
    volume = fresh["volume"].astype(float)
    pv = source * volume
    valid = np.isfinite(pv.to_numpy(float)) & np.isfinite(volume.to_numpy(float)) & (volume.to_numpy(float) >= 0)
    fresh = fresh.loc[valid]
    pv = pv.loc[valid]
    volume = volume.loc[valid]
    if fresh.empty:
        return dict(state)
    out = dict(state)
    out["sum_pv"] = float(out.get("sum_pv") or 0.0) + float(pv.sum())
    out["sum_v"] = float(out.get("sum_v") or 0.0) + float(volume.sum())
    out["n"] = int(out.get("n") or 0) + int(len(fresh))
    out["through"] = str(fresh.iloc[-1]["date"])
    out["anchor_close"] = float(fresh.iloc[-1]["close"])
    if not out.get("first"):
        out["first"] = str(fresh.iloc[0]["date"])
    return out


def inception_value(state: dict[str, Any] | None) -> float | None:
    if not isinstance(state, dict):
        return None
    pv = finite(state.get("sum_pv"))
    volume = finite(state.get("sum_v"))
    if pv is None or volume is None or volume <= 0:
        return None
    return pv / volume


def chart_rows(frame: pd.DataFrame, sessions: int = 320) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    rows = []
    for row in frame.tail(sessions).itertuples(index=False):
        rows.append({
            "time": str(row.date),
            "open": round(float(row.open), 6) if finite(row.open) is not None else round(float(row.close), 6),
            "high": round(float(row.high), 6),
            "low": round(float(row.low), 6),
            "close": round(float(row.close), 6),
            "volume": round(float(row.volume), 3),
        })
    return rows
