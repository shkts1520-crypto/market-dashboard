from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .mc57_engine import MC57_METRICS
from .mc57_live import calculate_mc57_panel

HISTORY_CONTRACT_VERSION = "v38.mc57.history.1"
HISTORY_LIMIT = 260
UI_HISTORY_LIMIT = 126

BREADTH_KEYS = {
    "sma20": "close_gt_sma20",
    "sma50": "close_gt_sma50",
    "sma200": "close_gt_sma200",
}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _point(date: str, value: Any) -> dict[str, Any] | None:
    x = _finite(value)
    if x is None:
        return None
    return {"date": date, "value": x}


def enrich_mc57_history(
    obj: dict[str, Any],
    *,
    closes: dict[str, pd.Series],
    target_session: str,
) -> dict[str, Any]:
    """Attach audited fixed-57 historical diagnostics to a READY MC57 object.

    The same adjusted-close histories and the same final MC57 engine are reused.
    No current-universe backfill or inferred stock breadth is introduced here.
    """
    target = pd.Timestamp(target_session)
    panel, _ = calculate_mc57_panel(closes)
    hist = panel.loc[panel.index <= target].dropna(subset=["mc57"]).tail(HISTORY_LIMIT)
    if hist.empty or target not in hist.index:
        raise ValueError(f"MC57 history target session missing: {target_session}")

    rich_history: list[dict[str, Any]] = []
    metric_history: dict[str, list[dict[str, Any]]] = {key: [] for key in MC57_METRICS}

    for idx, row in hist.iterrows():
        date = pd.Timestamp(idx).strftime("%Y-%m-%d")
        item: dict[str, Any] = {
            "date": date,
            "raw": _finite(row.get("raw")),
            "ema2_raw": _finite(row.get("ema2_raw")),
            "z": _finite(row.get("z")),
            "mc57": _finite(row.get("mc57")),
        }
        metrics: dict[str, float] = {}
        for metric in MC57_METRICS:
            value = _finite(row.get(metric))
            if value is None:
                continue
            metrics[metric] = value
            metric_history[metric].append({"date": date, "value": value})
        item["metrics"] = metrics
        for label, metric in BREADTH_KEYS.items():
            item[f"fixed57_breadth_{label}"] = metrics.get(metric)
        rich_history.append(item)

    latest = rich_history[-1]
    latest_metrics = latest.get("metrics") if isinstance(latest.get("metrics"), dict) else {}
    fixed57_breadth = {
        label: _finite(latest_metrics.get(metric))
        for label, metric in BREADTH_KEYS.items()
    }

    out = dict(obj)
    out["history_contract_version"] = HISTORY_CONTRACT_VERSION
    out["history_window_sessions"] = len(rich_history)
    out["ui_history_limit"] = UI_HISTORY_LIMIT
    out["history"] = rich_history
    out["metric_history"] = metric_history
    out["fixed57_breadth"] = fixed57_breadth
    return out


def build_mc57_ui_detail(
    mc57: dict[str, Any] | None,
    *,
    session: str,
) -> dict[str, Any]:
    if not isinstance(mc57, dict):
        return {"status": "DATA_REQUIRED", "reason": "MC57_FILE_MISSING", "series": {}, "metrics": {}}
    if mc57.get("session_date") != session:
        return {"status": "STALE", "reason": f"SESSION_MISMATCH:{mc57.get('session_date')}", "series": {}, "metrics": {}}
    if mc57.get("status") != "READY":
        return {"status": str(mc57.get("status") or "DATA_REQUIRED"), "reason": str(mc57.get("reason") or "MC57_NOT_READY"), "series": {}, "metrics": {}}
    if mc57.get("history_contract_version") != HISTORY_CONTRACT_VERSION:
        return {"status": "DATA_REQUIRED", "reason": "MC57_HISTORY_CONTRACT_MISSING", "series": {}, "metrics": {}}

    raw_history = mc57.get("history") if isinstance(mc57.get("history"), list) else []
    rows = [row for row in raw_history if isinstance(row, dict) and isinstance(row.get("date"), str)][-UI_HISTORY_LIMIT:]

    def series(key: str) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        for row in rows:
            point = _point(row["date"], row.get(key))
            if point is not None:
                points.append(point)
        return points

    metric_history = mc57.get("metric_history") if isinstance(mc57.get("metric_history"), dict) else {}
    metrics: dict[str, list[dict[str, Any]]] = {}
    for metric in MC57_METRICS:
        source = metric_history.get(metric) if isinstance(metric_history.get(metric), list) else []
        points: list[dict[str, Any]] = []
        for row in source[-UI_HISTORY_LIMIT:]:
            if not isinstance(row, dict) or not isinstance(row.get("date"), str):
                continue
            point = _point(row["date"], row.get("value"))
            if point is not None:
                points.append(point)
        metrics[metric] = points

    fixed = mc57.get("fixed57_breadth") if isinstance(mc57.get("fixed57_breadth"), dict) else {}
    return {
        "status": "READY",
        "reason": "CURRENT_SESSION_FIXED57_HISTORY",
        "history_sessions": len(rows),
        "current": {
            "mc57": _finite(mc57.get("mc57")),
            "raw": _finite(mc57.get("raw")),
            "ema2_raw": _finite(mc57.get("ema2_raw")),
            "z": _finite(mc57.get("z")),
        },
        "fixed57_breadth": {
            "sma20": _finite(fixed.get("sma20")),
            "sma50": _finite(fixed.get("sma50")),
            "sma200": _finite(fixed.get("sma200")),
        },
        "metric_scores": {
            metric: _finite((mc57.get("metric_scores") or {}).get(metric))
            for metric in MC57_METRICS
        },
        "series": {
            "mc57": series("mc57"),
            "raw": series("raw"),
            "ema2_raw": series("ema2_raw"),
            "z": series("z"),
            "fixed57_breadth_sma20": series("fixed57_breadth_sma20"),
            "fixed57_breadth_sma50": series("fixed57_breadth_sma50"),
            "fixed57_breadth_sma200": series("fixed57_breadth_sma200"),
        },
        "metrics": metrics,
    }
