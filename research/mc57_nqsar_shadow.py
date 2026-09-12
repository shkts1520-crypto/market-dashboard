#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf

# RESEARCH ONLY. Never import this file from production.
# Candidate 57 = the recovered 56-theme ETF set + QQQE.
THEME_56 = [
    "SMH", "XSD", "DRAM", "SOXX",
    "DTCR", "IGV", "WCLD", "SKYY",
    "CIBR", "AIQ", "QTUM", "BOTZ", "ARKW",
    "XBI", "IHI", "PPH", "GNOM",
    "KBE", "KRE", "IAI", "KIE",
    "XOP", "OIH", "XES",
    "TAN", "ICLN", "GRID", "FAN",
    "URA", "NLR", "LIT", "HYDR",
    "GDX", "SIL", "COPX", "XME", "SLX", "REMX",
    "ITA", "SHLD", "XAR",
    "JETS", "IYT", "BOAT",
    "XHB", "PAVE", "PKB",
    "XRT", "IBUY", "PEJ",
    "BLOK", "WGMI", "DRIV",
    "MOO", "PHO", "WOOD",
]
CANDIDATE_57 = THEME_56 + ["QQQE"]
MC57_METRICS = (
    "close_gt_sma10",
    "close_gt_sma20",
    "close_gt_sma50",
    "close_gt_sma200",
    "ret5_gt_0",
    "ret21_gt_0",
    "ret63_gt_0",
    "ret252_gt_0",
    "sma20_gt_sma50",
    "sma50_gt_sma200",
    "sma50_gt_sma50_shift20",
    "dd52_continuous_score",
)
CALIBRATION_LOOKBACK = 3780
OUT = Path("research_out")


