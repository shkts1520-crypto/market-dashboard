#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from v38.ui_view_model import build_ui_view_model, write_ui_view_model


def main() -> int:
    p = argparse.ArgumentParser(description="Build display-only V38 live UI view model")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    out = build_ui_view_model(a.data_dir)
    write_ui_view_model(a.data_dir, a.output)
    print(
        json.dumps(
            {
                "output": a.output,
                "session_date": out["session_date"],
                "daily_status": out["daily"]["status"],
                "rs_status": out["rs"]["status"],
                "rs_rows": len(out["rs"]["rows"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
