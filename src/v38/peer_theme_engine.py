from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-peer-theme-1.0.0"
SCHEMA_VERSION = "v38.theme_scores.1"
INPUT_VERSION = "v38-peer-theme-inputs-1.0.0"
NEUTRAL = 50.0
MIN_PRICE = 5.0
MIN_DDV20 = 10_000_000.0


class PeerThemeError(RuntimeError):
    pass


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and int(value) in (0, 1):
        return bool(value)
    return None


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise PeerThemeError(f"invalid JSON: {path}") from exc
    if not isinstance(obj, dict):
        raise PeerThemeError(f"expected JSON object: {path}")
    return obj


def _rank_pct(values: dict[str, float | None]) -> dict[str, float]:
    valid = [(key, float(value)) for key, value in values.items() if _finite(value) is not None]
    if not valid:
        return {}
    frame = pd.DataFrame(valid, columns=["key", "value"])
    frame["pct"] = frame["value"].rank(method="average", pct=True) * 100.0
    return {str(row.key): float(row.pct) for row in frame.itertuples(index=False)}


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=float)))


def augment_rs_peer_theme_inputs(
    rs_path: str | Path,
    ohlcv_path: str | Path,
) -> dict[str, Any]:
    """Attach current EMA21 state and 20-session-ago RS63 to rs.json.

    The input OHLCV is the same adjusted, completed, split-checked history used by
    the stock adapter.  This does not change current RS/eligibility; it only adds
    the three inputs required by the adopted Peer Theme calculation.
    """
    rs_file = Path(rs_path)
    ohlcv_file = Path(ohlcv_path)
    rs = _read_json(rs_file)
    rows = rs.get("rows")
    session = str(rs.get("session_date") or "")
    if not isinstance(rows, list) or not session:
        raise PeerThemeError("rs rows/session_date are required")
    if not ohlcv_file.is_file():
        raise PeerThemeError(f"OHLCV file missing: {ohlcv_file}")

    d = pd.read_csv(ohlcv_file)
    d.columns = [str(col).strip().lower().replace(" ", "_") for col in d.columns]
    required = {"ticker", "date", "close", "volume"}
    if not required.issubset(d.columns):
        raise PeerThemeError("OHLCV requires ticker/date/close/volume")
    d["ticker"] = d["ticker"].astype(str).str.strip().str.upper()
    parsed = pd.to_datetime(d["date"], errors="coerce")
    d = d.loc[parsed.notna()].copy()
    d["date"] = parsed.loc[parsed.notna()].dt.strftime("%Y-%m-%d")
    d = d[d["date"] <= session].copy()
    for column in ("close", "volume"):
        d[column] = pd.to_numeric(d[column], errors="coerce")
    d = d.dropna(subset=["close", "volume"])
    d = d[(d["close"] > 0) & (d["volume"] >= 0)]
    if "is_complete" in d.columns:
        d = d[d["is_complete"].astype(str).str.lower().isin({"true", "1", "yes"})]
    if "split_checked" in d.columns:
        d = d[d["split_checked"].astype(str).str.lower().isin({"true", "1", "yes"})]
    if "split_anomaly" in d.columns:
        d = d[~d["split_anomaly"].astype(str).str.lower().isin({"true", "1", "yes"})]
    d = d.sort_values(["ticker", "date"], kind="mergesort").drop_duplicates(["ticker", "date"], keep="last")

    wanted = {str(row.get("ticker") or "").strip().upper() for row in rows if isinstance(row, dict)}
    d = d[d["ticker"].isin(wanted)]
    metrics: dict[str, dict[str, Any]] = {}
    prior_ret63: dict[str, float | None] = {}
    prior_base: dict[str, bool] = {}

    for ticker, frame in d.groupby("ticker", sort=False):
        frame = frame.sort_values("date", kind="mergesort")
        closes = frame["close"].astype(float).to_numpy()
        volumes = frame["volume"].astype(float).to_numpy()
        if len(closes) == 0 or str(frame.iloc[-1]["date"]) != session:
            continue
        ema21 = float(pd.Series(closes).ewm(span=21, adjust=False).mean().iloc[-1])
        current_close = float(closes[-1])
        item: dict[str, Any] = {
            "ema21": ema21,
            "above_ema21": bool(current_close > ema21),
            "rs63_20d": None,
            "peer_theme_input_status": "PARTIAL",
        }
        ret63_20d = None
        prior_price = None
        prior_ddv20 = None
        if len(closes) >= 84:
            prior_price = float(closes[-21])
            base63 = float(closes[-84])
            if base63 > 0:
                ret63_20d = prior_price / base63 - 1.0
        if len(closes) >= 40:
            prior_ddv20 = float(np.mean(closes[-40:-20] * volumes[-40:-20]))
        prior_ret63[ticker] = ret63_20d
        prior_base[ticker] = bool(
            ret63_20d is not None
            and prior_price is not None and prior_price >= MIN_PRICE
            and prior_ddv20 is not None and prior_ddv20 >= MIN_DDV20
        )
        item["ret63_20d"] = ret63_20d
        item["price_20d"] = prior_price
        item["ddv20_20d"] = prior_ddv20
        metrics[ticker] = item

    rank_input = {
        ticker: value if prior_base.get(ticker, False) else None
        for ticker, value in prior_ret63.items()
    }
    prior_ranks = _rank_pct(rank_input)

    complete = 0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        ticker = str(raw.get("ticker") or "").strip().upper()
        item = metrics.get(ticker)
        if item is None:
            raw["ema21"] = None
            raw["above_ema21"] = None
            raw["rs63_20d"] = None
            raw["peer_theme_input_status"] = "DATA_REQUIRED"
            continue
        raw.update(item)
        raw["rs63_20d"] = prior_ranks.get(ticker)
        raw["peer_theme_input_status"] = (
            "READY"
            if raw.get("above_ema21") is not None and _finite(raw.get("rs63_20d")) is not None
            else "PARTIAL"
        )
        complete += int(raw["peer_theme_input_status"] == "READY")

    rs["peer_theme_input_version"] = INPUT_VERSION
    rs["peer_theme_input_source"] = "same adjusted completed OHLCV as stock adapter; EMA21 span=21 adjust=False; prior RS63 at t-20"
    rs["peer_theme_input_coverage"] = complete / max(1, len(rows))
    atomic_write_json(rs_file, rs)
    return rs


