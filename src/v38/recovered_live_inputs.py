from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-recovered-live-inputs-1.0.1"
NQSAR_SCHEMA = "v38.nqsar.1"
CLASSIFICATION_SCHEMA = "v38.classifications.1"
THEME_SCHEMA = "v38.theme_scores.1"
ANALYTICS_SCHEMA = "v38.analytics.1"
VALID_STATES = {"Blue", "Green", "Yellow", "Red"}

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


def _psar(high: np.ndarray, low: np.ndarray, *, step: float = 0.02, maximum: float = 0.08) -> np.ndarray:
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
    bsu = bsd = 99
    prev_rsi: float | None = None
    states: list[str] = []
    for i in range(len(close)):
        bsu = 0 if (i > 0 and above[i] and not above[i - 1]) else bsu + 1
        bsd = 0 if (i > 0 and (not above[i]) and above[i - 1]) else bsd + 1
        current_rsi = float(rsi[i]) if np.isfinite(rsi[i]) else float("nan")
        drsi = current_rsi - prev_rsi if prev_rsi is not None and np.isfinite(current_rsi) else 0.0
        if above[i]:
            if state == "Blue":
                state = "Green" if close[i] < ema21[i] else "Blue"
            else:
                state = "Blue" if current_rsi > 52 and bsu >= 2 and drsi <= 3.0 else "Green"
        else:
            if state == "Red":
                state = "Yellow" if current_rsi > 50 else "Red"
            else:
                state = "Red" if current_rsi < 47 and bsd >= 2 and drsi >= -3.0 else "Yellow"
        states.append(state)
        if np.isfinite(current_rsi):
            prev_rsi = current_rsi
    return pd.DataFrame({"close": close, "psar": sar, "ema21": ema21, "rsi14": rsi, "state": states}, index=f.index)


def build_recovered_nqsar(market_inputs: dict[str, Any], *, session_date: str, generated_at: str) -> dict[str, Any]:
    series = market_inputs.get("series") if isinstance(market_inputs, dict) else None
    rows = series.get("NQ=F") if isinstance(series, dict) else None
    if not isinstance(rows, list):
        raise RecoveredInputError("market_inputs NQ=F series missing")
    records = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str) or row["date"] > session_date:
            continue
        high, low, close = (_finite(row.get(k)) for k in ("high", "low", "close"))
        if high is not None and low is not None and close is not None:
            records.append({"date": row["date"], "high": high, "low": low, "close": close})
    if not records:
        raise RecoveredInputError("no usable NQ=F completed bars")
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    state_frame = _nqsar_state_series(frame.set_index("date").sort_index())
    target = pd.Timestamp(session_date)
    if target not in state_frame.index:
        raise RecoveredInputError(f"NQSAR target bar missing: {session_date}")
    row = state_frame.loc[target]
    state = str(row["state"])
    history = [
        {
            "date": pd.Timestamp(idx).strftime("%Y-%m-%d"), "state": str(h["state"]),
            "close": float(h["close"]), "psar": float(h["psar"]), "ema21": float(h["ema21"]),
            "rsi14": float(h["rsi14"]) if np.isfinite(h["rsi14"]) else None,
        }
        for idx, h in state_frame.tail(260).iterrows()
    ]
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
        "reason": "TradingView NQ1!/EXP_STATE_ID source is unavailable; legacy Yahoo NQ=F fallback estimate only.",
        "parameters": {
            "psar_start": 0.02, "psar_increment": 0.02, "psar_max": 0.08,
            "ema": 21, "rsi": "Wilder14",
            "green_to_blue": "RSI>52 and bars_since_flip>=2 and dRSI<=3",
            "blue_to_green": "Close<EMA21",
            "yellow_to_red": "RSI<47 and bars_since_flip>=2 and dRSI>=-3",
            "red_to_yellow": "RSI>50",
        },
        "latest": {
            "close": float(row["close"]), "psar": float(row["psar"]), "ema21": float(row["ema21"]),
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
        out[symbol.split(":", 1)[-1].strip().upper()] = dict(zip(columns, values))
    return out


def build_classifications(rs: dict[str, Any], fundamentals: dict[str, dict[str, Any]], *, session_date: str, generated_at: str) -> dict[str, Any]:
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
            and market_cap is not None and market_cap < CLINICAL_MARKET_CAP_MAX
            and revenue is not None and revenue < CLINICAL_REVENUE_TTM_MAX
        )
        output.append({
            "ticker": ticker, "industry": industry or None, "market_cap": market_cap,
            "revenue_ttm": revenue, "structural_clinical_biotech": excluded,
            "classification_reason": "INDUSTRY_AND_MCAP_AND_REVENUE_TTM" if excluded else "NOT_EXCLUDED_OR_REVENUE_MISSING_FAIL_OPEN",
        })
    return {
        "session_date": session_date, "generated_at": generated_at,
        "coverage": len(output) / max(1, len(rows)),
        "source": "TradingView america/scan fundamentals + current V38 RS universe",
        "schema_version": CLASSIFICATION_SCHEMA, "calculation_version": CALCULATION_VERSION, "status": "READY",
        "rules": {
            "industries": sorted(CLINICAL_INDUSTRIES), "market_cap_lt": CLINICAL_MARKET_CAP_MAX,
            "revenue_ttm_lt": CLINICAL_REVENUE_TTM_MAX, "all_conditions_required": True,
            "revenue_missing_policy": "fail_open_not_excluded",
        },
        "coverage_detail": {"rs_rows": len(rows), "classified_rows": len(output), "revenue_ttm_available": complete_revenue},
        "rows": output,
    }


