from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-f123-display-completion-1.1.0"


class F123DisplayError(RuntimeError):
    pass


def _load(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _severity(value: float | None, warn: float, severe: float) -> str:
    if value is None:
        return "NO_JUDGMENT"
    if value >= severe:
        return "SEVERE"
    if value >= warn:
        return "CAUTION"
    return "NORMAL"


def complete_f123_for_display(
    f123: dict[str, Any],
    reconstructed: dict[str, Any],
    *,
    session_date: str,
    generated_at: str,
) -> dict[str, Any]:
    """Attach display-only F1/F3 alternatives without mutating strict authority.

    The current-universe historical reconstruction is useful for the restored
    dashboard but is not PIT evidence. Therefore f1/f2/f3 remain exactly as the
    strict engine produced them. Display fallbacks live under display_overrides,
    making it impossible for downstream trading code to mistake them for exact
    current-session authority.
    """
    out = dict(f123)
    if out.get("session_date") != session_date:
        raise F123DisplayError("f123 session mismatch")
    if reconstructed.get("session_date") != session_date:
        return out
    if reconstructed.get("status") != "READY" or reconstructed.get("history_kind") != "CURRENT_UNIVERSE_RECONSTRUCTED":
        return out
    rows = reconstructed.get("rows")
    if not isinstance(rows, list):
        return out
    current = next(
        (row for row in reversed(rows) if isinstance(row, dict) and row.get("date") == session_date),
        None,
    )
    if current is None:
        return out

    overrides: dict[str, Any] = {}
    exact_f1 = out.get("f1") if isinstance(out.get("f1"), dict) else {}
    exact_dep = exact_f1.get("dependency") if isinstance(exact_f1.get("dependency"), dict) else {}
    exact_proven = exact_dep.get("status") == "OK" and _finite(exact_f1.get("value")) is not None
    reconstructed_f1 = current.get("f1") if isinstance(current.get("f1"), dict) else {}
    if not exact_proven and _finite(reconstructed_f1.get("value")) is not None:
        display_f1 = dict(reconstructed_f1)
        display_f1["strict_pit_status"] = exact_f1.get("status")
        display_f1["strict_pit_dependency"] = exact_dep
        display_f1["display_source"] = "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC_NOT_PIT"
        display_f1["display_only"] = True
        display_f1["trading_gate_eligible"] = False
        overrides["f1"] = display_f1

    f3 = out.get("f3") if isinstance(out.get("f3"), dict) else {}
    if _finite(f3.get("value")) is None:
        queue = int(f3.get("queue_count") or 0)
        observed = int(f3.get("observable_count") or 0)
        broken = int(f3.get("break_count") or 0)
        coverage = observed / queue if queue > 0 else None
        if queue >= 3 and coverage is not None and coverage >= 0.90:
            value = broken / queue
            display_f3 = dict(f3)
            display_f3["value"] = value
            display_f3["status"] = "PARTIAL"
            display_f3["coverage"] = coverage
            display_f3["severity"] = _severity(value, 0.40, 0.60)
            display_f3["display_source"] = "OBSERVED_BREAKS_OVER_FULL_QUEUE_WITH_UNKNOWN_COVERAGE_REPORTED"
            display_f3["display_only"] = True
            display_f3["trading_gate_eligible"] = False
            overrides["f3"] = display_f3

    out["generated_at"] = generated_at
    out["display_overrides"] = overrides
    out["display_completion_version"] = CALCULATION_VERSION
    out["display_completion_policy"] = {
        "f1": "Strict f1 remains unchanged. If PIT is unavailable, the current-universe reconstructed value is display-only.",
        "f3": "Strict f3 remains unchanged. If >=90% of the queue is observable, observed breaks/full queue may be displayed with coverage.",
        "hard_gate": False,
    }
    return out


def complete_f123_file(
    data_dir: str | Path,
    *,
    session_date: str,
    generated_at: str,
) -> Path | None:
    root = Path(data_dir)
    f123 = _load(root / "f123.json")
    reconstructed = _load(root / "history" / "reconstructed_stock_metrics.json")
    if not f123 or not reconstructed:
        return None
    out = complete_f123_for_display(
        f123,
        reconstructed,
        session_date=session_date,
        generated_at=generated_at,
    )
    return atomic_write_json(root / "f123.json", out)
