from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .freshness import atomic_write_json
from .stock_adapter import MIN_DDV20, MIN_PRICE, load_tabular

CALCULATION_VERSION = "v38-historical-stock-reconstruction-1.0.0"
SCHEMA_VERSION = "v38.reconstructed_stock_history.1"
DEFAULT_SESSIONS = 126
TOP_RS_ROWS = 100
TOP_N = 24
DROP_RANK = 36
LEADER_RS = 85.0
F1_LAG_SESSIONS = 20
F1_COV_FULL = 0.90
F1_COV_MIN = 0.70


class HistoricalReconstructionError(RuntimeError):
    pass


def _bool_series(series: pd.Series, *, default: bool) -> pd.Series:
    def parse(value: Any) -> bool:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, np.integer, float, np.floating)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "ok", "checked", "complete", "completed"}

    return series.map(parse)


def _prepare_history(ohlcv: pd.DataFrame, tickers: Iterable[str], session_date: str) -> tuple[pd.DataFrame, list[str]]:
    d = ohlcv.copy()
    d.columns = [str(col).strip().lower().replace(" ", "_") for col in d.columns]
    required = {"ticker", "date", "high", "close", "volume"}
    missing = sorted(required - set(d.columns))
    if missing:
        raise HistoricalReconstructionError("ohlcv missing required columns: " + ", ".join(missing))

    active = sorted({str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()})
    if not active:
        raise HistoricalReconstructionError("current universe is empty")

    d["ticker"] = d["ticker"].astype(str).str.strip().str.upper()
    parsed = pd.to_datetime(d["date"], errors="coerce", utc=True)
    d = d.loc[parsed.notna()].copy()
    d["date"] = parsed.loc[parsed.notna()].dt.strftime("%Y-%m-%d")
    d = d[(d["ticker"].isin(active)) & (d["date"] <= session_date)].copy()
    if d.empty:
        raise HistoricalReconstructionError("no OHLC history for the current universe")

    if "is_complete" in d.columns:
        d = d[_bool_series(d["is_complete"], default=False)]
    if "split_checked" in d.columns:
        d = d[_bool_series(d["split_checked"], default=False)]
    if "split_anomaly" in d.columns:
        d = d[~_bool_series(d["split_anomaly"], default=False)]

    for column in ("high", "close", "volume"):
        d[column] = pd.to_numeric(d[column], errors="coerce")
    d = d.dropna(subset=["high", "close", "volume"])
    d = d[(d["close"] > 0) & (d["high"] > 0) & (d["volume"] >= 0)]
    d = d.sort_values(["ticker", "date"], kind="mergesort").drop_duplicates(["ticker", "date"], keep="last")
    if d.empty:
        raise HistoricalReconstructionError("no valid completed split-checked OHLC history")
    return d, active


