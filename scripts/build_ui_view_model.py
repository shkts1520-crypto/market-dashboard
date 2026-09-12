#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from v38.mc57_ui import attach_mc57_ui_detail
from v38.recovery_ui import attach_recovered_theme_ui
from v38.ui_view_model import build_ui_view_model


def main() -> int:
    p = argparse.ArgumentParser(description="Build display-only V38 live UI view model")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    out = build_ui_view_model(a.data_dir)
    out = attach_mc57_ui_detail(out, a.data_dir)
    out = attach_recovered_theme_ui(out, a.data_dir)
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

    print(
        json.dumps(
            {
                "output": a.output,
                "session_date": out["session_date"],
                "daily_status": out["daily"]["status"],
                "rs_status": out["rs"]["status"],
                "rs_rows": len(out["rs"]["rows"]),
                "rs_history": rs_history_output.as_posix(),
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
