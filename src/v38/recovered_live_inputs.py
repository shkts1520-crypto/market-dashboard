from __future__ import annotations

import csv
import json
import math
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-recovered-live-inputs-1.0.0"
NQSAR_SCHEMA = "v38.nqsar.1"
CLASSIFICATION_SCHEMA = "v38.classifications.1"
THEME_SCHEMA = "v38.theme_scores.1"
ANALYTICS_SCHEMA = "v38.analytics.1"
VALID_STATES = {"Blue", "Green", "Yellow", "Red"}

# Final V38 Structural Clinical Biotech contract recovered in the final audit.
CLINICAL_INDUSTRIES = {"Biotechnology", "Pharmaceuticals: Other"}
CLINICAL_MARKET_CAP_MAX = 10_000_000_000.0
CLINICAL_REVENUE_TTM_MAX = 50_000_000.0
NEUTRAL_THEME_SCORE = 50.0


class RecoveredInputError(RuntimeError):
    pass


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _read_json(path: str | Path) -> dict[str, Any] | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _psar(high: np.ndarray, low: np.ndarray, *, step: float = 0.02, maximum: float = 0.08) -> np.ndarray:
    """Legacy OniMine-compatible PSAR core with the final 0.02/0.02/0.08 parameters."""
    n = len(high)
    if n == 0 or len(low) != n:
        return np.array([], dtype=float)
    sar = np.zeros(n, dtype=float)
    bull = True
    af = float(step)
    ep = float(low[0])
    sar[0] = float(low[0])
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if bull:
            if low[i] < sar[i]:
                bull = False
                sar[i] = ep
                ep = float(low[i])
                af = float(step)
            elif high[i] > ep:
                ep = float(high[i])
                af = min(af + step, maximum)
        else:
            if high[i] > sar[i]:
                bull = True
                sar[i] = ep
                ep = float(high[i])
                af = float(step)
            elif low[i] < ep:
                ep = float(low[i])
                af = min(af + step, maximum)
    return sar