def _add_stock_metrics(d: pd.DataFrame) -> pd.DataFrame:
    out = d.copy()
    groups = out.groupby("ticker", sort=False)
    out["sma50"] = groups["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    out["sma200"] = groups["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    out["ddv20"] = (
        (out["close"] * out["volume"])
        .groupby(out["ticker"], sort=False)
        .transform(lambda s: s.rolling(20, min_periods=20).mean())
    )
    for period in (20, 63, 126, 189):
        prior = groups["close"].shift(period)
        out[f"ret{period}"] = out["close"] / prior - 1.0
    out["high52"] = groups["high"].transform(lambda s: s.rolling(252, min_periods=252).max())
    out["dist52"] = out["close"] / out["high52"] - 1.0

    for period in (63, 126, 189):
        eligible = (
            out[f"ret{period}"].notna()
            & out["close"].ge(MIN_PRICE)
            & out["ddv20"].ge(MIN_DDV20)
        )
        out[f"rs{period}"] = np.nan
        ranked = out.loc[eligible, ["date", f"ret{period}"]].copy()
        if not ranked.empty:
            ranks = ranked.groupby("date", sort=False)[f"ret{period}"].rank(method="average", pct=True) * 100.0
            out.loc[ranked.index, f"rs{period}"] = ranks
    return out


def _severity(value: float | None, warn: float, severe: float) -> str:
    if value is None:
        return "NO_JUDGMENT"
    if value >= severe:
        return "SEVERE"
    if value >= warn:
        return "CAUTION"
    return "NORMAL"


def _base_pool(day: pd.DataFrame) -> pd.DataFrame:
    pool = day[
        day["close"].ge(MIN_PRICE)
        & day["ddv20"].ge(MIN_DDV20)
        & day["sma50"].notna()
        & day["sma200"].notna()
        & (day["sma50"] > day["sma200"])
        & day["rs189"].notna()
    ].copy()
    return pool.sort_values(["rs189", "ticker"], ascending=[False, True], kind="mergesort")


def _f2(day: pd.DataFrame) -> dict[str, Any]:
    top24 = _base_pool(day).head(TOP_N)
    observed = top24[top24["rs63"].notna()]
    weak = observed[observed["rs63"] < LEADER_RS]
    value = float(len(weak) / len(observed)) if len(observed) else None
    return {
        "value": value,
        "status": "OK" if value is not None else "DATA_INCOMPLETE",
        "severity": _severity(value, 0.25, 0.40),
        "top24_count": int(len(top24)),
        "observable_count": int(len(observed)),
        "weak_count": int(len(weak)),
    }


def _f3(day: pd.DataFrame) -> dict[str, Any]:
    pool = _base_pool(day)
    queue = pool[(pool["rs189"] >= LEADER_RS) & (pool["close"] > pool["sma200"])].copy()
    observed = queue[queue["ret20"].notna() & queue["dist52"].notna()]
    broken = observed[(observed["ret20"] <= 0.0) | (observed["dist52"] < -0.15)]
    if len(queue) < 3:
        value = None
        status = "NO_JUDGMENT"
    elif len(observed) != len(queue):
        value = None
        status = "DATA_INCOMPLETE"
    else:
        value = float(len(broken) / len(queue))
        status = "OK"
    return {
        "value": value,
        "status": status,
        "severity": _severity(value, 0.40, 0.60),
        "queue_count": int(len(queue)),
        "observable_count": int(len(observed)),
        "break_count": int(len(broken)),
    }


def _f1(old_day: pd.DataFrame | None, current_day: pd.DataFrame) -> dict[str, Any]:
    if old_day is None:
        return {
            "value": None,
            "status": "DATA_REQUIRED",
            "severity": "NO_JUDGMENT",
            "coverage": None,
            "old_top24_count": 0,
            "observable_count": 0,
            "drop_count": 0,
        }
    old_names = _base_pool(old_day).head(TOP_N)["ticker"].astype(str).tolist()
    if not old_names:
        return {
            "value": None,
            "status": "DATA_REQUIRED",
            "severity": "NO_JUDGMENT",
            "coverage": None,
            "old_top24_count": 0,
            "observable_count": 0,
            "drop_count": 0,
        }

    pool = _base_pool(current_day)
    rank_now = {str(ticker): rank for rank, ticker in enumerate(pool["ticker"].astype(str), start=1)}
    by_ticker = current_day.set_index("ticker", drop=False)
    observable = 0
    dropped = 0
    for ticker in old_names:
        if ticker not in by_ticker.index:
            continue
        row = by_ticker.loc[ticker]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[-1]
        needed = ("close", "ddv20", "sma50", "sma200", "rs189")
        if any(pd.isna(row.get(key)) for key in needed):
            continue
        observable += 1
        in_base = (
            float(row["close"]) >= MIN_PRICE
            and float(row["ddv20"]) >= MIN_DDV20
            and float(row["sma50"]) > float(row["sma200"])
        )
        if (not in_base) or rank_now.get(ticker, 10**9) > DROP_RANK:
            dropped += 1

    coverage = observable / len(old_names) if old_names else None
    if not observable or coverage is None or coverage < F1_COV_MIN:
        value = None
        status = "DATA_INCOMPLETE"
    else:
        value = dropped / observable
        status = "FULL" if coverage >= F1_COV_FULL else "PARTIAL"
    return {
        "value": float(value) if value is not None else None,
        "status": status,
        "severity": _severity(value, 0.20, 0.30),
        "coverage": float(coverage) if coverage is not None else None,
        "old_top24_count": int(len(old_names)),
        "observable_count": int(observable),
        "drop_count": int(dropped),
    }


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    x = float(value)
    return x if math.isfinite(x) else None


def _row_payload(row: pd.Series) -> dict[str, Any]:
    return {
        "ticker": str(row["ticker"]),
        "price": _number(row.get("close")),
        "ddv20": _number(row.get("ddv20")),
        "sma50": _number(row.get("sma50")),
        "sma200": _number(row.get("sma200")),
        "ret20": _number(row.get("ret20")),
        "ret63": _number(row.get("ret63")),
        "ret126": _number(row.get("ret126")),
        "ret189": _number(row.get("ret189")),
        "high52": _number(row.get("high52")),
        "dist52": _number(row.get("dist52")),
        "rs63": _number(row.get("rs63")),
        "rs126": _number(row.get("rs126")),
        "rs189": _number(row.get("rs189")),
    }


def _ranked(day: pd.DataFrame, key: str, limit: int) -> list[dict[str, Any]]:
    ranked = day[day[key].notna()].sort_values([key, "ticker"], ascending=[False, True], kind="mergesort").head(limit)
    return [_row_payload(row) for _, row in ranked.iterrows()]


def _reconstruction_dates(metrics: pd.DataFrame, active_count: int, session_date: str, sessions: int) -> list[str]:
    counts = metrics.groupby("date", sort=True)["close"].count()
    floor = max(30, int(math.ceil(active_count * 0.60)))
    dates = [str(day) for day, count in counts.items() if int(count) >= floor and str(day) <= session_date]
    if not dates:
        raise HistoricalReconstructionError("no historical sessions meet the current-universe coverage floor")
    return dates[-max(22, int(sessions)) :]


def build_reconstructed_stock_history(
    ohlcv: pd.DataFrame,
    tickers: Iterable[str],
    *,
    session_date: str,
    generated_at: str,
    sessions: int = DEFAULT_SESSIONS,
) -> dict[str, Any]:
    if not generated_at:
        raise HistoricalReconstructionError("generated_at is required")
    try:
        session_date = pd.Timestamp(session_date).strftime("%Y-%m-%d")
    except Exception as exc:
        raise HistoricalReconstructionError(f"invalid session_date: {session_date}") from exc

    prepared, active = _prepare_history(ohlcv, tickers, session_date)
    metrics = _add_stock_metrics(prepared)
    dates = _reconstruction_dates(metrics, len(active), session_date, sessions)
    by_date = {str(day): frame.copy() for day, frame in metrics[metrics["date"].isin(dates)].groupby("date", sort=True)}

    rows: list[dict[str, Any]] = []
    for index, day in enumerate(dates):
        frame = by_date.get(day)
        if frame is None or frame.empty:
            continue
        valid50 = frame["sma50"].notna() & frame["close"].notna()
        valid200 = frame["sma200"].notna() & frame["close"].notna()
        valid50_count = int(valid50.sum())
        valid200_count = int(valid200.sum())
        breadth50 = float(100.0 * ((frame.loc[valid50, "close"] > frame.loc[valid50, "sma50"]).sum()) / valid50_count) if valid50_count else None
        min200 = max(30, int(math.ceil(0.60 * len(active))))
        breadth200 = (
            float(100.0 * ((frame.loc[valid200, "close"] > frame.loc[valid200, "sma200"]).sum()) / valid200_count)
            if valid200_count >= min200 else None
        )
        old_frame = by_date.get(dates[index - F1_LAG_SESSIONS]) if index >= F1_LAG_SESSIONS else None
        f1 = _f1(old_frame, frame)
        f2 = _f2(frame)
        f3 = _f3(frame)
        rows.append({
            "date": day,
            "coverage": float(frame["close"].notna().sum() / len(active)),
            "breadth50": breadth50,
            "breadth200": breadth200,
            "breadth50_valid": valid50_count,
            "breadth200_valid": valid200_count,
            "f1": f1,
            "f2": f2,
            "f3": f3,
            "rs_top": _ranked(frame, "rs189", TOP_RS_ROWS),
            "rs_windows": {
                "63": _ranked(frame, "rs63", 10),
                "126": _ranked(frame, "rs126", 10),
            },
        })

    if not rows:
        raise HistoricalReconstructionError("historical reconstruction produced no sessions")
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": rows[-1]["coverage"],
        "source": "reconstructed:Yahoo adjusted daily OHLC using current-universe membership",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
        "first_session": rows[0]["date"],
        "latest_session": rows[-1]["date"],
        "session_count": len(rows),
        "current_universe_count": len(active),
        "survivorship_warning": True,
        "trading_gate_eligible": False,
        "provenance": {
            "pit_universe": False,
            "membership_scope": f"current universe as of {session_date}",
            "ohlcv": "Yahoo Finance adjusted daily OHLC fetched by production acquisition",
            "purpose": "display/history reconstruction only; never a normal-stock hard gate",
        },
        "rules": {
            "rs": "same cross-sectional RS63/126/189 percentile formula as stock_adapter",
            "breadth": "same Close>SMA50 / Close>SMA200 formula, current universe applied historically",
            "f1": "same 20-session Top24 drop formula, but old/current membership reconstructed within current universe",
            "f2": "same current base-pool RS189 Top24 fraction with RS63<85",
            "f3": "same leader queue fraction with Ret20<=0 OR Dist52<-15%",
        },
        "rows": rows,
    }


def write_reconstructed_stock_history(
    ohlcv_path: str | Path,
    tickers: Iterable[str],
    output_path: str | Path,
    *,
    session_date: str,
    generated_at: str,
    sessions: int = DEFAULT_SESSIONS,
) -> Path:
    out = build_reconstructed_stock_history(
        load_tabular(ohlcv_path),
        tickers,
        session_date=session_date,
        generated_at=generated_at,
        sessions=sessions,
    )
    return atomic_write_json(output_path, out)