def build_neutral_theme_scores(rs: dict[str, Any], *, session_date: str, generated_at: str) -> dict[str, Any]:
    rows = rs.get("rows") if isinstance(rs, dict) else None
    if not isinstance(rows, list):
        raise RecoveredInputError("rs rows missing for theme neutralization")
    out = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        ticker = str(raw.get("ticker") or "").strip().upper()
        if ticker:
            out.append({"ticker": ticker, "peer_theme_score": NEUTRAL_THEME_SCORE, "theme_status": "MISSING_NEUTRAL", "theme_id": None})
    return {
        "session_date": session_date, "generated_at": generated_at, "coverage": 1.0,
        "source": "final-v38-missing-theme-neutral-policy; no Sector/Industry substitution",
        "schema_version": THEME_SCHEMA, "calculation_version": CALCULATION_VERSION, "status": "READY",
        "rows": out,
        "rules": {"missing_theme_score": NEUTRAL_THEME_SCORE, "sector_substitution": False, "industry_substitution": False, "loo_required_when_theme_exists": True},
        "note": "This fills only the final V38 missing-theme neutral value. It does not claim recovered fine-theme membership.",
    }


def build_rotation_diagnostics(rs: dict[str, Any], *, session_date: str, generated_at: str) -> dict[str, Any]:
    rows = [row for row in rs.get("rows", []) if isinstance(row, dict)] if isinstance(rs, dict) else []
    def groups(key: str):
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            label = str(row.get(key) or "").strip()
            if label:
                grouped.setdefault(label, []).append(row)
        out = []
        for label, members in grouped.items():
            if len(members) < 3:
                continue
            ret20 = [_finite(x.get("ret20")) for x in members]
            ret63 = [_finite(x.get("ret63")) for x in members]
            rs63 = [_finite(x.get("rs63")) for x in members]
            ret20 = [x for x in ret20 if x is not None]; ret63 = [x for x in ret63 if x is not None]; rs63 = [x for x in rs63 if x is not None]
            leaders = sorted(members, key=lambda x: (-(_finite(x.get("rs63")) or -1e100), str(x.get("ticker") or "")))[:3]
            out.append({
                "group": label, "member_count": len(members),
                "ret20_avg": sum(ret20) / len(ret20) if ret20 else None,
                "ret63_avg": sum(ret63) / len(ret63) if ret63 else None,
                "rs63_avg": sum(rs63) / len(rs63) if rs63 else None,
                "leaders": [str(x.get("ticker")) for x in leaders],
                "trade_input": False,
            })
        out.sort(key=lambda x: (-(x["ret20_avg"] if x["ret20_avg"] is not None else -1e100), x["group"]))
        return out
    return {
        "session_date": session_date, "generated_at": generated_at, "coverage": rs.get("coverage"),
        "source": "current RS universe sector/industry diagnostics",
        "schema_version": ANALYTICS_SCHEMA, "calculation_version": CALCULATION_VERSION, "status": "READY",
        "trade_input": False,
        "note": "Sector/Industry rotation diagnostics only; not the final fine-grained Peer Theme Score.",
        "sector": groups("sector"), "industry": groups("industry"),
    }


def write_json(path: str | Path, obj: dict[str, Any]) -> Path:
    return atomic_write_json(Path(path), obj)
