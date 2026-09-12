from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mc57_history import build_mc57_ui_detail


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def attach_mc57_ui_detail(
    view: dict[str, Any],
    data_dir: str | Path,
) -> dict[str, Any]:
    session = view.get("session_date")
    daily = view.get("daily")
    if not isinstance(session, str) or not isinstance(daily, dict):
        return view
    mc57 = _read(Path(data_dir) / "mc57.json")
    daily["mc57_detail"] = build_mc57_ui_detail(mc57, session=session)
    daily["pit_breadth_history_sessions"] = len(daily.get("history") or [])
    return view