def _nqsar_state_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the recovered OniMine FSM to completed NQ daily bars.

    This intentionally reproduces the legacy live fallback. It is marked as a
    recovered estimate because Yahoo NQ=F is not identical to the missing
    TradingView NQ1! authoritative export.
    """
    required = {"high", "low", "close"}
    if frame is None or frame.empty or not required.issubset(frame.columns):
        raise RecoveredInputError("NQ frame requires high/low/close")
    f = frame.copy().sort_index()
    for col in required:
        f[col] = pd.to_numeric(f[col], errors="coerce")
    f = f.dropna(subset=["high", "low", "close"])
    if len(f) < 60:
        raise RecoveredInputError("NQ frame requires at least 60 completed bars")

    high = f["high"].to_numpy(dtype=float)
    low = f["low"].to_numpy(dtype=float)
    close = f["close"].to_numpy(dtype=float)
    sar = _psar(high, low, step=0.02, maximum=0.08)
    ema21 = f["close"].ewm(span=21, adjust=False).mean().to_numpy(dtype=float)
    delta = f["close"].diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    ru = up.ewm(alpha=1 / 14, adjust=False).mean()
    rd = down.ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100.0 - 100.0 / (1.0 + ru / rd)).to_numpy(dtype=float)

    above = close > sar
    state = "Green" if bool(above[0]) else "Yellow"
    bars_since_up = 99
    bars_since_down = 99
    prev_rsi: float | None = None
    states: list[str] = []
    for i in range(len(close)):
        bars_since_up = 0 if (i > 0 and above[i] and not above[i - 1]) else bars_since_up + 1
        bars_since_down = 0 if (i > 0 and (not above[i]) and above[i - 1]) else bars_since_down + 1
        current_rsi = float(rsi[i]) if np.isfinite(rsi[i]) else float("nan")
        drsi = current_rsi - prev_rsi if prev_rsi is not None and np.isfinite(current_rsi) else 0.0
        if above[i]:
            if state == "Blue":
                state = "Green" if close[i] < ema21[i] else "Blue"
            else:
                state = "Blue" if (current_rsi > 52 and bars_since_up >= 2 and drsi <= 3.0) else "Green"
        else:
            if state == "Red":
                state = "Yellow" if current_rsi > 50 else "Red"
            else:
                state = "Red" if (current_rsi < 47 and bars_since_down >= 2 and drsi >= -3.0) else "Yellow"
        states.append(state)
        if np.isfinite(current_rsi):
            prev_rsi = current_rsi

    out = pd.DataFrame(
        {
            "close": close,
            "psar": sar,
            "ema21": ema21,
            "rsi14": rsi,
            "state": states,
        },
        index=f.index,
    )
    return out


def build_recovered_nqsar(
    market_inputs: dict[str, Any],
    *,
    session_date: str,
    generated_at: str,
) -> dict[str, Any]:
    series = market_inputs.get("series") if isinstance(market_inputs, dict) else None
    rows = series.get("NQ=F") if isinstance(series, dict) else None
    if not isinstance(rows, list):
        raise RecoveredInputError("market_inputs NQ=F series missing")
    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str):
            continue
        if row["date"] > session_date:
            continue
        high, low, close = (_finite(row.get(k)) for k in ("high", "low", "close"))
        if high is None or low is None or close is None:
            continue
        records.append({"date": row["date"], "high": high, "low": low, "close": close})
    if not records:
        raise RecoveredInputError("no usable NQ=F completed bars")
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").sort_index()
    state_frame = _nqsar_state_series(frame)
    target = pd.Timestamp(session_date)
    if target not in state_frame.index:
        raise RecoveredInputError(f"NQSAR target bar missing: {session_date}")
    row = state_frame.loc[target]
    state = str(row["state"])
    if state not in VALID_STATES:
        raise RecoveredInputError(f"invalid recovered NQSAR state: {state}")
    history = []
    for idx, h in state_frame.tail(260).iterrows():
        history.append(
            {
                "date": pd.Timestamp(idx).strftime("%Y-%m-%d"),
                "state": str(h["state"]),
                "close": float(h["close"]),
                "psar": float(h["psar"]),
                "ema21": float(h["ema21"]),
                "rsi14": float(h["rsi14"]) if np.isfinite(h["rsi14"]) else None,
            }
        )
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": 1.0,
        "source": "recovered-legacy-live-fallback:Yahoo NQ=F completed daily bars",
        "schema_version": NQSAR_SCHEMA,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "state": state,
        "input_kind": "RECOVERED_YAHOO_FSM_ESTIMATE",
        "authoritative_exact": False,
        "reason": "TradingView NQ1!/EXP_STATE_ID source is unavailable; this is the legacy production fallback, not an exact authority replacement.",
        "parameters": {
            "psar_start": 0.02,
            "psar_increment": 0.02,
            "psar_max": 0.08,
            "ema": 21,
            "rsi": "Wilder14",
            "green_to_blue": "RSI>52 and bars_since_flip>=2 and dRSI<=3",
            "blue_to_green": "Close<EMA21",
            "yellow_to_red": "RSI<47 and bars_since_flip>=2 and dRSI>=-3",
            "red_to_yellow": "RSI>50",
        },
        "latest": {
            "close": float(row["close"]),
            "psar": float(row["psar"]),
            "ema21": float(row["ema21"]),
            "rsi14": float(row["rsi14"]) if np.isfinite(row["rsi14"]) else None,
        },
        "history": history,
    }


def fetch_tradingview_fundamentals(timeout: int = 30) -> dict[str, dict[str, Any]]:
    columns = ["name", "market_cap_basic", "industry", "total_revenue_ttm"]
    payload = {
        "filter": [
            {"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE", "AMEX"]},
            {"left": "type", "operation": "equal", "right": "stock"},
        ],
        "options": {"lang": "en"},
        "markets": ["america"],
        "columns": columns,
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 10000],
    }
    req = urllib.request.Request(
        "https://scanner.tradingview.com/america/scan",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 V38Dashboard/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        obj = json.loads(response.read().decode("utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for item in obj.get("data", []):
        values = item.get("d") if isinstance(item, dict) else None
        symbol = item.get("s") if isinstance(item, dict) else None
        if not isinstance(values, list) or len(values) != len(columns) or not isinstance(symbol, str):
            continue
        ticker = symbol.split(":", 1)[-1].strip().upper()
        row = dict(zip(columns, values))
        out[ticker] = row
    return out


def build_classifications(
    rs: dict[str, Any],
    fundamentals: dict[str, dict[str, Any]],
    *,
    session_date: str,
    generated_at: str,
) -> dict[str, Any]:
    rows = rs.get("rows") if isinstance(rs, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RecoveredInputError("rs rows missing for classifications")
    output = []
    complete_revenue = 0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        ticker = str(raw.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        f = fundamentals.get(ticker, {})
        industry = str(f.get("industry") or raw.get("industry") or "").strip()
        market_cap = _finite(f.get("market_cap_basic"))
        revenue = _finite(f.get("total_revenue_ttm"))
        if revenue is not None:
            complete_revenue += 1
        excluded = bool(
            industry in CLINICAL_INDUSTRIES
            and market_cap is not None
            and market_cap < CLINICAL_MARKET_CAP_MAX
            and revenue is not None
            and revenue < CLINICAL_REVENUE_TTM_MAX
        )
        output.append(
            {
                "ticker": ticker,
                "industry": industry or None,
                "market_cap": market_cap,
                "revenue_ttm": revenue,
                "structural_clinical_biotech": excluded,
                "classification_reason": (
                    "INDUSTRY_AND_MCAP_AND_REVENUE_TTM" if excluded
                    else "NOT_EXCLUDED_OR_REVENUE_MISSING_FAIL_OPEN"
                ),
            }
        )
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": len(output) / max(1, len(rows)),
        "source": "TradingView america/scan fundamentals + current V38 RS universe",
        "schema_version": CLASSIFICATION_SCHEMA,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "rules": {
            "industries": sorted(CLINICAL_INDUSTRIES),
            "market_cap_lt": CLINICAL_MARKET_CAP_MAX,
            "revenue_ttm_lt": CLINICAL_REVENUE_TTM_MAX,
            "all_conditions_required": True,
            "revenue_missing_policy": "fail_open_not_excluded",
        },
        "coverage_detail": {
            "rs_rows": len(rows),
            "classified_rows": len(output),
            "revenue_ttm_available": complete_revenue,
        },
        "rows": output,
    }


def _load_ohlcv_close(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame()
    cols = {str(c).strip().lower(): c for c in df.columns}
    if not {"date", "ticker", "close"}.issubset(cols):
        return pd.DataFrame()
    x = df[[cols["date"], cols["ticker"], cols["close"]]].copy()
    x.columns = ["date", "ticker", "close"]
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    x["ticker"] = x["ticker"].astype(str).str.strip().str.upper()
    x["close"] = pd.to_numeric(x["close"], errors="coerce")
    x = x.dropna(subset=["date", "ticker", "close"])
    if x.empty:
        return pd.DataFrame()
    return x.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()


def _percentile(values: pd.Series) -> pd.Series:
    return values.rank(pct=True, method="average") * 100.0


def _display_rotation_groups(rs_rows: list[dict[str, Any]], close: pd.DataFrame) -> list[dict[str, Any]]:
    by_industry: dict[str, list[str]] = defaultdict(list)
    rs63: dict[str, float] = {}
    for row in rs_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        industry = str(row.get("industry") or "").strip()
        value = _finite(row.get("rs63"))
        if ticker and industry and value is not None:
            by_industry[industry].append(ticker)
            rs63[ticker] = value
    groups = {name: sorted(set(members)) for name, members in by_industry.items() if len(set(members)) >= 3}
    if not groups:
        return []

    current_raw = pd.Series({name: float(np.median([rs63[t] for t in members if t in rs63])) for name, members in groups.items()})
    current_pct = _percentile(current_raw)

    above21: dict[str, float | None] = {}
    accel_raw: dict[str, float | None] = {name: None for name in groups}
    if not close.empty:
        ema21 = close.ewm(span=21, adjust=False).mean()
        if len(close) >= 1:
            last_close = close.iloc[-1]
            last_ema = ema21.iloc[-1]
            for name, members in groups.items():
                valid = [t for t in members if t in close.columns and pd.notna(last_close.get(t)) and pd.notna(last_ema.get(t))]
                above21[name] = (100.0 * sum(float(last_close[t]) > float(last_ema[t]) for t in valid) / len(valid)) if valid else None
        if len(close) >= 84:
            now_ret = close.iloc[-1] / close.shift(63).iloc[-1] - 1.0
            old_ret = close.iloc[-21] / close.shift(63).iloc[-21] - 1.0
            now_rs = _percentile(now_ret.dropna())
            old_rs = _percentile(old_ret.dropna())
            now_group = {}
            old_group = {}
            for name, members in groups.items():
                nv = [float(now_rs[t]) for t in members if t in now_rs.index and pd.notna(now_rs[t])]
                ov = [float(old_rs[t]) for t in members if t in old_rs.index and pd.notna(old_rs[t])]
                if nv:
                    now_group[name] = float(np.median(nv))
                if ov:
                    old_group[name] = float(np.median(ov))
            if now_group and old_group:
                now_rank = _percentile(pd.Series(now_group))
                old_rank = _percentile(pd.Series(old_group))
                for name in groups:
                    if name in now_rank.index and name in old_rank.index:
                        accel_raw[name] = float(now_rank[name] - old_rank[name])
    accel_series = pd.Series({k: v for k, v in accel_raw.items() if v is not None}, dtype=float)
    accel_pct = _percentile(accel_series) if not accel_series.empty else pd.Series(dtype=float)

    rows = []
    for name, members in groups.items():
        rows.append(
            {
                "theme": name,
                "group_kind": "TRADINGVIEW_INDUSTRY_DISPLAY_ONLY",
                "members": len(members),
                "theme_rs63_percentile": _finite(current_pct.get(name)),
                "rank_acceleration_20d": _finite(accel_raw.get(name)),
                "rank_acceleration_percentile": _finite(accel_pct.get(name)),
                "above21ema_pct": _finite(above21.get(name)),
                "note": "Display-only rotation group. Industry is not used as the final Peer Theme ranking substitute.",
            }
        )
    rows.sort(key=lambda r: (-(r.get("theme_rs63_percentile") or -1e9), r["theme"]))
    return rows


def build_theme_scores(
    rs: dict[str, Any],
    *,
    session_date: str,
    generated_at: str,
    ohlcv_path: str | Path | None = None,
) -> dict[str, Any]:
    rs_rows = rs.get("rows") if isinstance(rs, dict) else None
    if not isinstance(rs_rows, list) or not rs_rows:
        raise RecoveredInputError("rs rows missing for theme scores")
    # Final V38 explicitly says missing fine-theme data is neutral. The old full
    # sector_snapshot/s2t authority is not available in this repository, so do
    # not substitute TradingView Industry into the 30% trading score.
    rows = []
    for raw in rs_rows:
        if not isinstance(raw, dict):
            continue
        ticker = str(raw.get("ticker") or "").strip().upper()
        if ticker:
            rows.append(
                {
                    "ticker": ticker,
                    "peer_theme_score": NEUTRAL_THEME_SCORE,
                    "theme_status": "NEUTRAL_FINE_THEME_MAP_UNAVAILABLE",
                    "strict_loo": True,
                    "components": {"theme_rs63": None, "rank_acceleration_20d": None, "above21ema": None},
                }
            )
    close = _load_ohlcv_close(ohlcv_path) if ohlcv_path else pd.DataFrame()
    groups = _display_rotation_groups(rs_rows, close)
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": 1.0,
        "source": "final-V38-neutral-missing-theme + TradingView Industry display-only rotation",
        "schema_version": THEME_SCHEMA,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "peer_theme_contract": {
            "fine_theme_required": True,
            "strict_loo_required": True,
            "missing_theme_policy": "neutral_50",
            "industry_substitution_for_trading_score": False,
        },
        "rows": rows,
        "theme_groups": groups,
    }


def build_analytics(
    rs: dict[str, Any],
    breadth: dict[str, Any],
    market_inputs: dict[str, Any],
    mc57: dict[str, Any] | None,
    nqsar: dict[str, Any] | None,
    *,
    session_date: str,
    generated_at: str,
) -> dict[str, Any]:
    diagnostics = rs.get("market_diagnostics") if isinstance(rs, dict) else None
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": _finite(rs.get("coverage")) if isinstance(rs, dict) else None,
        "source": "derived:current V38 RS/breadth/market-inputs/MC57 + recovered legacy analytics",
        "schema_version": ANALYTICS_SCHEMA,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "breadth50": _finite(breadth.get("breadth50")) if isinstance(breadth, dict) else None,
        "breadth200": _finite(breadth.get("breadth200")) if isinstance(breadth, dict) else None,
        "market_diagnostics": diagnostics if isinstance(diagnostics, dict) else {},
        "mc57_history": list(mc57.get("history") or []) if isinstance(mc57, dict) else [],
        "nqsar_history": list(nqsar.get("history") or []) if isinstance(nqsar, dict) else [],
        "note": "Analytics are display-only unless the final V38 rules explicitly consume them.",
    }


def write_recovered_inputs(
    *,
    data_dir: str | Path,
    ohlcv_path: str | Path | None,
    generated_at: str,
    fetch_fundamentals: bool = True,
) -> tuple[Path, ...]:
    root = Path(data_dir)
    state = _read_json(root / "state.json")
    rs = _read_json(root / "rs.json")
    breadth = _read_json(root / "breadth.json")
    market_inputs = _read_json(root / "market_inputs.json")
    mc57 = _read_json(root / "mc57.json")
    if not state or not rs or not breadth or not market_inputs:
        raise RecoveredInputError("state/rs/breadth/market_inputs are required")
    session = str(state.get("session_date") or "")
    if not session:
        raise RecoveredInputError("state.session_date missing")

    nqsar = build_recovered_nqsar(market_inputs, session_date=session, generated_at=generated_at)
    fundamentals = fetch_tradingview_fundamentals() if fetch_fundamentals else {}
    classifications = build_classifications(rs, fundamentals, session_date=session, generated_at=generated_at)
    theme_scores = build_theme_scores(rs, session_date=session, generated_at=generated_at, ohlcv_path=ohlcv_path)
    analytics = build_analytics(rs, breadth, market_inputs, mc57, nqsar, session_date=session, generated_at=generated_at)

    paths = [
        atomic_write_json(root / "nqsar.json", nqsar),
        atomic_write_json(root / "classifications.json", classifications),
        atomic_write_json(root / "theme_scores.json", theme_scores),
        atomic_write_json(root / "analytics.json", analytics),
    ]
    return tuple(paths)
