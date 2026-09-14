from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-display-observation-history-1.0.0"
MIN_PRICE = 5.0
MIN_DDV20 = 10_000_000.0
MAX_SPLIT_MOVE = 1.50


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


def _prepare(frame: pd.DataFrame, tickers: Iterable[str], session: str) -> pd.DataFrame:
    d = frame.copy()
    d.columns = [str(column).strip().lower().replace(" ", "_") for column in d.columns]
    required = {"ticker", "date", "close", "volume"}
    missing = sorted(required - set(d.columns))
    if missing:
        raise ValueError("display-observation OHLC missing: " + ", ".join(missing))
    active = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    d["ticker"] = d["ticker"].astype(str).str.strip().str.upper()
    parsed = pd.to_datetime(d["date"], errors="coerce", utc=True)
    d = d.loc[parsed.notna()].copy()
    d["date"] = parsed.loc[parsed.notna()].dt.strftime("%Y-%m-%d")
    d = d[d["ticker"].isin(active) & (d["date"] <= session)].copy()
    for column in ("close", "volume"):
        d[column] = pd.to_numeric(d[column], errors="coerce")
    if "is_complete" in d.columns:
        d = d[_bool_series(d["is_complete"], default=False)]
    if "split_checked" in d.columns:
        d = d[_bool_series(d["split_checked"], default=False)]
    if "split_anomaly" in d.columns:
        d = d[~_bool_series(d["split_anomaly"], default=False)]
    d = d.dropna(subset=["close", "volume"])
    d = d[(d["close"] > 0) & (d["volume"] >= 0)]
    d = d.sort_values(["ticker", "date"], kind="mergesort").drop_duplicates(["ticker", "date"], keep="last")
    if d.empty:
        raise ValueError("no valid OHLC rows for display observation history")
    return d


def build_histories(frame: pd.DataFrame, tickers: Iterable[str], *, session: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recover the old display-only RS63 pool and parabolic-rate history.

    Old RS63 pool contract: split/data-artifact guard (max absolute 1d move over
    trailing 200 sessions <=150%), close >= $5 and 20-day average dollar volume
    >= $10M. Historical ranking is performed inside that historical pool.
    """
    d = _prepare(frame, tickers, session)
    groups = d.groupby("ticker", sort=False)
    d["ret1"] = groups["close"].pct_change(fill_method=None)
    d["maxabs200"] = d.groupby("ticker", sort=False)["ret1"].transform(
        lambda series: series.abs().rolling(200, min_periods=2).max()
    )
    dollar_volume = d["close"] * d["volume"]
    d["ddv20"] = dollar_volume.groupby(d["ticker"], sort=False).transform(
        lambda series: series.rolling(20, min_periods=20).mean()
    )
    d["ret63"] = d["close"] / groups["close"].shift(63) - 1.0
    d["sma200"] = groups["close"].transform(lambda series: series.rolling(200, min_periods=200).mean())

    pool = (
        d["ret63"].notna()
        & d["close"].ge(MIN_PRICE)
        & d["ddv20"].ge(MIN_DDV20)
        & d["maxabs200"].fillna(0.0).le(MAX_SPLIT_MOVE)
    )
    d["rs63"] = np.nan
    eligible = d.loc[pool, ["date", "ret63"]]
    if not eligible.empty:
        d.loc[eligible.index, "rs63"] = (
            eligible.groupby("date", sort=False)["ret63"].rank(method="average", pct=True) * 100.0
        )

    dates = sorted(d["date"].unique().tolist())[-756:]
    reversal: list[dict[str, Any]] = []
    parabolic: list[dict[str, Any]] = []
    for day in dates:
        day_frame = d[d["date"] == day]
        ranked = day_frame[day_frame["rs63"].notna()].sort_values(
            ["rs63", "ticker"], ascending=[False, True], kind="mergesort"
        ).head(20)
        reversal.append({
            "date": str(day),
            "pool_count": int(day_frame["rs63"].notna().sum()),
            "top20": [
                {"ticker": str(row.ticker), "rs63": float(row.rs63), "ret63": float(row.ret63)}
                for row in ranked.itertuples(index=False)
            ],
        })

        valid = day_frame["sma200"].notna() & day_frame["close"].notna()
        denominator = int(valid.sum())
        if denominator:
            count = int((day_frame.loc[valid, "close"] >= day_frame.loc[valid, "sma200"] * 1.45).sum())
            parabolic.append({
                "date": str(day),
                "value": 100.0 * count / denominator,
                "count": count,
                "denominator": denominator,
            })
    return reversal, parabolic


def write_histories(
    frame: pd.DataFrame,
    tickers: Iterable[str],
    data_dir: str | Path,
    *,
    session: str,
    generated_at: str,
) -> tuple[Path, Path]:
    root = Path(data_dir)
    reversal, parabolic = build_histories(frame, tickers, session=session)
    reversal_path = root / "history" / "reversal_rs63_2y.json"
    parabolic_path = root / "history" / "parabolic_rate_2y.json"
    reversal_obj = {
        "session_date": session,
        "generated_at": generated_at,
        "coverage": 1.0 if reversal and len(reversal[-1].get("top20") or []) == 20 else 0.0,
        "source": "same adjusted 3y full-universe OHLC used by display reconstruction",
        "schema_version": "v38.reversal_rs63_history.1",
        "calculation_version": CALCULATION_VERSION,
        "status": "READY" if reversal and len(reversal[-1].get("top20") or []) == 20 else "DATA_REQUIRED",
        "pool_contract": "maxabs200<=1.50, close>=5, ddv20>=10M; historical pool",
        "series": reversal,
        "trading_gate_eligible": False,
    }
    parabolic_obj = {
        "session_date": session,
        "generated_at": generated_at,
        "coverage": 1.0 if len(parabolic) >= 60 else 0.0,
        "source": "same adjusted 3y full-universe OHLC used by display reconstruction",
        "schema_version": "v38.parabolic_rate_history.1",
        "calculation_version": CALCULATION_VERSION,
        "status": "READY" if len(parabolic) >= 60 else "DATA_REQUIRED",
        "definition": "100 * count(close >= SMA200*1.45) / count(valid SMA200)",
        "series": parabolic[-756:],
        "trading_gate_eligible": False,
    }
    atomic_write_json(reversal_path, reversal_obj)
    atomic_write_json(parabolic_path, parabolic_obj)
    return reversal_path, parabolic_path


def exact_old_top20(data_dir: str | Path, *, lag: int = 42) -> tuple[str | None, list[dict[str, Any]]]:
    obj_path = Path(data_dir) / "history" / "reversal_rs63_2y.json"
    if not obj_path.is_file():
        return None, []
    try:
        obj = json.loads(obj_path.read_text(encoding="utf-8"))
    except Exception:
        return None, []
    rows = obj.get("series") if isinstance(obj, dict) else None
    if not isinstance(rows, list) or len(rows) <= lag:
        return None, []
    row = rows[-(lag + 1)]
    top20 = row.get("top20") if isinstance(row, dict) else None
    clean = [dict(item) for item in top20 if isinstance(item, dict)] if isinstance(top20, list) else []
    return str(row.get("date") or "") or None, clean[:20]
