from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import display_observations as base
from .display_observation_history import exact_old_top20
from .freshness import atomic_write_json
from .live_acquisition import select_yfinance_symbol_frame


def _sentiment_market(session: str) -> dict[str, pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError:
        return {}

    cutoff = pd.Timestamp(session)
    symbols = list(base.SENTIMENT_TICKERS)
    frames: dict[str, pd.DataFrame] = {}
    raw = pd.DataFrame()
    for attempt in range(3):
        try:
            raw = yf.download(
                symbols,
                period="5y",
                interval="1d",
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                timeout=30,
            )
            if not raw.empty:
                break
        except Exception:
            raw = pd.DataFrame()
        time.sleep(1.5 * (attempt + 1))

    def clean(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty:
            return pd.DataFrame()
        out = frame.copy()
        out.columns = [str(column).strip().lower().replace(" ", "_") for column in out.columns]
        if "close" not in out.columns:
            return pd.DataFrame()
        out.index = pd.to_datetime(out.index, errors="coerce").tz_localize(None)
        out = out[out.index.notna() & (out.index <= cutoff)]
        # base.build_sentiment is recovered from source and expects the historical
        # Close/Volume shape, so restore those names after common normalization.
        rename = {"close": "Close", "volume": "Volume", "open": "Open", "high": "High", "low": "Low"}
        return out.rename(columns={key: value for key, value in rename.items() if key in out.columns})

    for symbol in symbols:
        frame = clean(select_yfinance_symbol_frame(raw, symbol))
        if len(frame) >= 120:
            frames[symbol] = frame
            continue
        # Batch Yahoo responses can omit one leveraged ETF. Retry exactly that
        # symbol instead of declaring the whole sentiment component unavailable.
        for attempt in range(2):
            try:
                retry = yf.download(
                    [symbol],
                    period="5y",
                    interval="1d",
                    progress=False,
                    auto_adjust=True,
                    group_by="ticker",
                    threads=False,
                    timeout=30,
                )
            except Exception:
                retry = pd.DataFrame()
            frame = clean(select_yfinance_symbol_frame(retry, symbol))
            if len(frame) >= 120:
                frames[symbol] = frame
                break
            time.sleep(1.0 * (attempt + 1))
    return frames


def fetch_sentiment(data_dir: str | Path, *, session: str) -> dict[str, Any]:
    root = Path(data_dir)
    market = _sentiment_market(session)
    fear_greed, put_call = base._fetch_cnn(session)
    naaim = base._fetch_naaim(session)
    parabolic = base._load_parabolic_history(root, session)
    result = base.build_sentiment(
        market,
        session=session,
        fear_greed=fear_greed,
        put_call=put_call,
        naaim=naaim,
        parabolic=parabolic,
    )
    result["acquisition"] = {
        "market_symbols": sorted(market),
        "cnn_fear_greed_points": int(len(fear_greed)),
        "cnn_put_call_points": int(len(put_call)),
        "naaim_points": int(len(naaim)),
        "parabolic_points": int(len(parabolic)),
    }
    return result


def _reversal_current(tickers: list[str], session: str) -> dict[str, dict[str, float]]:
    if not tickers:
        return {}
    try:
        import yfinance as yf
    except ImportError:
        return {}
    cutoff = pd.Timestamp(session)
    raw = pd.DataFrame()
    for attempt in range(3):
        try:
            raw = yf.download(
                tickers,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                timeout=30,
            )
            if not raw.empty:
                break
        except Exception:
            raw = pd.DataFrame()
        time.sleep(1.5 * (attempt + 1))

    def measure(frame: pd.DataFrame) -> dict[str, float] | None:
        if frame is None or frame.empty:
            return None
        out = frame.copy()
        out.columns = [str(column).strip().lower().replace(" ", "_") for column in out.columns]
        if "close" not in out.columns or "volume" not in out.columns:
            return None
        out.index = pd.to_datetime(out.index, errors="coerce").tz_localize(None)
        out = out[out.index.notna() & (out.index <= cutoff)]
        close = pd.to_numeric(out["close"], errors="coerce").dropna()
        volume = pd.to_numeric(out["volume"], errors="coerce").reindex(close.index)
        if len(close) < 51:
            return None
        ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        vol50 = volume.iloc[-50:].mean()
        current_volume = volume.iloc[-1]
        if not math.isfinite(float(ema21)) or not math.isfinite(float(vol50)) or vol50 <= 0:
            return None
        rvol = float(current_volume / vol50) if math.isfinite(float(current_volume)) else float("nan")
        return {"close": float(close.iloc[-1]), "ema21": float(ema21), "rvol": rvol}

    observations: dict[str, dict[str, float]] = {}
    for ticker in tickers:
        measured = measure(select_yfinance_symbol_frame(raw, ticker))
        if measured is not None:
            observations[ticker] = measured
            continue
        try:
            retry = yf.download(
                [ticker],
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=False,
                timeout=30,
            )
        except Exception:
            retry = pd.DataFrame()
        measured = measure(select_yfinance_symbol_frame(retry, ticker))
        if measured is not None:
            observations[ticker] = measured
    return observations


def build_reversal_leaders(data_dir: str | Path, market_series: dict[str, Any], *, session: str) -> dict[str, Any]:
    root = Path(data_dir)
    qqq = base._market_frame(market_series.get("QQQ"))
    if len(qqq) < 60:
        return {"status": "DATA_REQUIRED", "reason": "QQQ_HISTORY_TOO_SHORT"}
    close = qqq["close"].dropna()
    window = close.iloc[-90:] if len(close) >= 90 else close
    current = float(close.iloc[-1])
    values = window.to_numpy(dtype=float)
    low_index = int(np.argmin(values))
    low = float(values[low_index])
    prior_peak = float(np.max(values[: low_index + 1]))
    running_high = float(np.max(values))
    dd_at_low = low / prior_peak - 1.0
    off_low = current / low - 1.0 if low > 0 else 0.0
    dd_now = current / running_high - 1.0
    active = bool(dd_at_low <= -0.10 and off_low >= 0.05 and low_index < len(values) - 2)

    old_date, old = exact_old_top20(root, lag=42)
    base_result: dict[str, Any] = {
        "status": "READY",
        "active": active,
        "dd_now": dd_now,
        "off_low": off_low,
        "dd_at_low": dd_at_low,
        "old_leader_date": old_date,
        "trading_gate_eligible": False,
        "scope": "DISPLAY_OBSERVATION_ONLY",
    }
    if not active:
        base_result.update({"leaders": [], "ready_count": 0, "candidate_count": 0})
        return base_result
    if len(old) != 20:
        return {
            **base_result,
            "status": "DATA_REQUIRED",
            "reason": f"EXACT_OLD_RS63_TOP20_INCOMPLETE:{len(old)}",
            "leaders": [],
        }

    tickers = [str(row.get("ticker") or "").strip().upper() for row in old]
    observations = _reversal_current(tickers, session)
    current_rs = base._current_rs_map(root)
    leaders: list[dict[str, Any]] = []
    for old_row in old:
        ticker = str(old_row.get("ticker") or "").strip().upper()
        observation = observations.get(ticker)
        if not ticker or observation is None:
            continue
        reclaim = observation["close"] > observation["ema21"]
        rvol = base._finite(observation.get("rvol"))
        volume_recovered = bool(rvol is not None and rvol >= 1.0)
        now = current_rs.get(ticker, {})
        leaders.append({
            "ticker": ticker,
            "old_rs63": base._finite(old_row.get("rs63")),
            "rs63": base._finite(now.get("rs63")),
            "rs189": base._finite(now.get("rs189")),
            "reclaim21": bool(reclaim),
            "volume_recovered": volume_recovered,
            "rvol": rvol,
            "score": (2 if reclaim else 0) + (1 if volume_recovered else 0),
        })
    if len(leaders) != 20:
        return {
            **base_result,
            "status": "DATA_REQUIRED",
            "reason": f"CURRENT_OLD_LEADER_OBSERVATIONS_INCOMPLETE:{len(leaders)}",
            "leaders": leaders,
        }
    leaders.sort(key=lambda row: (-int(row["score"]), -float(row.get("rs63") or 0.0), row["ticker"]))
    base_result.update({
        "leaders": leaders,
        "ready_count": sum(1 for row in leaders if row["reclaim21"] and row["volume_recovered"]),
        "candidate_count": 20,
    })
    return base_result


def materialize_display_observations(
    data_dir: str | Path,
    *,
    session_date: str,
    generated_at: str,
) -> Path:
    root = Path(data_dir)
    market_series = base._market_series(root)
    sections = {
        "regime_history": base.update_nqsar_history(root, session=session_date, generated_at=generated_at),
        "net_liquidity": base.fetch_net_liquidity(session=session_date),
        "sentiment": fetch_sentiment(root, session=session_date),
        "reversal_leaders": build_reversal_leaders(root, market_series, session=session_date),
        "ftd_proxy": base.build_ftd_proxy(market_series),
    }
    blocked = [name for name, section in sections.items() if section.get("status") != "READY"]
    obj = {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": (len(sections) - len(blocked)) / len(sections),
        "source": "recovered source-defined display observations",
        "schema_version": base.SCHEMA_VERSION,
        "calculation_version": base.CALCULATION_VERSION,
        "status": "READY" if not blocked else "DATA_REQUIRED",
        "trading_gate_eligible": False,
        "blocked_sections": blocked,
        **sections,
    }
    path = root / "display_observations.json"
    atomic_write_json(path, obj)
    if blocked:
        reasons = {name: sections[name].get("reason") for name in blocked}
        details = {
            "sentiment_acquisition": sections["sentiment"].get("acquisition"),
            "reversal_active": sections["reversal_leaders"].get("active"),
            "reversal_old_date": sections["reversal_leaders"].get("old_leader_date"),
        }
        raise RuntimeError(f"display observations incomplete: {reasons}; {details}")
    return path
