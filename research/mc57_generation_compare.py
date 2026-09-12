#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from mc57_nqsar_shadow import CANDIDATE_57, CALIBRATION_LOOKBACK, finite_or_none

TARGET = pd.Timestamp("2026-08-28")
EXPECTED = 56.438985
OUT = Path("research_out")


def download_closes(auto_adjust: bool) -> dict[str, pd.Series]:
    found: dict[str, pd.Series] = {}
    for start in range(0, len(CANDIDATE_57), 12):
        batch = CANDIDATE_57[start:start+12]
        data = yf.download(batch, start="2004-01-01", interval="1d", auto_adjust=auto_adjust,
                           actions=False, progress=False, threads=True, timeout=30, group_by="ticker")
        if data is None or data.empty:
            continue
        if isinstance(data.columns, pd.MultiIndex):
            outer = set(str(x) for x in data.columns.get_level_values(0))
            for t in batch:
                if t not in outer or "Close" not in data[t]:
                    continue
                s = pd.to_numeric(data[t]["Close"], errors="coerce").dropna()
                if not s.empty:
                    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
                    found[t] = s[~s.index.duplicated(keep="last")].sort_index()
    return found


def ticker_metrics(close: pd.Series, dd_binary: bool) -> dict[str, pd.Series]:
    c = close.astype(float).sort_index()
    sma10 = c.rolling(10, min_periods=10).mean()
    sma20 = c.rolling(20, min_periods=20).mean()
    sma50 = c.rolling(50, min_periods=50).mean()
    sma200 = c.rolling(200, min_periods=200).mean()
    r5 = c.pct_change(5, fill_method=None)
    r21 = c.pct_change(21, fill_method=None)
    r63 = c.pct_change(63, fill_method=None)
    r252 = c.pct_change(252, fill_method=None)
    high52 = c.rolling(252, min_periods=252).max()
    dd = c / high52 - 1.0
    def b(cond: pd.Series, valid: pd.Series) -> pd.Series:
        return cond.astype(float).mul(100).where(valid)
    ddscore = b(dd >= -0.10, dd.notna()) if dd_binary else ((dd + 0.30) / 0.25 * 100).clip(0, 100).where(dd.notna())
    return {
        "c10": b(c > sma10, sma10.notna()),
        "c20": b(c > sma20, sma20.notna()),
        "c50": b(c > sma50, sma50.notna()),
        "c200": b(c > sma200, sma200.notna()),
        "r5": b(r5 > 0, r5.notna()),
        "r21": b(r21 > 0, r21.notna()),
        "r63": b(r63 > 0, r63.notna()),
        "r252": b(r252 > 0, r252.notna()),
        "s20_50": b(sma20 > sma50, sma20.notna() & sma50.notna()),
        "s50_200": b(sma50 > sma200, sma50.notna() & sma200.notna()),
        "s50_up": b(sma50 > sma50.shift(20), sma50.notna() & sma50.shift(20).notna()),
        "dd52": ddscore,
    }


def calculate(closes: dict[str, pd.Series], dd_binary: bool, aggregation: str) -> pd.DataFrame:
    metrics = {t: ticker_metrics(s, dd_binary) for t, s in closes.items() if t in CANDIDATE_57}
    if aggregation == "metric_first":
        parts = {}
        for m in next(iter(metrics.values())).keys():
            f = pd.concat({t: mm[m] for t, mm in metrics.items()}, axis=1).sort_index()
            parts[m] = f.mean(axis=1, skipna=True)
        raw = pd.DataFrame(parts).mean(axis=1, skipna=False)
    elif aggregation == "ticker_first":
        per_ticker = {}
        for t, mm in metrics.items():
            per_ticker[t] = pd.DataFrame(mm).mean(axis=1, skipna=True)
        raw = pd.DataFrame(per_ticker).mean(axis=1, skipna=True)
    elif aggregation == "complete_ticker_only":
        per_ticker = {}
        for t, mm in metrics.items():
            frame = pd.DataFrame(mm)
            per_ticker[t] = frame.mean(axis=1, skipna=False)
        raw = pd.DataFrame(per_ticker).mean(axis=1, skipna=True)
    else:
        raise ValueError(aggregation)
    ema2 = raw.ewm(span=2, adjust=False).mean()
    mu = ema2.shift(1).rolling(CALIBRATION_LOOKBACK, min_periods=CALIBRATION_LOOKBACK).mean()
    sd = ema2.shift(1).rolling(CALIBRATION_LOOKBACK, min_periods=CALIBRATION_LOOKBACK).std(ddof=0)
    z = (ema2 - mu) / sd.where(sd > 0)
    logistic = 100 / (1 + np.power(3.0, -z))
    return pd.DataFrame({"raw": raw, "ema2": ema2, "mu": mu, "sigma": sd, "z": z, "logistic": logistic})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for auto_adjust in (True, False):
        closes = download_closes(auto_adjust)
        for dd_binary in (False, True):
            for aggregation in ("metric_first", "ticker_first", "complete_ticker_only"):
                p = calculate(closes, dd_binary, aggregation)
                if TARGET not in p.index:
                    continue
                row = p.loc[TARGET]
                for output in ("raw", "ema2", "logistic"):
                    value = finite_or_none(row[output])
                    results.append({
                        "auto_adjust": auto_adjust,
                        "dd52": "binary_ge_-10pct" if dd_binary else "continuous_final",
                        "aggregation": aggregation,
                        "output": output,
                        "value": value,
                        "difference": None if value is None else value - EXPECTED,
                        "abs_difference": None if value is None else abs(value - EXPECTED),
                        "z": finite_or_none(row["z"]),
                        "mu": finite_or_none(row["mu"]),
                        "sigma": finite_or_none(row["sigma"]),
                        "downloaded": len(closes),
                    })
    results.sort(key=lambda x: float("inf") if x["abs_difference"] is None else x["abs_difference"])
    payload = {
        "research_only": True,
        "target_date": TARGET.date().isoformat(),
        "historical_value": EXPECTED,
        "purpose": "Identify whether the recovered 2026-08-28 value belongs to a pre-standardization generation rather than final MC15/logistic MC57.",
        "best": results[:12],
        "all": results,
    }
    (OUT / "mc57_generation_compare_20260828.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["best"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
