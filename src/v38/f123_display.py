from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-f123-display-completion-1.0.0"


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
    """Fill display-only F1/F3 gaps from the already downloaded OHLC history.

    The historical reconstruction intentionally uses today's universe for old
    dates.  It is therefore appropriate for dashboard diagnostics, but it is not
    PIT evidence and must never become a normal-stock hard gate.  Existing exact
    F1 evidence always wins.
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

    exact_f1 = out.get("f1") if isinstance(out.get("f1"), dict) else {}
    exact_dep = exact_f1.get("dependency") if isinstance(exact_f1.get("dependency"), dict) else {}
    exact_proven = exact_dep.get("status") == "OK" and _finite(exact_f1.get("value")) is not None
    reconstructed_f1 = current.get("f1") if isinstance(current.get("f1"), dict) else {}
    if not exact_proven and _finite(reconstructed_f1.get("value")) is not None:
        patched = dict(reconstructed_f1)
        patched["strict_pit_status"] = exact_f1.get("status")
        patched["strict_pit_dependency"] = exact_dep
        patched["display_source"] = "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC_NOT_PIT"
        patched["display_only"] = True
        out["f1"] = patched

    f3 = out.get("f3") if isinstance(out.get("f3"), dict) else {}
    if _finite(f3.get("value")) is None:
        queue = int(f3.get("queue_count") or 0)
        observed = int(f3.get("observable_count") or 0)
        broken = int(f3.get("break_count") or 0)
        coverage = observed / queue if queue > 0 else None
        # Preserve the original denominator.  Unknown names are not silently
        # reclassified as healthy; instead the display is explicitly PARTIAL.
        if queue >= 3 and coverage is not None and coverage >= 0.90:
            value = broken / queue
            patched = dict(f3)
            patched["strict_status"] = f3.get("status")
            patched["strict_value"] = f3.get("value")
            patched["value"] = value
            patched["status"] = "PARTIAL"
            patched["coverage"] = coverage
            patched["severity"] = _severity(value, 0.40, 0.60)
            patched["display_source"] = "OBSERVED_BREAKS_OVER_FULL_QUEUE_WITH_UNKNOWN_COVERAGE_REPORTED"
            patched["display_only"] = True
            out["f3"] = patched

    out["generated_at"] = generated_at
    out["display_completion_version"] = CALCULATION_VERSION
    out["display_completion_policy"] = {
        "f1": "Use exact PIT F1 when proven; otherwise current-universe reconstructed OHLC F1 for display only.",
        "f3": "If strict F3 is incomplete but >=90% of the queue is observable, display observed breaks/full queue and report coverage.",
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
