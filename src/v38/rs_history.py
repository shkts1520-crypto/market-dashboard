from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from v38.stock_adapter import MIN_DDV20, MIN_PRICE, RS_PERIODS, _prepare_ohlcv

RS_HISTORY_SCHEMA_VERSION = "v38.rs.history.1"
RS_HISTORY_CALCULATION_VERSION = "v38-rs-history-1.0.0"
TOP_N = 10
PERSISTENCE_TOP_N = 24
COMPARISON_LAGS = ((1, "1日", "前営業日"), (5, "1週", "約5営業日前"), (21, "1か月", "約21営業日前"))
TAG_ORDER = ("定着", "新規急浮上", "再浮上", "失速中", "一日急騰型", "継続")
CURRENT_MATCH_TOLERANCE = 1e-7


class RSHistoryError(RuntimeError):
    """Raised when RS history cannot be reproduced safely from current inputs."""


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise RSHistoryError(f"cannot read JSON: {path}") from exc
    if not isinstance(obj, dict):
        raise RSHistoryError(f"expected JSON object: {path}")
    return obj


def _atomic_write_json(path: str | Path, obj: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def _rank_percentile(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rank(axis=1, method="average", pct=True) * 100.0


def _ticker_history(group: pd.DataFrame, session_date: str) -> dict[int, pd.Series]:
    g = group[group["date"] <= session_date].copy()
    if g.empty:
        return {}
    g = g.sort_values("date", kind="mergesort").drop_duplicates("date", keep="last")
    # Current stock_adapter drops forming rows and fails the ticker when recent data
    # are unsafe. For retrospective display, retain the date position but null any
    # row that is not completed/split-checked so no return silently bridges it.
    valid = (
        (g["_complete"] == True)  # noqa: E712
        & (g["_split_checked"] == True)  # noqa: E712
        & (~g["_split_anomaly"].fillna(False))
        & g["close"].notna()
        & g["volume"].notna()
        & (g["close"] > 0)
        & (g["volume"] >= 0)
    )
    index = pd.Index(g["date"].astype(str), name="date")
    close = pd.Series(np.where(valid, g["close"].astype(float), np.nan), index=index, dtype=float)
    volume = pd.Series(np.where(valid, g["volume"].astype(float), np.nan), index=index, dtype=float)
    ddv20 = (close * volume).rolling(20, min_periods=20).mean()
    pool = (close >= MIN_PRICE) & (ddv20 >= MIN_DDV20)
    output: dict[int, pd.Series] = {}
    for period in RS_PERIODS:
        returns = close.pct_change(period, fill_method=None)
        output[period] = returns.where(pool)
    return output


def _build_rs_frames(ohlcv: pd.DataFrame, tickers: list[str], session_date: str) -> dict[int, pd.DataFrame]:
    prepared = _prepare_ohlcv(ohlcv)
    prepared = prepared[prepared["ticker"].isin(tickers) & (prepared["date"] <= session_date)].copy()
    if prepared.empty:
        raise RSHistoryError("no OHLCV rows for current RS universe")

    by_period: dict[int, dict[str, pd.Series]] = {period: {} for period in RS_PERIODS}
    for ticker, group in prepared.groupby("ticker", sort=False):
        history = _ticker_history(group, session_date)
        for period, series in history.items():
            by_period[period][str(ticker)] = series

    frames: dict[int, pd.DataFrame] = {}
    for period in RS_PERIODS:
        columns = by_period[period]
        if not columns:
            raise RSHistoryError(f"RS{period}: no historical return series")
        returns = pd.concat(columns, axis=1).sort_index()
        returns = returns.loc[returns.index <= session_date]
        frames[period] = _rank_percentile(returns)
    return frames


def _top_at(frame: pd.DataFrame, date: str, n: int = TOP_N) -> list[str]:
    if date not in frame.index:
        return []
    values = pd.to_numeric(frame.loc[date], errors="coerce").dropna()
    ordered = sorted(((str(ticker), float(value)) for ticker, value in values.items()), key=lambda item: (-item[1], item[0]))
    return [ticker for ticker, _ in ordered[:n]]


def _valid_dates(frame: pd.DataFrame, session_date: str) -> list[str]:
    subset = frame.loc[frame.index <= session_date].dropna(how="all")
    return [str(value) for value in subset.index.tolist()]


def _lag_snapshot(frame: pd.DataFrame, session_date: str, lag: int) -> tuple[str | None, list[str]]:
    dates = _valid_dates(frame, session_date)
    if len(dates) <= lag:
        return None, []
    day = dates[-1 - lag]
    return day, _top_at(frame, day)


def _value_at_lag(frame: pd.DataFrame, ticker: str, session_date: str, lag: int) -> float | None:
    dates = _valid_dates(frame, session_date)
    if len(dates) <= lag or ticker not in frame.columns:
        return None
    return _finite(frame.at[dates[-1 - lag], ticker])


def _current_rows(rs: dict[str, Any]) -> list[dict[str, Any]]:
    raw = rs.get("rows")
    if not isinstance(raw, list):
        raise RSHistoryError("rs.rows missing")
    return [dict(row) for row in raw if isinstance(row, dict) and str(row.get("ticker") or "").strip()]


def _validate_current_identity(rs: dict[str, Any], frames: dict[int, pd.DataFrame], session_date: str) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    compared = 0
    for row in _current_rows(rs):
        ticker = str(row.get("ticker") or "").strip().upper()
        for period in RS_PERIODS:
            expected = _finite(row.get(f"rs{period}"))
            if expected is None:
                continue
            compared += 1
            actual = _finite(frames[period].at[session_date, ticker]) if session_date in frames[period].index and ticker in frames[period].columns else None
            if actual is None or abs(actual - expected) > CURRENT_MATCH_TOLERANCE:
                mismatches.append({
                    "ticker": ticker,
                    "period": period,
                    "expected": expected,
                    "recomputed": actual,
                })
    return {
        "compared_values": compared,
        "mismatch_count": len(mismatches),
        "tolerance": CURRENT_MATCH_TOLERANCE,
        "mismatches": mismatches[:20],
    }


def _comparison(frames: dict[int, pd.DataFrame], session_date: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for period in RS_PERIODS:
        frame = frames[period]
        dates = _valid_dates(frame, session_date)
        if not dates or dates[-1] != session_date:
            output[str(period)] = {"current": [], "windows": [], "reason": "CURRENT_RS_DATE_MISSING"}
            continue
        current = _top_at(frame, session_date)
        windows = []
        for lag, label, period_label in COMPARISON_LAGS:
            prior_date, previous = _lag_snapshot(frame, session_date, lag)
            if prior_date is None:
                windows.append({
                    "lag": lag,
                    "label": label,
                    "period_label": period_label,
                    "date": None,
                    "previous": [],
                    "in": [],
                    "out": [],
                    "overlap": None,
                    "turnover": None,
                    "status": "DATA_REQUIRED",
                })
                continue
            previous_set = set(previous)
            current_set = set(current)
            entered = [ticker for ticker in current if ticker not in previous_set]
            exited = [ticker for ticker in previous if ticker not in current_set]
            windows.append({
                "lag": lag,
                "label": label,
                "period_label": period_label,
                "date": prior_date,
                "previous": previous,
                "in": entered,
                "out": exited,
                "overlap": len(current_set & previous_set),
                "turnover": len(entered),
                "status": "READY",
            })
        output[str(period)] = {"current": current, "windows": windows}
    return output


def _delta_21(frame: pd.DataFrame, ticker: str, session_date: str) -> float | None:
    if ticker not in frame.columns:
        return None
    values = pd.to_numeric(frame[ticker].loc[:session_date], errors="coerce").dropna()
    if len(values) < 22:
        return None
    return float(values.iloc[-1] - values.iloc[-22])


def _tag_persistence(*, rs_now: float, top10_days: int, streak: int, move21: float | None,
                     d63: float | None, d126: float | None, d189: float | None,
                     top24_rate: float | None, smooth63: float | None) -> str:
    if (
        top10_days <= 2 and streak <= 2 and d63 is not None and d63 >= 12
        and (smooth63 is None or rs_now - smooth63 >= 8)
    ):
        return "一日急騰型"
    if streak <= 4 and move21 is not None and move21 >= 10 and d63 is not None and d63 >= 5:
        return "新規急浮上"
    if (move21 is not None and move21 <= -8) or (
        d63 is not None and d126 is not None and d63 <= -10 and d126 <= -5
    ):
        return "失速中"
    if streak <= 5 and top10_days >= 5 and move21 is not None and move21 >= 5:
        return "再浮上"
    if (
        top10_days >= 15 and top24_rate is not None and top24_rate >= 0.75
        and (d189 is None or d189 >= -3)
        and (smooth63 is None or smooth63 >= 85)
    ):
        return "定着"
    return "継続"


def _persistence(rs: dict[str, Any], frames: dict[int, pd.DataFrame], session_date: str) -> dict[str, Any]:
    current = sorted(
        (row for row in _current_rows(rs) if _finite(row.get("rs189")) is not None),
        key=lambda row: (-float(row["rs189"]), str(row.get("ticker") or "")),
    )[:PERSISTENCE_TOP_N]
    rank189 = frames[189].rank(axis=1, ascending=False, method="min")
    rows = []
    for current_rank, raw in enumerate(current, start=1):
        ticker = str(raw.get("ticker") or "").strip().upper()
        if ticker not in rank189.columns:
            continue
        ranks = pd.to_numeric(rank189[ticker].loc[:session_date], errors="coerce").dropna()
        if ranks.empty:
            continue
        w21 = ranks.iloc[-21:]
        w63 = ranks.iloc[-63:]
        top10_days = int((w21 <= 10).sum())
        top24_days = int((w63 <= PERSISTENCE_TOP_N).sum())
        valid21 = int(len(w21))
        valid63 = int(len(w63))
        streak = 0
        for value in ranks.iloc[::-1]:
            if value <= 10:
                streak += 1
            else:
                break
        old_rank = float(ranks.iloc[-22]) if len(ranks) >= 22 else None
        historical_rank = float(ranks.iloc[-1])
        move21 = old_rank - historical_rank if old_rank is not None else None
        d63 = _delta_21(frames[63], ticker, session_date)
        d126 = _delta_21(frames[126], ticker, session_date)
        d189 = _delta_21(frames[189], ticker, session_date)
        smooth_values = [
            _value_at_lag(frames[63], ticker, session_date, lag)
            for lag in (0, 21, 42)
        ]
        smooth63 = (
            float(sum(value for value in smooth_values if value is not None) / 3.0)
            if all(value is not None for value in smooth_values)
            else None
        )
        top24_rate = top24_days / valid63 if valid63 else None
        rs_now = float(raw["rs189"])
        tag = _tag_persistence(
            rs_now=rs_now,
            top10_days=top10_days,
            streak=streak,
            move21=move21,
            d63=d63,
            d126=d126,
            d189=d189,
            top24_rate=top24_rate,
            smooth63=smooth63,
        )
        rows.append({
            "rank": current_rank,
            "historical_rank": int(round(historical_rank)),
            "ticker": ticker,
            "rs189": rs_now,
            "top10_days_21": top10_days,
            "valid21": valid21,
            "top24_days_63": top24_days,
            "valid63": valid63,
            "top24_rate": top24_rate,
            "top10_streak": streak,
            "rank_move_21": move21,
            "rs63_change_21": d63,
            "rs126_change_21": d126,
            "rs189_change_21": d189,
            "rs63_smooth_3snap": smooth63,
            "tag": tag,
        })
    groups = [
        {"tag": tag, "tickers": [row["ticker"] for row in rows if row["tag"] == tag]}
        for tag in TAG_ORDER
        if any(row["tag"] == tag for row in rows)
    ]
    return {
        "top_n": PERSISTENCE_TOP_N,
        "rows": rows,
        "groups": groups,
        "tag_order": list(TAG_ORDER),
        "display_only": True,
    }


def build_rs_history_analysis(ohlcv: pd.DataFrame, rs: dict[str, Any], *, session_date: str) -> dict[str, Any]:
    rows = _current_rows(rs)
    tickers = sorted({str(row.get("ticker") or "").strip().upper() for row in rows if row.get("ticker")})
    if not tickers:
        raise RSHistoryError("current RS universe is empty")
    frames = _build_rs_frames(ohlcv, tickers, session_date)
    identity = _validate_current_identity(rs, frames, session_date)
    if identity["mismatch_count"]:
        return {
            "status": "DATA_REQUIRED",
            "reason": "CURRENT_RS_RECOMPUTE_MISMATCH",
            "schema_version": RS_HISTORY_SCHEMA_VERSION,
            "calculation_version": RS_HISTORY_CALCULATION_VERSION,
            "identity_check": identity,
            "scope": "retrospective current-PIT/current-quality universe; display only",
        }

    comparison = _comparison(frames, session_date)
    required_windows = [
        window
        for period in comparison.values()
        for window in period.get("windows", [])
    ]
    if len(required_windows) != len(RS_PERIODS) * len(COMPARISON_LAGS) or any(window.get("status") != "READY" for window in required_windows):
        return {
            "status": "DATA_REQUIRED",
            "reason": "RS_COMPARISON_HISTORY_INSUFFICIENT",
            "schema_version": RS_HISTORY_SCHEMA_VERSION,
            "calculation_version": RS_HISTORY_CALCULATION_VERSION,
            "identity_check": identity,
            "comparison": comparison,
            "scope": "retrospective current-PIT/current-quality universe; display only",
        }

    persistence = _persistence(rs, frames, session_date)
    if not persistence["rows"]:
        return {
            "status": "DATA_REQUIRED",
            "reason": "RS189_PERSISTENCE_HISTORY_INSUFFICIENT",
            "schema_version": RS_HISTORY_SCHEMA_VERSION,
            "calculation_version": RS_HISTORY_CALCULATION_VERSION,
            "identity_check": identity,
            "comparison": comparison,
            "persistence": persistence,
            "scope": "retrospective current-PIT/current-quality universe; display only",
        }

    history_sessions = max(len(_valid_dates(frame, session_date)) for frame in frames.values())
    return {
        "status": "READY",
        "reason": "CURRENT_RS_FORMULA_REPRODUCED",
        "schema_version": RS_HISTORY_SCHEMA_VERSION,
        "calculation_version": RS_HISTORY_CALCULATION_VERSION,
        "session_date": session_date,
        "history_sessions": history_sessions,
        "identity_check": identity,
        "comparison": comparison,
        "persistence": persistence,
        "rules": {
            "periods": list(RS_PERIODS),
            "top_n": TOP_N,
            "comparison_lags": [lag for lag, _, _ in COMPARISON_LAGS],
            "price_min": MIN_PRICE,
            "ddv20_min": MIN_DDV20,
            "percentile_method": "average_rank_pct",
            "rs63_smooth": "mean(current, lag21, lag42) when all three are available",
            "persistence_tags_are_display_only": True,
        },
        "scope": "retrospective current-PIT/current-quality universe; display only; does not alter Core12 or eligibility",
    }


def enrich_rs_history_file(ohlcv_path: str | Path, rs_path: str | Path, *, session_date: str) -> Path:
    rs = _read_json(rs_path)
    if rs.get("session_date") != session_date:
        raise RSHistoryError(f"rs session mismatch: {rs.get('session_date')} != {session_date}")
    try:
        ohlcv = pd.read_csv(ohlcv_path)
        analysis = build_rs_history_analysis(ohlcv, rs, session_date=session_date)
    except Exception as exc:
        if isinstance(exc, RSHistoryError):
            reason = str(exc)
        else:
            reason = f"{type(exc).__name__}: {exc}"
        analysis = {
            "status": "DATA_REQUIRED",
            "reason": "RS_HISTORY_BUILD_FAILED",
            "detail": reason[:500],
            "schema_version": RS_HISTORY_SCHEMA_VERSION,
            "calculation_version": RS_HISTORY_CALCULATION_VERSION,
            "session_date": session_date,
            "scope": "retrospective current-PIT/current-quality universe; display only",
        }
    rs["history_analysis"] = analysis
    return _atomic_write_json(rs_path, rs)
