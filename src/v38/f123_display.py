from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-f123-display-completion-1.2.0"


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
    """Attach a display-only F1 fallback when canonical F1 cannot be restored.

    F3 is no longer patched in the display layer: the canonical engine itself
    follows the original V38 full-queue denominator contract.
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

    out["generated_at"] = generated_at
    out["display_overrides"] = overrides
    out["display_completion_version"] = CALCULATION_VERSION
    out["display_completion_policy"] = {
        "f1": "Canonical F1 is preferred; current-universe reconstructed F1 is display-only only when canonical restoration is unavailable.",
        "f3": "No display override. Canonical F3 uses the original full qualified-queue denominator.",
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
