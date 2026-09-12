from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

READY = "READY"
DATA_REQUIRED = "DATA_REQUIRED"
CALCULATION_VERSION = "v38-ui-polish-1.0.0"


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
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _good_component(component: Any) -> bool:
    if not isinstance(component, dict):
        return False
    return (
        _finite(component.get("value")) is not None
        and str(component.get("status") or "") in {"OK", "FULL", "PARTIAL", READY}
    )


def _display_component(
    exact: Any,
    reconstructed: Any,
    *,
    key: str,
) -> dict[str, Any]:
    if _good_component(exact):
        out = dict(exact)
        out["display_provenance"] = "CURRENT_SESSION_EXACT"
        out["trading_gate_eligible"] = False
        return out
    if isinstance(reconstructed, dict) and _finite(reconstructed.get("value")) is not None:
        out = dict(reconstructed)
        out["status"] = READY
        out["display_provenance"] = "CURRENT_UNIVERSE_RECONSTRUCTED_DISPLAY_ONLY"
        out["trading_gate_eligible"] = False
        out["reason"] = "CURRENT_UNIVERSE_RECONSTRUCTED_DISPLAY_ONLY"
        return out
    return {
        "value": None,
        "status": DATA_REQUIRED,
        "severity": "NO_JUDGMENT",
        "display_provenance": "UNAVAILABLE",
        "trading_gate_eligible": False,
        "reason": f"{key.upper()}_DISPLAY_INPUT_UNAVAILABLE",
    }


def _merge_history(
    reconstructed_rows: list[dict[str, Any]],
    observed_rows: Any,
    *,
    session: str,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    keys = ("breadth50", "breadth200", "f1", "f2", "f3")
    for raw in reconstructed_rows:
        if not isinstance(raw, dict) or not isinstance(raw.get("date"), str):
            continue
        day = raw["date"]
        if day > session:
            continue
        item: dict[str, Any] = {
            "date": day,
            "breadth50": _finite(raw.get("breadth50")),
            "breadth200": _finite(raw.get("breadth200")),
            "f1": _finite((raw.get("f1") or {}).get("value")) if isinstance(raw.get("f1"), dict) else None,
            "f2": _finite((raw.get("f2") or {}).get("value")) if isinstance(raw.get("f2"), dict) else None,
            "f3": _finite((raw.get("f3") or {}).get("value")) if isinstance(raw.get("f3"), dict) else None,
            "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
            "full_v38_ready": False,
        }
        merged[day] = item

    if isinstance(observed_rows, list):
        for observed in observed_rows:
            if not isinstance(observed, dict) or not isinstance(observed.get("date"), str):
                continue
            day = observed["date"]
            if day > session:
                continue
            base = dict(merged.get(day) or {"date": day})
            used_reconstructed = False
            for key in keys:
                value = _finite(observed.get(key))
                if value is not None:
                    base[key] = value
                elif key in base and base.get(key) is not None:
                    used_reconstructed = True
            if "full_v38_ready" in observed:
                base["full_v38_ready"] = bool(observed.get("full_v38_ready"))
            base["history_kind"] = (
                "OBSERVED_SESSION_WITH_RECONSTRUCTED_GAPS"
                if used_reconstructed
                else "OBSERVED_SESSION"
            )
            merged[day] = base
    return [merged[day] for day in sorted(merged)][-260:]


def _replace_metric(metrics: Any, key: str, component: dict[str, Any]) -> None:
    if not isinstance(metrics, list):
        return
    value = _finite(component.get("value"))
    if value is None:
        return
    for metric in metrics:
        if not isinstance(metric, dict) or metric.get("key") != key:
            continue
        metric["value"] = value
        metric["display"] = f"{value * 100.0:.1f}%"
        metric["status"] = READY
        metric["reason"] = str(component.get("display_provenance") or "DISPLAY_VALUE")
        metric["display_provenance"] = component.get("display_provenance")
        metric["trading_gate_eligible"] = False
        return


def _refresh_daily_status(daily: dict[str, Any]) -> None:
    required = {
        "market_mode", "nqsar", "breadth50", "breadth200", "mc57",
        "f1", "f2", "f3", "market_QQQ", "market_TQQQ", "market_^VIX",
        "market_NQ=F", "market_SPY",
    }
    metrics = daily.get("metrics")
    if not isinstance(metrics, list):
        return
    by_key = {
        str(row.get("key")): row
        for row in metrics
        if isinstance(row, dict) and row.get("key") is not None
    }
    daily["status"] = (
        READY
        if all(isinstance(by_key.get(key), dict) and by_key[key].get("status") == READY for key in required)
        else DATA_REQUIRED
    )


def attach_reconstructed_stock_ui(
    view: dict[str, Any],
    data_dir: str | Path,
) -> dict[str, Any]:
    """Attach reconstructed stock history for display only.

    Strict current F1 authority stays in data/f123.json.  If that exact PIT input is
    unavailable, the visible F1 card may use the already-approved current-universe
    historical reconstruction.  It is explicitly marked display-only and never
    becomes a trading-gate authority.
    """
    if not isinstance(view, dict):
        return view
    daily = view.get("daily")
    session = str(view.get("session_date") or "")
    if not isinstance(daily, dict) or not session:
        return view

    root = Path(data_dir)
    reconstructed = _read(root / "history" / "reconstructed_stock_metrics.json")
    if (
        reconstructed is None
        or reconstructed.get("status") != READY
        or reconstructed.get("history_kind") != "CURRENT_UNIVERSE_RECONSTRUCTED"
        or not isinstance(reconstructed.get("rows"), list)
    ):
        return view

    reconstructed_rows = [row for row in reconstructed["rows"] if isinstance(row, dict)]
    by_date = {
        row["date"]: row
        for row in reconstructed_rows
        if isinstance(row.get("date"), str)
    }
    current_reconstructed = by_date.get(session) or {}
    f123 = _read(root / "f123.json") or {}
    exact_same_session = f123.get("session_date") == session

    detail: dict[str, Any] = {}
    for key in ("f1", "f2", "f3"):
        exact = f123.get(key) if exact_same_session else None
        recon = current_reconstructed.get(key) if isinstance(current_reconstructed, dict) else None
        detail[key] = _display_component(exact, recon, key=key)

    daily["history"] = _merge_history(
        reconstructed_rows,
        daily.get("history"),
        session=session,
    )
    daily["f123_detail"] = {
        "status": READY if all(_finite(detail[key].get("value")) is not None for key in ("f1", "f2", "f3")) else DATA_REQUIRED,
        "calculation_version": CALCULATION_VERSION,
        "f1": detail["f1"],
        "f2": detail["f2"],
        "f3": detail["f3"],
    }
    for key in ("f1", "f2", "f3"):
        _replace_metric(daily.get("metrics"), key, detail[key])
    _refresh_daily_status(daily)

    daily["historical_reconstruction"] = {
        "status": READY,
        "history_kind": reconstructed.get("history_kind"),
        "session_count": reconstructed.get("session_count"),
        "first_session": reconstructed.get("first_session"),
        "latest_session": reconstructed.get("latest_session"),
        "current_universe_count": reconstructed.get("current_universe_count"),
        "survivorship_warning": bool(reconstructed.get("survivorship_warning")),
        "trading_gate_eligible": bool(reconstructed.get("trading_gate_eligible")),
        "source": reconstructed.get("source"),
    }
    return view