def finite_or_none(value):
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def download_adjusted_closes(tickers: Iterable[str]) -> dict[str, pd.Series]:
    tickers = list(tickers)
    found: dict[str, pd.Series] = {}
    # Smaller batches reduce one bad/young ETF poisoning a whole Yahoo request.
    for start in range(0, len(tickers), 12):
        batch = tickers[start : start + 12]
        data = yf.download(
            batch,
            start="2004-01-01",
            interval="1d",
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=True,
            group_by="ticker",
            timeout=30,
        )
        if data is None or len(data) == 0:
            continue
        if isinstance(data.columns, pd.MultiIndex):
            outer = set(str(x) for x in data.columns.get_level_values(0))
            for ticker in batch:
                if ticker not in outer:
                    continue
                sub = data[ticker]
                if "Close" not in sub:
                    continue
                s = pd.to_numeric(sub["Close"], errors="coerce").dropna()
                if not s.empty:
                    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
                    found[ticker] = s[~s.index.duplicated(keep="last")].sort_index()
        else:
            # Defensive path; normally batches above produce MultiIndex columns.
            if len(batch) == 1 and "Close" in data:
                s = pd.to_numeric(data["Close"], errors="coerce").dropna()
                if not s.empty:
                    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
                    found[batch[0]] = s[~s.index.duplicated(keep="last")].sort_index()

    # One retry for missing names; useful for transient Yahoo chunk failures.
    for ticker in [t for t in tickers if t not in found]:
        try:
            data = yf.download(
                ticker,
                start="2004-01-01",
                interval="1d",
                auto_adjust=True,
                actions=False,
                progress=False,
                threads=False,
                timeout=30,
            )
            if data is None or len(data) == 0:
                continue
            if isinstance(data.columns, pd.MultiIndex):
                close = data.xs("Close", axis=1, level=-1)
                if close.shape[1] != 1:
                    continue
                s = close.iloc[:, 0]
            else:
                s = data["Close"]
            s = pd.to_numeric(s, errors="coerce").dropna()
            if not s.empty:
                s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
                found[ticker] = s[~s.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
    return found


def binary_score(condition: pd.Series, valid: pd.Series) -> pd.Series:
    return condition.astype(float).mul(100.0).where(valid)


def ticker_metric_series(close: pd.Series) -> dict[str, pd.Series]:
    close = close.astype(float).sort_index()
    sma10 = close.rolling(10, min_periods=10).mean()
    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    ret5 = close.pct_change(5, fill_method=None)
    ret21 = close.pct_change(21, fill_method=None)
    ret63 = close.pct_change(63, fill_method=None)
    ret252 = close.pct_change(252, fill_method=None)
    peak252 = close.rolling(252, min_periods=252).max()
    dd52 = close.div(peak252).sub(1.0)
    dd_score = dd52.add(0.30).div(0.25).mul(100.0).clip(0.0, 100.0)
    return {
        "close_gt_sma10": binary_score(close > sma10, sma10.notna()),
        "close_gt_sma20": binary_score(close > sma20, sma20.notna()),
        "close_gt_sma50": binary_score(close > sma50, sma50.notna()),
        "close_gt_sma200": binary_score(close > sma200, sma200.notna()),
        "ret5_gt_0": binary_score(ret5 > 0.0, ret5.notna()),
        "ret21_gt_0": binary_score(ret21 > 0.0, ret21.notna()),
        "ret63_gt_0": binary_score(ret63 > 0.0, ret63.notna()),
        "ret252_gt_0": binary_score(ret252 > 0.0, ret252.notna()),
        "sma20_gt_sma50": binary_score(sma20 > sma50, sma20.notna() & sma50.notna()),
        "sma50_gt_sma200": binary_score(sma50 > sma200, sma50.notna() & sma200.notna()),
        "sma50_gt_sma50_shift20": binary_score(sma50 > sma50.shift(20), sma50.notna() & sma50.shift(20).notna()),
        "dd52_continuous_score": dd_score.where(dd52.notna()),
    }


def calculate_mc57(closes: dict[str, pd.Series], universe: list[str]) -> tuple[pd.DataFrame, dict]:
    metric_by_ticker = {t: ticker_metric_series(closes[t]) for t in universe if t in closes}
    score_cols = {}
    count_cols = {}
    for metric in MC57_METRICS:
        frame = pd.concat(
            {t: metrics[metric] for t, metrics in metric_by_ticker.items()}, axis=1
        ).sort_index()
        score_cols[metric] = frame.mean(axis=1, skipna=True)
        count_cols[metric] = frame.count(axis=1).astype(float)
    scores = pd.DataFrame(score_cols).sort_index()
    counts = pd.DataFrame(count_cols).reindex(scores.index)
    raw = scores.mean(axis=1, skipna=False)
    ema2 = raw.ewm(span=2, adjust=False).mean()
    mu = ema2.shift(1).rolling(CALIBRATION_LOOKBACK, min_periods=CALIBRATION_LOOKBACK).mean()
    sigma = ema2.shift(1).rolling(CALIBRATION_LOOKBACK, min_periods=CALIBRATION_LOOKBACK).std(ddof=0)
    z = (ema2 - mu).div(sigma.where(sigma > 0.0))
    mc57 = 100.0 / (1.0 + np.power(3.0, -z))
    panel = pd.concat(
        {
            "raw": raw,
            "ema2_raw": ema2,
            "mu_prior": mu,
            "sigma_prior": sigma,
            "z": z,
            "mc57": mc57,
        },
        axis=1,
    )
    close_frame = pd.concat({t: closes[t] for t in universe if t in closes}, axis=1).sort_index()
    latest = panel.index.max()
    latest_scores = scores.loc[latest] if latest in scores.index else pd.Series(dtype=float)
    latest_counts = counts.loc[latest] if latest in counts.index else pd.Series(dtype=float)
    diag = {
        "universe_size": len(universe),
        "downloaded": len([t for t in universe if t in closes]),
        "missing_tickers": [t for t in universe if t not in closes],
        "latest_date": latest.date().isoformat(),
        "latest_close_count": int(close_frame.loc[latest].notna().sum()) if latest in close_frame.index else 0,
        "latest_close_coverage": float(close_frame.loc[latest].notna().mean()) if latest in close_frame.index else 0.0,
        "first_calibrated_date": (
            panel["mc57"].first_valid_index().date().isoformat()
            if panel["mc57"].first_valid_index() is not None else None
        ),
        "latest": {k: finite_or_none(panel.loc[latest, k]) for k in panel.columns},
        "latest_metric_scores": {k: finite_or_none(latest_scores.get(k)) for k in MC57_METRICS},
        "latest_metric_valid_counts": {k: int(latest_counts.get(k, 0)) for k in MC57_METRICS},
        "inception": {
            t: {
                "first": closes[t].index.min().date().isoformat(),
                "last": closes[t].index.max().date().isoformat(),
                "rows": int(closes[t].shape[0]),
            }
            for t in universe if t in closes
        },
    }
    return panel, diag


def psar_recovered(high: np.ndarray, low: np.ndarray, step: float = 0.02, max_af: float = 0.08) -> np.ndarray:
    # Recovered V38/OniMine helper structure, with max_af corrected to the frozen 0.08 setting.
    n = len(high)
    sar = np.full(n, np.nan, dtype=float)
    if n == 0:
        return sar
    bull = True
    af = step
    ep = float(low[0])
    sar[0] = float(low[0])
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if bull:
            if low[i] < sar[i]:
                bull = False
                sar[i] = ep
                ep = float(low[i])
                af = step
            elif high[i] > ep:
                ep = float(high[i])
                af = min(af + step, max_af)
        else:
            if high[i] > sar[i]:
                bull = True
                sar[i] = ep
                ep = float(high[i])
                af = step
            elif low[i] < ep:
                ep = float(low[i])
                af = min(af + step, max_af)
    return sar


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain.div(avg_loss.replace(0.0, np.nan))
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    return rsi


def nqsar_states(frame: pd.DataFrame, symmetric_yellow_red: bool) -> pd.DataFrame:
    frame = frame[["High", "Low", "Close"]].dropna().copy()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    close = frame["Close"].astype(float)
    sar = pd.Series(
        psar_recovered(frame["High"].to_numpy(float), frame["Low"].to_numpy(float), 0.02, 0.08),
        index=frame.index,
    )
    ema21 = close.ewm(span=21, adjust=False).mean()
    rsi = wilder_rsi(close, 14)
    above = close > sar
    state = "Green" if bool(above.iloc[0]) else "Yellow"
    bsu = 99
    bsd = 99
    prev_rsi = None
    states: list[str] = []
    drsis: list[float] = []
    for i, dt in enumerate(frame.index):
        if i > 0 and bool(above.iloc[i]) and not bool(above.iloc[i - 1]):
            bsu = 0
        else:
            bsu += 1
        if i > 0 and not bool(above.iloc[i]) and bool(above.iloc[i - 1]):
            bsd = 0
        else:
            bsd += 1
        rv = finite_or_none(rsi.iloc[i])
        drsi = 0.0 if prev_rsi is None or rv is None else rv - prev_rsi
        drsis.append(drsi)
        if rv is not None:
            if bool(above.iloc[i]):
                if state == "Blue":
                    state = "Green" if close.iloc[i] < ema21.iloc[i] else "Blue"
                else:
                    state = "Blue" if (rv > 52.0 and bsu >= 2 and drsi <= 3.0) else "Green"
            else:
                if state == "Red":
                    state = "Yellow" if rv > 50.0 else "Red"
                else:
                    drsi_ok = abs(drsi) <= 3.0 if symmetric_yellow_red else drsi >= -3.0
                    state = "Red" if (rv < 47.0 and bsd >= 2 and drsi_ok) else "Yellow"
            prev_rsi = rv
        states.append(state)
    return pd.DataFrame(
        {
            "close": close,
            "psar": sar,
            "ema21": ema21,
            "rsi14": rsi,
            "drsi": drsis,
            "above_psar": above,
            "state": states,
        },
        index=frame.index,
    )


def download_nq() -> pd.DataFrame:
    data = yf.download(
        "NQ=F",
        period="2y",
        interval="1d",
        auto_adjust=True,
        actions=False,
        progress=False,
        threads=False,
        timeout=30,
    )
    if data is None or len(data) == 0:
        raise RuntimeError("NQ=F download returned no rows")
    if isinstance(data.columns, pd.MultiIndex):
        # yfinance may return (Price, Ticker) for one symbol.
        data.columns = [str(a) for a, _ in data.columns]
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    assert len(THEME_56) == 56 and len(set(THEME_56)) == 56
    assert len(CANDIDATE_57) == 57 and len(set(CANDIDATE_57)) == 57

    closes = download_adjusted_closes(CANDIDATE_57)
    panel57, diag57 = calculate_mc57(closes, CANDIDATE_57)
    panel56, diag56 = calculate_mc57(closes, THEME_56)
    latest_common = min(panel57.index.max(), panel56.index.max())
    mc57_sensitivity = {
        "date": latest_common.date().isoformat(),
        "candidate57_mc57": finite_or_none(panel57.loc[latest_common, "mc57"]),
        "theme56_mc57": finite_or_none(panel56.loc[latest_common, "mc57"]),
    }
    if mc57_sensitivity["candidate57_mc57"] is not None and mc57_sensitivity["theme56_mc57"] is not None:
        mc57_sensitivity["difference_points"] = (
            mc57_sensitivity["candidate57_mc57"] - mc57_sensitivity["theme56_mc57"]
        )
    else:
        mc57_sensitivity["difference_points"] = None

    nq = download_nq()
    legacy = nqsar_states(nq, symmetric_yellow_red=False)
    symmetric = nqsar_states(nq, symmetric_yellow_red=True)
    joined = legacy.add_prefix("legacy_").join(symmetric.add_prefix("symmetric_"), how="inner")
    golden = {
        "2026-07-17": "Blue",   # EXP_STATE_ID=1
        "2026-07-20": "Yellow", # EXP_STATE_ID=2
    }
    golden_check = {}
    for ds, expected in golden.items():
        dt = pd.Timestamp(ds)
        golden_check[ds] = {
            "expected": expected,
            "legacy": str(legacy.loc[dt, "state"]) if dt in legacy.index else None,
            "symmetric": str(symmetric.loc[dt, "state"]) if dt in symmetric.index else None,
            "legacy_match": bool(dt in legacy.index and legacy.loc[dt, "state"] == expected),
            "symmetric_match": bool(dt in symmetric.index and symmetric.loc[dt, "state"] == expected),
        }
    diff_mask = joined["legacy_state"] != joined["symmetric_state"]
    diff_dates = [d.date().isoformat() for d in joined.index[diff_mask]]

    result = {
        "research_only": True,
        "production_authority": False,
        "mc57": {
            "candidate_universe_basis": "recovered 56 MICRO_ETFS + QQQE; hypothesis pending historical reproduction",
            "candidate_57": CANDIDATE_57,
            "theme_56": THEME_56,
            "price_mode": "Yahoo Finance auto_adjust=True",
            "formula": "12 cross-sectional participation metrics -> equal-weight Raw -> EMA2 -> prior 3780-session mu/sigma ddof=0 -> 100/(1+3^-Z)",
            "candidate57": diag57,
            "theme56": diag56,
            "sensitivity": mc57_sensitivity,
            "caveats": [
                "57-ticker identity is still a recovery hypothesis until reproduced against a verified historical MC57/MC15 fixture.",
                "ETF inception dates vary; missing values are excluded per metric, so historical cross-sectional membership changes over time.",
                "Yahoo adjusted history may differ from the original production vendor/stitching.",
            ],
        },
        "nqsar": {
            "input": "Yahoo continuous NQ=F daily, 2y, auto_adjust=True",
            "psar": {"start": 0.02, "increment": 0.02, "max": 0.08},
            "ema_length": 21,
            "rsi": "Wilder 14",
            "confirm_bars_after_sar_flip": 2,
            "legacy_yellow_red_drsi": "dRSI >= -3",
            "screenshot_yellow_red_drsi": "abs(dRSI) <= 3",
            "golden_source": "recovered nq.csv EXP_STATE_ID labels",
            "golden_check": golden_check,
            "variant_difference_count": int(diff_mask.sum()),
            "variant_difference_dates": diff_dates,
            "latest": {
                "date": legacy.index.max().date().isoformat(),
                "legacy": str(legacy.iloc[-1]["state"]),
                "symmetric": str(symmetric.iloc[-1]["state"]),
            },
            "caveats": [
                "Yahoo NQ=F continuous-futures stitching can differ from TradingView NQ1! used by the authoritative source.",
                "Recovered Python PSAR helper is a reconstruction; direct sar_state/EXP_STATE_ID remains higher authority.",
                "Two recovered golden dates are not enough by themselves to authorize production inference.",
            ],
        },
    }

    (OUT / "mc57_nqsar_shadow.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    panel57.tail(260).to_csv(OUT / "mc57_candidate57_tail.csv", index_label="date")
    joined.tail(260).to_csv(OUT / "nqsar_shadow_tail.csv", index_label="date")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
