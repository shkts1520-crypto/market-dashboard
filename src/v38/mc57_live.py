from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .freshness import atomic_write_json
from .mc57_engine import MC57_METRICS, calibrate_mc57

SCHEMA_VERSION = "v38.mc57.1"
CALCULATION_VERSION = "v38-mc57-live-1.0.0"
PRICE_START = "2004-01-01"
EXPECTED_ETF_COUNT = 57

# Recovered from the legacy V38 MICRO_ETFS source used by the dashboard, plus
# QQQE. ^VIX6M was fetched alongside these symbols but is not an ETF and is not
# part of MC57.
FIXED_57_ETFS = (
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
    "QQQE",
)


class MC57LiveError(RuntimeError):
    """Raised when the live MC57 publication contract cannot be satisfied."""


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _normalise_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def _symbol_frame(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = [str(x) for x in raw.columns.get_level_values(0)]
        level1 = [str(x) for x in raw.columns.get_level_values(1)]
        if symbol in level0:
            return _normalise_frame(raw[symbol])
        if symbol in level1:
            return _normalise_frame(raw.xs(symbol, axis=1, level=1))
        return pd.DataFrame()
    return _normalise_frame(raw)


def adjusted_close_series(frame: pd.DataFrame, *, target_session: str) -> pd.Series:
    """Return explicit Yahoo adjusted close through the requested completed session.

    Downloads use auto_adjust=False. Adj Close is therefore required explicitly;
    this avoids depending on yfinance's changing auto_adjust default.
    """
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    f = _normalise_frame(frame)
    if "adj_close" not in f.columns:
        return pd.Series(dtype=float)
    s = pd.to_numeric(f["adj_close"], errors="coerce").dropna()
    if s.empty:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s.loc[s.index <= pd.Timestamp(target_session)]
    return s[(s > 0) & np.isfinite(s)]


def _download_batch(yf: Any, symbols: list[str]) -> pd.DataFrame:
    return yf.download(
        tickers=symbols,
        start=PRICE_START,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=16,
        timeout=30,
    )


def download_fixed57_adjusted_closes(
    yf: Any,
    *,
    target_session: str,
    batch_size: int = 12,
) -> tuple[dict[str, pd.Series], dict[str, Any]]:
    try:
        target = pd.Timestamp(target_session).strftime("%Y-%m-%d")
    except Exception as exc:
        raise MC57LiveError(f"invalid target_session: {target_session}") from exc
    if len(FIXED_57_ETFS) != EXPECTED_ETF_COUNT or len(set(FIXED_57_ETFS)) != EXPECTED_ETF_COUNT:
        raise MC57LiveError("fixed MC57 universe must contain exactly 57 unique ETFs")

    closes: dict[str, pd.Series] = {}
    for offset in range(0, len(FIXED_57_ETFS), batch_size):
        batch = list(FIXED_57_ETFS[offset:offset + batch_size])
        try:
            raw = _download_batch(yf, batch)
        except Exception:
            raw = pd.DataFrame()
        for symbol in batch:
            s = adjusted_close_series(_symbol_frame(raw, symbol), target_session=target)
            if not s.empty:
                closes[symbol] = s

    missing_target = [
        symbol for symbol in FIXED_57_ETFS
        if symbol not in closes or pd.Timestamp(target) not in closes[symbol].index
    ]
    # One exact-symbol retry for provider partial responses. No symbol substitution.
    for symbol in list(missing_target):
        try:
            raw = _download_batch(yf, [symbol])
        except Exception:
            continue
        s = adjusted_close_series(_symbol_frame(raw, symbol), target_session=target)
        if not s.empty:
            closes[symbol] = s

    missing_target = [
        symbol for symbol in FIXED_57_ETFS
        if symbol not in closes or pd.Timestamp(target) not in closes[symbol].index
    ]
    if missing_target:
        raise MC57LiveError(
            "fixed57 current-session coverage incomplete: "
            f"{EXPECTED_ETF_COUNT - len(missing_target)}/{EXPECTED_ETF_COUNT}; "
            + ",".join(missing_target)
        )

    return closes, {
        "fixed_etf_count": EXPECTED_ETF_COUNT,
        "downloaded_history_count": len(closes),
        "current_close_count": EXPECTED_ETF_COUNT - len(missing_target),
        "current_close_coverage": (EXPECTED_ETF_COUNT - len(missing_target)) / EXPECTED_ETF_COUNT,
        "missing_current": missing_target,
    }


def _binary(cond: pd.Series, valid: pd.Series) -> pd.Series:
    return cond.astype(float).mul(100.0).where(valid)


def _ticker_metric_series(close: pd.Series) -> dict[str, pd.Series]:
    c = close.astype(float).sort_index()
    sma10 = c.rolling(10, min_periods=10).mean()
    sma20 = c.rolling(20, min_periods=20).mean()
    sma50 = c.rolling(50, min_periods=50).mean()
    sma200 = c.rolling(200, min_periods=200).mean()
    ret5 = c.pct_change(5, fill_method=None)
    ret21 = c.pct_change(21, fill_method=None)
    ret63 = c.pct_change(63, fill_method=None)
    ret252 = c.pct_change(252, fill_method=None)
    high52 = c.rolling(252, min_periods=252).max()
    dd52 = c / high52 - 1.0
    dd52_score = ((dd52 + 0.30) / 0.25 * 100.0).clip(0.0, 100.0).where(dd52.notna())
    return {
        "close_gt_sma10": _binary(c > sma10, sma10.notna()),
        "close_gt_sma20": _binary(c > sma20, sma20.notna()),
        "close_gt_sma50": _binary(c > sma50, sma50.notna()),
        "close_gt_sma200": _binary(c > sma200, sma200.notna()),
        "ret5_gt_0": _binary(ret5 > 0, ret5.notna()),
        "ret21_gt_0": _binary(ret21 > 0, ret21.notna()),
        "ret63_gt_0": _binary(ret63 > 0, ret63.notna()),
        "ret252_gt_0": _binary(ret252 > 0, ret252.notna()),
        "sma20_gt_sma50": _binary(sma20 > sma50, sma20.notna() & sma50.notna()),
        "sma50_gt_sma200": _binary(sma50 > sma200, sma50.notna() & sma200.notna()),
        "sma50_gt_sma50_shift20": _binary(
            sma50 > sma50.shift(20),
            sma50.notna() & sma50.shift(20).notna(),
        ),
        "dd52_continuous_score": dd52_score,
    }


def calculate_mc57_panel(
    closes: dict[str, pd.Series],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    if not closes:
        raise MC57LiveError("no fixed57 adjusted close history")
    per_ticker = {
        symbol: _ticker_metric_series(closes[symbol])
        for symbol in FIXED_57_ETFS
        if symbol in closes and not closes[symbol].empty
    }
    metric_frames: dict[str, pd.DataFrame] = {}
    metric_scores: dict[str, pd.Series] = {}
    for metric in MC57_METRICS:
        frame = pd.concat(
            {symbol: metrics[metric] for symbol, metrics in per_ticker.items()},
            axis=1,
        ).sort_index()
        metric_frames[metric] = frame
        metric_scores[metric] = frame.mean(axis=1, skipna=True)
    daily_scores = pd.DataFrame(metric_scores).sort_index()
    raw = daily_scores.mean(axis=1, skipna=False)
    calibrated = calibrate_mc57(raw)
    return calibrated.join(daily_scores, how="left"), metric_frames


def _reference_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified_reference(
    reference_path: str | Path,
    fixture_path: str | Path,
) -> dict[str, Any]:
    ref_path = Path(reference_path)
    gold_path = Path(fixture_path)
    if not ref_path.is_file() or not gold_path.is_file():
        raise MC57LiveError("MC57 verified reference and golden fixture are required")
    ref = json.loads(ref_path.read_text(encoding="utf-8"))
    if not isinstance(ref, dict) or ref.get("verified") is not True:
        raise MC57LiveError("MC57 reference is not verified")
    universe = ref.get("etf_universe")
    if universe != list(FIXED_57_ETFS):
        raise MC57LiveError("MC57 reference universe differs from fixed source universe")
    actual_sha = _reference_sha256(gold_path)
    if ref.get("golden_fixture_sha256") != actual_sha:
        raise MC57LiveError("MC57 golden fixture SHA256 mismatch")
    return ref


def build_mc57_object(
    *,
    closes: dict[str, pd.Series],
    target_session: str,
    generated_at: str,
    reference: dict[str, Any],
    fetch_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = pd.Timestamp(target_session).strftime("%Y-%m-%d")
    panel, metric_frames = calculate_mc57_panel(closes)
    day = pd.Timestamp(target)
    if day not in panel.index:
        raise MC57LiveError(f"MC57 target session missing from panel: {target}")
    row = panel.loc[day]
    required = ("raw", "ema2_raw", "mu_prior", "sigma_prior", "z", "mc57")
    values = {key: _finite(row.get(key)) for key in required}
    if any(values[key] is None for key in required):
        raise MC57LiveError(f"MC57 target is not calibrated/finite for {target}: {values}")
    if values["sigma_prior"] is None or values["sigma_prior"] <= 0:
        raise MC57LiveError("MC57 sigma must be positive")

    current_close = sum(
        int(symbol in closes and day in closes[symbol].index and _finite(closes[symbol].loc[day]) is not None)
        for symbol in FIXED_57_ETFS
    )
    if current_close != EXPECTED_ETF_COUNT:
        raise MC57LiveError(f"MC57 current close coverage must be 57/57, got {current_close}/57")

    scores: dict[str, float] = {}
    valid_counts: dict[str, int] = {}
    for metric in MC57_METRICS:
        score = _finite(row.get(metric))
        if score is None:
            raise MC57LiveError(f"MC57 metric score missing at target: {metric}")
        scores[metric] = score
        frame = metric_frames[metric]
        valid_counts[metric] = int(frame.loc[day].notna().sum()) if day in frame.index else 0
        if valid_counts[metric] <= 0:
            raise MC57LiveError(f"MC57 metric has zero valid ETF observations: {metric}")

    history = []
    hist = panel.loc[panel.index <= day, ["raw", "ema2_raw", "z", "mc57"]].dropna(subset=["mc57"]).tail(260)
    for idx, h in hist.iterrows():
        history.append({
            "date": pd.Timestamp(idx).strftime("%Y-%m-%d"),
            "raw": float(h["raw"]),
            "ema2_raw": float(h["ema2_raw"]),
            "z": float(h["z"]),
            "mc57": float(h["mc57"]),
        })

    coverage = current_close / EXPECTED_ETF_COUNT
    return {
        "session_date": target,
        "generated_at": generated_at,
        "coverage": coverage,
        "source": "Yahoo Finance via yfinance 0.2.66; auto_adjust=False with explicit Adj Close; fixed recovered 56 MICRO_ETFS + QQQE",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "mc57": values["mc57"],
        "raw": values["raw"],
        "ema2_raw": values["ema2_raw"],
        "mu_prior": values["mu_prior"],
        "sigma_prior": values["sigma_prior"],
        "z": values["z"],
        "metric_scores": scores,
        "coverage_detail": {
            "fixed_etf_count": EXPECTED_ETF_COUNT,
            "current_close_count": current_close,
            "current_close_coverage": coverage,
            "metric_valid_counts": valid_counts,
            "fetch": dict(fetch_stats or {}),
        },
        "etf_universe": list(FIXED_57_ETFS),
        "price_contract": {
            "vendor": "Yahoo Finance",
            "client": "yfinance==0.2.66",
            "download_auto_adjust": False,
            "calculation_price": "Adj Close",
            "history_start": PRICE_START,
            "calendar": "observed US ETF daily sessions cut to Dashboard completed session",
            "timezone": "America/New_York",
            "completed_session_cutoff_et": "16:15",
            "target_session_source": "data/state.json (QQQ+SPY common completed session)",
            "symbol_substitution": "none",
            "missing_metric_policy": "exclude missing ETF from that metric denominator",
            "target_close_policy": "require all fixed 57 ETFs present for current session",
        },
        "reference": {
            "reference_schema_version": reference.get("schema_version"),
            "verification_kind": reference.get("verification_kind"),
            "golden_fixture_sha256": reference.get("golden_fixture_sha256"),
        },
        "history": history,
    }


def write_mc57_json(path: str | Path, obj: dict[str, Any]) -> Path:
    return atomic_write_json(Path(path), obj)
