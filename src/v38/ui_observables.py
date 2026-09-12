from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

from .mc57_engine import MC57_METRICS

CALCULATION_VERSION = "v38-ui-observables-1.0.0"


class UIObservablesError(RuntimeError):
    pass


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _series(history: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    rows = []
    for row in history:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str):
            continue
        value = _finite(row.get(key))
        if value is not None:
            rows.append({"date": row["date"], "value": value})
    return rows


def augment_view_model(data_dir: str | Path, view_model_path: str | Path) -> dict[str, Any]:
    root = Path(data_dir)
    view_path = Path(view_model_path)
    view = _read(view_path)
    if view is None:
        raise UIObservablesError("ui_view_model.json is missing or invalid")
    daily = view.get("daily")
    if not isinstance(daily, dict):
        raise UIObservablesError("ui_view_model.daily is missing")
    session = str(view.get("session_date") or "")

    mc57 = _read(root / "mc57.json")
    if mc57 and mc57.get("session_date") == session and mc57.get("status") == "READY":
        raw_history = mc57.get("history")
        history = [row for row in raw_history if isinstance(row, dict)] if isinstance(raw_history, list) else []
        scores = mc57.get("metric_scores") if isinstance(mc57.get("metric_scores"), dict) else {}
        metrics = {metric: _series(history, metric) for metric in MC57_METRICS}
        daily["mc57_detail"] = {
            "status": "READY",
            "calculation_version": mc57.get("calculation_version"),
            "history_sessions": len(_series(history, "mc57")),
            "current": {
                "mc57": _finite(mc57.get("mc57")),
                "raw": _finite(mc57.get("raw")),
                "ema2_raw": _finite(mc57.get("ema2_raw")),
                "z": _finite(mc57.get("z")),
                "mu_prior": _finite(mc57.get("mu_prior")),
                "sigma_prior": _finite(mc57.get("sigma_prior")),
            },
            "series": {
                "mc57": _series(history, "mc57"),
                "raw": _series(history, "raw"),
                "ema2_raw": _series(history, "ema2_raw"),
                "z": _series(history, "z"),
                "fixed57_breadth_sma20": _series(history, "close_gt_sma20"),
                "fixed57_breadth_sma50": _series(history, "close_gt_sma50"),
                "fixed57_breadth_sma200": _series(history, "close_gt_sma200"),
            },
            "fixed57_breadth": {
                "sma20": _finite(scores.get("close_gt_sma20")),
                "sma50": _finite(scores.get("close_gt_sma50")),
                "sma200": _finite(scores.get("close_gt_sma200")),
            },
            "metric_scores": {metric: _finite(scores.get(metric)) for metric in MC57_METRICS},
            "metrics": metrics,
        }
    else:
        daily["mc57_detail"] = {"status": "DATA_REQUIRED", "history_sessions": 0}

    daily_history = daily.get("history")
    daily["pit_breadth_history_sessions"] = len(daily_history) if isinstance(daily_history, list) else 0

    nqsar = _read(root / "nqsar.json")
    if nqsar and nqsar.get("session_date") == session:
        hist = nqsar.get("history")
        daily["nqsar_history"] = [dict(row) for row in hist if isinstance(row, dict)] if isinstance(hist, list) else []
        daily["nqsar_input_kind"] = nqsar.get("input_kind")
        daily["nqsar_authoritative_exact"] = bool(nqsar.get("authoritative_exact"))

    analytics = _read(root / "analytics.json")
    if analytics and analytics.get("session_date") == session:
        daily["recovered_analytics"] = {
            "status": analytics.get("status"),
            "source": analytics.get("source"),
            "market_diagnostics": analytics.get("market_diagnostics") if isinstance(analytics.get("market_diagnostics"), dict) else {},
        }

    view["observables_calculation_version"] = CALCULATION_VERSION
    return view


def write_augmented_view_model(data_dir: str | Path, view_model_path: str | Path) -> Path:
    path = Path(view_model_path)
    obj = augment_view_model(data_dir, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path