def build_strict_loo_peer_theme_scores(
    rs: dict[str, Any],
    membership: dict[str, Any],
    *,
    session_date: str,
    generated_at: str,
) -> dict[str, Any]:
    if rs.get("session_date") != session_date or membership.get("session_date") != session_date:
        raise PeerThemeError("rs/theme membership session mismatch")
    rs_rows = rs.get("rows")
    member_rows = membership.get("rows")
    if not isinstance(rs_rows, list) or not isinstance(member_rows, list):
        raise PeerThemeError("rs.rows and membership.rows are required")

    by_ticker = {
        str(row.get("ticker") or "").strip().upper(): row
        for row in rs_rows if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }
    membership_by_ticker: dict[str, dict[str, Any]] = {}
    members_by_theme: dict[str, list[str]] = defaultdict(list)
    for row in member_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        theme = str(row.get("theme_id") or row.get("theme_name") or "").strip()
        if not ticker:
            continue
        membership_by_ticker[ticker] = row
        if theme:
            members_by_theme[theme].append(ticker)

    def theme_raw(theme: str, excluded: str | None = None) -> tuple[float | None, float | None, float | None, int]:
        current: list[float] = []
        prior: list[float] = []
        above: list[bool] = []
        peers = 0
        for ticker in members_by_theme.get(theme, []):
            if excluded and ticker == excluded:
                continue
            row = by_ticker.get(ticker)
            if row is None:
                continue
            peers += 1
            value = _finite(row.get("rs63"))
            if value is not None:
                current.append(value)
            value = _finite(row.get("rs63_20d"))
            if value is not None:
                prior.append(value)
            flag = _bool(row.get("above_ema21"))
            if flag is not None:
                above.append(flag)
        return (
            _median(current),
            _median(prior),
            (100.0 * sum(above) / len(above)) if above else None,
            peers,
        )

    themes = sorted(members_by_theme)
    baseline_raw = {theme: theme_raw(theme) for theme in themes}
    baseline_current = _rank_pct({theme: raw[0] for theme, raw in baseline_raw.items()})
    baseline_prior = _rank_pct({theme: raw[1] for theme, raw in baseline_raw.items()})
    baseline_accel_raw = {
        theme: (
            baseline_current[theme] - baseline_prior[theme]
            if theme in baseline_current and theme in baseline_prior else None
        )
        for theme in themes
    }

    output: list[dict[str, Any]] = []
    ready = partial = neutral = 0
    for ticker in sorted(by_ticker):
        membership_row = membership_by_ticker.get(ticker, {})
        theme = str(membership_row.get("theme_id") or membership_row.get("theme_name") or "").strip()
        base = {
            "ticker": ticker,
            "theme_id": theme or None,
            "theme_name": membership_row.get("theme_name") if theme else None,
            "major_theme": membership_row.get("major_theme") if theme else None,
            "tag_method": membership_row.get("tag_method"),
            "tag_confidence": membership_row.get("tag_confidence"),
        }
        if not theme or theme not in members_by_theme:
            output.append({
                **base,
                "peer_theme_score": NEUTRAL,
                "theme_rs63_score": NEUTRAL,
                "rank_acceleration_score": NEUTRAL,
                "above_ema21_score": NEUTRAL,
                "peer_count": 0,
                "theme_status": "MISSING_NEUTRAL",
            })
            neutral += 1
            continue

        current_raw, prior_raw, ema_score, peer_count = theme_raw(theme, excluded=ticker)
        current_map = {name: raw[0] for name, raw in baseline_raw.items()}
        prior_map = {name: raw[1] for name, raw in baseline_raw.items()}
        current_map[theme] = current_raw
        prior_map[theme] = prior_raw
        current_rank = _rank_pct(current_map)
        prior_rank = _rank_pct(prior_map)
        accel_raw = {
            name: (
                current_rank[name] - prior_rank[name]
                if name in current_rank and name in prior_rank else None
            )
            for name in themes
        }
        accel_rank = _rank_pct(accel_raw)

        a = current_rank.get(theme)
        b = accel_rank.get(theme)
        c = ema_score
        component_values = [a if a is not None else NEUTRAL, b if b is not None else NEUTRAL, c if c is not None else NEUTRAL]
        score = float(sum(component_values) / 3.0)
        missing_components = [
            name for name, value in (
                ("theme_rs63", a),
                ("rank_acceleration", b),
                ("above_ema21", c),
            ) if value is None
        ]
        status = "STRICT_LOO_READY" if not missing_components and peer_count > 0 else "STRICT_LOO_PARTIAL_NEUTRAL_COMPONENT"
        ready += int(status == "STRICT_LOO_READY")
        partial += int(status != "STRICT_LOO_READY")
        output.append({
            **base,
            "peer_theme_score": score,
            "theme_rs63_score": a if a is not None else NEUTRAL,
            "rank_acceleration_score": b if b is not None else NEUTRAL,
            "above_ema21_score": c if c is not None else NEUTRAL,
            "theme_rs63_raw_loo": current_raw,
            "theme_rs63_20d_raw_loo": prior_raw,
            "theme_rank_acceleration_raw": (
                current_rank.get(theme) - prior_rank.get(theme)
                if theme in current_rank and theme in prior_rank else None
            ),
            "peer_count": peer_count,
            "missing_components": missing_components,
            "theme_status": status,
        })

    total = len(output)
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": total / max(1, len(by_ticker)),
        "source": "derived:fine-theme membership + current/prior RS63 + EMA21; strict leave-one-out",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "loo_required": True,
        "rows": output,
        "coverage_detail": {
            "rs_rows": len(by_ticker),
            "score_rows": total,
            "strict_loo_ready": ready,
            "partial_neutral_component": partial,
            "missing_theme_neutral": neutral,
        },
        "rules": {
            "fine_theme_only": True,
            "sector_substitution": False,
            "industry_substitution": False,
            "strict_leave_one_out": True,
            "theme_rs63": "percentile of LOO median constituent RS63 across fine themes",
            "rank_acceleration": "percentile of 20-session change in fine-theme RS63 percentile, recomputed with candidate excluded",
            "above_ema21": "100 * LOO observable peers with Close>EMA21 / observable peers",
            "component_weights": [1 / 3, 1 / 3, 1 / 3],
            "missing_component_score": NEUTRAL,
            "missing_theme_score": NEUTRAL,
        },
    }


def write_strict_loo_peer_theme_scores(
    rs_path: str | Path,
    membership_path: str | Path,
    output_path: str | Path,
    *,
    session_date: str,
    generated_at: str,
) -> Path:
    obj = build_strict_loo_peer_theme_scores(
        _read_json(rs_path),
        _read_json(membership_path),
        session_date=session_date,
        generated_at=generated_at,
    )
    return atomic_write_json(output_path, obj)
