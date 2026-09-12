from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

READY = "READY"
DATA_REQUIRED = "DATA_REQUIRED"
CALCULATION_VERSION = "v38-recovery-ui-1.0.0"


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


def _theme_as_legacy_group(row: dict[str, Any]) -> dict[str, Any] | None:
    name = str(row.get("theme_name") or row.get("theme_id") or "").strip()
    if not name:
        return None
    leaders = row.get("leaders")
    return {
        "group": name,
        "major_theme": row.get("major_theme"),
        "member_count": int(row.get("member_count") or 0),
        "ret20_avg": _finite(row.get("ret20_median")),
        "ret63_avg": None,
        "rs63_avg": _finite(row.get("rs63_median")),
        "rs189_avg": _finite(row.get("rs189_median")),
        "theme_rs": _finite(row.get("theme_rs")),
        "leaders": [str(x) for x in leaders] if isinstance(leaders, list) else [],
        "scope": "RECOVERED_FINE_THEME_DISPLAY",
    }


def _major_theme_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        major = str(row.get("major_theme") or "").strip()
        if major:
            grouped[major].append(row)

    output: list[dict[str, Any]] = []
    for major, members in grouped.items():
        weights = [max(1, int(row.get("member_count") or 0)) for row in members]

        def weighted(key: str) -> float | None:
            pairs = [
                (_finite(row.get(key)), weight)
                for row, weight in zip(members, weights)
            ]
            pairs = [(value, weight) for value, weight in pairs if value is not None]
            total = sum(weight for _, weight in pairs)
            if not pairs or total <= 0:
                return None
            return sum(value * weight for value, weight in pairs) / total

        leader_rows = sorted(
            members,
            key=lambda row: -(_finite(row.get("theme_rs")) or -1.0),
        )
        leaders: list[str] = []
        for row in leader_rows:
            raw = row.get("leaders")
            if not isinstance(raw, list):
                continue
            for ticker in raw:
                text = str(ticker).strip().upper()
                if text and text not in leaders:
                    leaders.append(text)
                if len(leaders) >= 5:
                    break
            if len(leaders) >= 5:
                break

        output.append({
            "group": major,
            "member_count": sum(weights),
            "ret20_avg": weighted("ret20_median"),
            "ret63_avg": None,
            "rs63_avg": weighted("rs63_median"),
            "rs189_avg": weighted("rs189_median"),
            "theme_rs": weighted("theme_rs"),
            "leaders": leaders,
            "scope": "RECOVERED_MAJOR_THEME_DISPLAY",
        })

    output.sort(
        key=lambda row: (
            -(row["theme_rs"] if row["theme_rs"] is not None else -1e100),
            row["group"],
        )
    )
    return output


def attach_recovered_theme_ui(
    view: dict[str, Any],
    data_dir: str | Path,
) -> dict[str, Any]:
    """Attach recovered legacy fine themes without changing trade authority.

    Existing v38-site.js already knows how to render `rotation.diagnostics.industry`
    and `.sector`.  Project the recovered 367-theme display dataset into those
    fields so the original Rotation cards become useful immediately, while also
    exposing the full rows separately for the later exact card restoration.
    """
    if not isinstance(view, dict):
        return view
    session = str(view.get("session_date") or "")
    rotation = view.get("rotation")
    if not session or not isinstance(rotation, dict):
        return view

    root = Path(data_dir)
    recovered = _read(root / "theme_rotation_recovered.json")
    membership = _read(root / "theme_membership.json")
    if (
        recovered is None
        or recovered.get("session_date") != session
        or recovered.get("status") != READY
        or not isinstance(recovered.get("rows"), list)
    ):
        rotation["fine_theme_status"] = DATA_REQUIRED
        rotation["fine_theme_reason"] = "RECOVERED_THEME_ROTATION_MISSING_OR_STALE"
        rotation["fine_theme_rows"] = []
        return view

    full_rows = [dict(row) for row in recovered["rows"] if isinstance(row, dict)]
    fine_groups = [
        projected
        for projected in (_theme_as_legacy_group(row) for row in full_rows)
        if projected is not None
    ]
    fine_groups.sort(
        key=lambda row: (
            -(row["theme_rs"] if row["theme_rs"] is not None else -1e100),
            row["group"],
        )
    )
    major_groups = _major_theme_groups(full_rows)

    diagnostics = rotation.get("diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        rotation["diagnostics"] = diagnostics
    diagnostics["industry"] = fine_groups[:60]
    diagnostics["sector"] = major_groups[:30]

    detail = membership.get("coverage_detail") if isinstance(membership, dict) else None
    rotation["fine_theme_status"] = READY
    rotation["fine_theme_reason"] = "RECOVERED_LEGACY_367_THEME_MAP"
    rotation["fine_theme_coverage"] = _finite(
        membership.get("coverage") if isinstance(membership, dict) else None
    )
    rotation["fine_theme_coverage_detail"] = detail if isinstance(detail, dict) else {}
    rotation["fine_theme_rows"] = full_rows
    rotation["fine_theme_count"] = len(full_rows)
    rotation["fine_theme_calculation_version"] = CALCULATION_VERSION
    rotation["diagnostic_status"] = READY if fine_groups else rotation.get("diagnostic_status", DATA_REQUIRED)
    return view
