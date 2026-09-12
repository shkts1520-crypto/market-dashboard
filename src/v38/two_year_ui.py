from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DISPLAY_SESSIONS = 504


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _merge_daily_history(existing: Any, reconstructed: Any, session: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    if isinstance(reconstructed, list):
        for row in reconstructed:
            if not isinstance(row, dict) or not isinstance(row.get("date"), str):
                continue
            if row["date"] > session:
                continue
            item = {
                "date": row["date"],
                "breadth50": row.get("breadth50"),
                "breadth200": row.get("breadth200"),
            }
            for key in ("f1", "f2", "f3"):
                component = row.get(key)
                item[key] = component.get("value") if isinstance(component, dict) else None
            merged[row["date"]] = item
    if isinstance(existing, list):
        for row in existing:
            if not isinstance(row, dict) or not isinstance(row.get("date"), str):
                continue
            if row["date"] > session:
                continue
            base = dict(merged.get(row["date"], {"date": row["date"]}))
            for key, value in row.items():
                if key == "date" or value is not None:
                    base[key] = value
            merged[row["date"]] = base
    return [merged[day] for day in sorted(merged)][-DISPLAY_SESSIONS:]


def attach_two_year_display_history(view: dict[str, Any], data_dir: str | Path) -> dict[str, Any]:
    """Attach display-only 2-year series without altering trading authorities."""
    if not isinstance(view, dict):
        return view
    daily = view.get("daily")
    session = str(view.get("session_date") or "")
    if not isinstance(daily, dict) or not session:
        return view

    root = Path(data_dir)
    stock = _read(root / "history" / "reconstructed_stock_metrics.json") or {}
    stock_rows = stock.get("rows") if isinstance(stock.get("rows"), list) else []
    daily["history"] = _merge_daily_history(daily.get("history"), stock_rows, session)

    market = _read(root / "history" / "market_series_2y.json") or {}
    if market.get("session_date") == session and isinstance(market.get("series"), dict):
        daily["market_series"] = {
            symbol: [dict(row) for row in rows[-DISPLAY_SESSIONS:] if isinstance(row, dict)]
            for symbol, rows in market["series"].items()
            if isinstance(rows, list)
        }

    diagnostics = _read(root / "history" / "market_diagnostics_2y.json") or {}
    if diagnostics.get("session_date") == session and isinstance(diagnostics.get("series"), list):
        daily["market_diagnostics"] = {
            "status": diagnostics.get("status", "READY"),
            "reason": "CURRENT_UNIVERSE_DISPLAY_DIAGNOSTIC_NOT_TRADING_GATE",
            "universe_scope": "current point-in-time universe applied to historical bars",
            "survivorship_warning": True,
            "series": [dict(row) for row in diagnostics["series"][-DISPLAY_SESSIONS:] if isinstance(row, dict)],
        }

    daily["display_history"] = {
        "window_sessions": DISPLAY_SESSIONS,
        "history_points": len(daily.get("history") or []),
        "market_source": market.get("source"),
        "diagnostic_source": diagnostics.get("source"),
        "trading_gate_eligible": False,
    }
    return view
