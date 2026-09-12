#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from v38.ui_observables import augment_view_model, write_augmented_view_model


def main() -> int:
    p = argparse.ArgumentParser(description="Add MC57, fixed57 breadth and recovered analytics histories to the canonical UI view model")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--view-model", required=True)
    a = p.parse_args()
    out = augment_view_model(a.data_dir, a.view_model)
    write_augmented_view_model(a.data_dir, a.view_model)
    detail = out.get("daily", {}).get("mc57_detail", {})
    print(json.dumps({
        "view_model": a.view_model,
        "mc57_status": detail.get("status"),
        "mc57_history_sessions": detail.get("history_sessions", 0),
        "pit_breadth_history_sessions": out.get("daily", {}).get("pit_breadth_history_sessions", 0),
        "nqsar_input_kind": out.get("daily", {}).get("nqsar_input_kind"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
