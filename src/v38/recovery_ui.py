from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

READY = "READY"
DATA_REQUIRED = "DATA_REQUIRED"
CALCULATION_VERSION = "v38-recovery-ui-1.1.0"


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


def _qualified_leaders_by_theme(
    rs: dict[str, Any] | None,
    membership: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """Recover the old 'strong stock in strong group' display definition.

    The archived Command Center described leaders as RS189>=85 and above 200MA.
    This is display recovery only; it does not change Core 12 eligibility/ranking.
    """
    if not isinstance(rs, dict) or not isinstance(membership, dict):
        return {}
    member_rows = membership.get("rows")
    rs_rows = rs.get("rows")
    if not isinstance(member_rows, list) or not isinstance(rs_rows, list):
        return {}

    ticker_to_theme: dict[str, str] = {}
    for row in member_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        theme = str(row.get("theme_name") or row.get("theme_id") or "").strip()
        if ticker and theme:
            ticker_to_theme[ticker] = theme

    grouped: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for row in rs_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        theme = ticker_to_theme.get(ticker)
        rs189 = _finite(row.get("rs189"))
        price = _finite(row.get("price"))
        sma200 = _finite(row.get("sma200"))
        if (
            not ticker
            or not theme
            or rs189 is None
            or rs189 < 85.0
            or price is None
            or sma200 is None
            or price <= sma200
        ):
            continue
        grouped[theme].append((rs189, ticker))

    out: dict[str, list[str]] = {}
    for theme, values in grouped.items():
        values.sort(key=lambda item: (-item[0], item[1]))
        out[theme] = [ticker for _, ticker in values[:5]]
    return out


def _theme_as_legacy_group(
    row: dict[str, Any],
    qualified_leaders: dict[str, list[str]],
) -> dict[str, Any] | None:
    name = str(row.get("theme_name") or row.get("theme_id") or "").strip()
    if not name:
        return None
    raw_leaders = row.get("leaders")
    fallback = [str(x) for x in raw_leaders] if isinstance(raw_leaders, list) else []
    return {
        "group": name,
        "major_theme": row.get("major_theme"),
        "member_count": int(row.get("member_count") or 0),
        "ret20_avg": _finite(row.get("ret20_median")),
        "ret63_avg": None,
        "rs63_avg": _finite(row.get("rs63_median")),
        "rs189_avg": _finite(row.get("rs189_median")),
        "theme_rs": _finite(row.get("theme_rs")),
        "leaders": qualified_leaders.get(name, fallback),
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

    Existing v38-site.js already knows how to render `rotation.diagnostics.industry`.
    We project the recovered fine-theme ranking there so the two most important
    Rotation cards become useful immediately. Existing sector diagnostics are kept
    intact so the current heatmap is not silently relabelled as a different object.
    The full recovered rows are also exposed for exact Sub-Theme RS rendering.
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
    rs = _read(root / "rs.json")
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
    qualified = _qualified_leaders_by_theme(rs, membership)
    fine_groups = [
        projected
        for projected in (
            _theme_as_legacy_group(row, qualified)
            for row in full_rows
        )
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
    if isinstance(diagnostics.get("industry"), list):
        rotation["original_industry_diagnostics"] = diagnostics["industry"]
    diagnostics["industry"] = fine_groups[:120]

    detail = membership.get("coverage_detail") if isinstance(membership, dict) else None
    rotation["fine_theme_status"] = READY
    rotation["fine_theme_reason"] = "RECOVERED_LEGACY_367_THEME_MAP"
    rotation["fine_theme_coverage"] = _finite(
        membership.get("coverage") if isinstance(membership, dict) else None
    )
    rotation["fine_theme_coverage_detail"] = detail if isinstance(detail, dict) else {}
    rotation["fine_theme_rows"] = full_rows
    rotation["fine_theme_groups"] = fine_groups
    rotation["major_theme_groups"] = major_groups
    rotation["fine_theme_count"] = len(full_rows)
    rotation["fine_theme_calculation_version"] = CALCULATION_VERSION
    rotation["diagnostic_status"] = READY if fine_groups else rotation.get("diagnostic_status", DATA_REQUIRED)
    return view
