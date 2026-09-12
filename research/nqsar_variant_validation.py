#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("research_out")
GOLDEN = {
    "2026-07-17": "Blue",   # recovered EXP_STATE_ID=1
    "2026-07-20": "Yellow", # recovered EXP_STATE_ID=2
}


def _flat_yf(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        if "NQ=F" in df.columns.get_level_values(-1):
            df = df.xs("NQ=F", axis=1, level=-1)
        else:
            df.columns = [str(x[0]) for x in df.columns]
    out = df[["High", "Low", "Close"]].copy().dropna()
    out.index = pd.DatetimeIndex(out.index).tz_localize(None).normalize()
    return out[~out.index.duplicated(keep="last")].sort_index()


def download_window(asof: str, *, auto_adjust: bool, warmup_days: int) -> pd.DataFrame:
    end = pd.Timestamp(asof) + pd.Timedelta(days=1)
    start = pd.Timestamp(asof) - pd.Timedelta(days=warmup_days)
    df = yf.download(
        "NQ=F",
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        interval="1d",
        auto_adjust=auto_adjust,
        actions=False,
        progress=False,
        threads=False,
        timeout=30,
    )
    if df is None or len(df) == 0:
        raise RuntimeError(f"no NQ=F data for {asof}")
    return _flat_yf(df)


def psar_recovered(h: np.ndarray, l: np.ndarray, step=0.02, max_af=0.08) -> np.ndarray:
    # Exact structure recovered from the old V38 dashboard helper.
    n = len(h)
    sar = np.full(n, np.nan)
    bull = True
    af = step
    ep = float(l[0])
    sar[0] = float(l[0])
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if bull:
            if l[i] < sar[i]:
                bull = False
                sar[i] = ep
                ep = float(l[i])
                af = step
            elif h[i] > ep:
                ep = float(h[i])
                af = min(af + step, max_af)
        else:
            if h[i] > sar[i]:
                bull = True
                sar[i] = ep
                ep = float(h[i])
                af = step
            elif l[i] < ep:
                ep = float(l[i])
                af = min(af + step, max_af)
    return sar


def psar_pine_like(h: np.ndarray, l: np.ndarray, c: np.ndarray, start=0.02, inc=0.02, max_af=0.08) -> np.ndarray:
    # Pine/TradingView ta.sar-style initialization + prior-two-bar clamping.
    n = len(c)
    result = np.full(n, np.nan)
    if n < 2:
        return result
    below = bool(c[1] > c[0])
    extreme = float(h[1] if below else l[1])
    sar = float(l[0] if below else h[0])
    af = start
    result[0] = sar
    result[1] = sar
    first_trend_bar = True
    for i in range(2, n):
        sar = sar + af * (extreme - sar)
        first_trend_bar = False
        if below:
            if sar > l[i]:
                first_trend_bar = True
                below = False
                sar = extreme
                extreme = float(l[i])
                af = start
        else:
            if sar < h[i]:
                first_trend_bar = True
                below = True
                sar = extreme
                extreme = float(h[i])
                af = start
        if not first_trend_bar:
            if below and h[i] > extreme:
                extreme = float(h[i])
                af = min(af + inc, max_af)
            elif (not below) and l[i] < extreme:
                extreme = float(l[i])
                af = min(af + inc, max_af)
        if below:
            sar = min(sar, float(l[i - 1]), float(l[i - 2]))
        else:
            sar = max(sar, float(h[i - 1]), float(h[i - 2]))
        result[i] = sar
    return result


def rsi_old_python(close: pd.Series, period=14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    ru = up.ewm(alpha=1 / period, adjust=False).mean()
    rd = dn.ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd)


def rma_pine(x: pd.Series, length: int) -> pd.Series:
    arr = x.to_numpy(float)
    out = np.full(len(arr), np.nan)
    valid = np.where(np.isfinite(arr))[0]
    if len(valid) < length:
        return pd.Series(out, index=x.index)
    # Pine RMA seed = SMA of first length valid observations, then alpha=1/length recursion.
    seed_pos = valid[length - 1]
    seed_vals = arr[valid[:length]]
    out[seed_pos] = float(np.mean(seed_vals))
    alpha = 1.0 / length
    prev = out[seed_pos]
    for i in range(seed_pos + 1, len(arr)):
        if np.isfinite(arr[i]):
            prev = alpha * arr[i] + (1 - alpha) * prev
        out[i] = prev
    return pd.Series(out, index=x.index)


def rsi_pine(close: pd.Series, period=14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    ru = rma_pine(up, period)
    rd = rma_pine(dn, period)
    rs = ru / rd
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.where(rd != 0, 100.0)
    return rsi


def run_fsm(df: pd.DataFrame, *, psar_kind: str, rsi_kind: str, symmetric_yellow_red: bool) -> pd.DataFrame:
    close = df["Close"].astype(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = close.to_numpy(float)
    sar_arr = psar_recovered(h, l) if psar_kind == "recovered" else psar_pine_like(h, l, c)
    sar = pd.Series(sar_arr, index=df.index)
    ema21 = close.ewm(span=21, adjust=False).mean()
    rsi = rsi_old_python(close) if rsi_kind == "old" else rsi_pine(close)
    above = close > sar
    first_valid = next((i for i in range(len(df)) if np.isfinite(sar.iloc[i])), 0)
    state = "Green" if bool(above.iloc[first_valid]) else "Yellow"
    bsu = bsd = 99
    prev_rsi = None
    states = []
    for i in range(len(df)):
        if i > 0 and bool(above.iloc[i]) and not bool(above.iloc[i - 1]):
            bsu = 0
        else:
            bsu += 1
        if i > 0 and (not bool(above.iloc[i])) and bool(above.iloc[i - 1]):
            bsd = 0
        else:
            bsd += 1
        rv = float(rsi.iloc[i]) if pd.notna(rsi.iloc[i]) else None
        drsi = 0.0 if prev_rsi is None or rv is None else rv - prev_rsi
        if rv is not None:
            if bool(above.iloc[i]):
                if state == "Blue":
                    state = "Green" if close.iloc[i] < ema21.iloc[i] else "Blue"
                else:
                    state = "Blue" if rv > 52 and bsu >= 2 and drsi <= 3 else "Green"
            else:
                if state == "Red":
                    state = "Yellow" if rv > 50 else "Red"
                else:
                    drsi_ok = abs(drsi) <= 3 if symmetric_yellow_red else drsi >= -3
                    state = "Red" if rv < 47 and bsd >= 2 and drsi_ok else "Yellow"
            prev_rsi = rv
        states.append(state)
    return pd.DataFrame({"Close": close, "PSAR": sar, "EMA21": ema21, "RSI14": rsi, "Above": above, "State": states})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    variants = []
    for adjust in (False, True):
        for warmup in (400, 800):
            for psar_kind in ("recovered", "pine_like"):
                for rsi_kind in ("old", "pine"):
                    for symmetric in (False, True):
                        variants.append((adjust, warmup, psar_kind, rsi_kind, symmetric))

    results = {}
    scores = {str(v): 0 for v in variants}
    for asof, expected in GOLDEN.items():
        results[asof] = {"expected": expected, "variants": {}}
        cache = {}
        for adjust, warmup, psar_kind, rsi_kind, symmetric in variants:
            data_key = (adjust, warmup)
            if data_key not in cache:
                cache[data_key] = download_window(asof, auto_adjust=adjust, warmup_days=warmup)
            df = cache[data_key]
            out = run_fsm(df, psar_kind=psar_kind, rsi_kind=rsi_kind, symmetric_yellow_red=symmetric)
            dt = pd.Timestamp(asof)
            state = str(out.loc[dt, "State"]) if dt in out.index else None
            key = f"adjust={adjust}|warmup={warmup}|psar={psar_kind}|rsi={rsi_kind}|sym={symmetric}"
            match = state == expected
            scores[str((adjust, warmup, psar_kind, rsi_kind, symmetric))] += int(match)
            row = out.loc[dt] if dt in out.index else None
            results[asof]["variants"][key] = {
                "state": state,
                "match": match,
                "close": None if row is None else float(row["Close"]),
                "psar": None if row is None or pd.isna(row["PSAR"]) else float(row["PSAR"]),
                "ema21": None if row is None or pd.isna(row["EMA21"]) else float(row["EMA21"]),
                "rsi14": None if row is None or pd.isna(row["RSI14"]) else float(row["RSI14"]),
                "above": None if row is None else bool(row["Above"]),
            }

    ranked = []
    for v in variants:
        adjust, warmup, psar_kind, rsi_kind, symmetric = v
        key = str(v)
        ranked.append({
            "matches": scores[key],
            "total": len(GOLDEN),
            "auto_adjust": adjust,
            "warmup_days": warmup,
            "psar": psar_kind,
            "rsi": rsi_kind,
            "yellow_red_symmetric": symmetric,
        })
    ranked.sort(key=lambda x: (-x["matches"], x["auto_adjust"], x["warmup_days"], x["psar"], x["rsi"], x["yellow_red_symmetric"]))
    payload = {
        "research_only": True,
        "production_authority": False,
        "golden": "recovered 2026 EXP_STATE_ID only",
        "golden_dates": GOLDEN,
        "variant_count": len(variants),
        "ranked": ranked,
        "results": results,
        "notes": [
            "Recovered old V38 estimator used NQ=F, 1y, auto_adjust=False and a simplified PSAR helper.",
            "pine_like PSAR adds TradingView-style initialization and prior-two-bar clamps.",
            "pine RSI uses RMA seeded by SMA; old RSI uses pandas ewm recursion.",
            "Only two verified 2026 EXP_STATE_ID labels are available, so even 2/2 is not sufficient for production promotion.",
            "NQ=F continuous-futures stitching can still differ from TradingView NQ1!.",
        ],
    }
    (OUT / "nqsar_variant_validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"top": ranked[:8], "golden": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
