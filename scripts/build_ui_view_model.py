#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from v38.mc57_ui import attach_mc57_ui_detail
from v38.recovery_ui import attach_recovered_theme_ui
from v38.ui_view_model import build_ui_view_model


def _finite(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _attach_reconstructed_daily_history(view: dict, data_dir: str | Path) -> dict:
    path = Path(data_dir) / "history" / "reconstructed_stock_metrics.json"
    if not path.is_file():
        return view
    try:
        reconstructed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return view
    if reconstructed.get("status") != "READY" or reconstructed.get("history_kind") != "CURRENT_UNIVERSE_RECONSTRUCTED":
        return view
    raw_rows = reconstructed.get("rows")
    if not isinstance(raw_rows, list):
        return view

    daily = view.get("daily")
    if not isinstance(daily, dict):
        return view
    merged = {}
    for raw in raw_rows:
        if not isinstance(raw, dict) or not isinstance(raw.get("date"), str):
            continue
        item = {
            "date": raw["date"],
            "breadth50": _finite(raw.get("breadth50")),
            "breadth200": _finite(raw.get("breadth200")),
            "f1": _finite((raw.get("f1") or {}).get("value")) if isinstance(raw.get("f1"), dict) else None,
            "f2": _finite((raw.get("f2") or {}).get("value")) if isinstance(raw.get("f2"), dict) else None,
            "f3": _finite((raw.get("f3") or {}).get("value")) if isinstance(raw.get("f3"), dict) else None,
            "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
            "full_v38_ready": False,
        }
        merged[item["date"]] = item

    # Exact archived sessions are authoritative when both exist.
    observed = daily.get("history")
    if isinstance(observed, list):
        for row in observed:
            if isinstance(row, dict) and isinstance(row.get("date"), str):
                merged[row["date"]] = dict(row)
                merged[row["date"]]["history_kind"] = "OBSERVED_SESSION"

    session = str(view.get("session_date") or "")
    daily["history"] = [merged[day] for day in sorted(merged) if day <= session][-260:]
    daily["historical_reconstruction"] = {
        "status": "READY",
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


def main() -> int:
    p = argparse.ArgumentParser(description="Build display-only V38 live UI view model")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    out = build_ui_view_model(a.data_dir)
    out = attach_mc57_ui_detail(out, a.data_dir)
    out = attach_recovered_theme_ui(out, a.data_dir)
    out = _attach_reconstructed_daily_history(out, a.data_dir)
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    rs_history_source = Path(a.data_dir) / "history" / "rs_history.json"
    rs_history_output = path.parent / "rs_history.json"
    if not rs_history_source.is_file():
        raise SystemExit(f"RS history shard is required: {rs_history_source}")
    shutil.copy2(rs_history_source, rs_history_output)

    history_meta = out["daily"].get("historical_reconstruction") or {}
    print(
        json.dumps(
            {
                "output": a.output,
                "session_date": out["session_date"],
                "daily_status": out["daily"]["status"],
                "rs_status": out["rs"]["status"],
                "rs_rows": len(out["rs"]["rows"]),
                "rs_history": rs_history_output.as_posix(),
                "stock_history_kind": history_meta.get("history_kind"),
                "stock_history_sessions": history_meta.get("session_count", 0),
                "mc57_history_status": out["daily"]["mc57_detail"]["status"],
                "mc57_history_sessions": out["daily"]["mc57_detail"].get("history_sessions", 0),
                "fine_theme_status": out["rotation"].get("fine_theme_status"),
                "fine_theme_count": out["rotation"].get("fine_theme_count", 0),
                "fine_theme_coverage": out["rotation"].get("fine_theme_coverage"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
