#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from v38.rs_history import (
    RS_HISTORY_CALCULATION_VERSION,
    RS_HISTORY_SCHEMA_VERSION,
    build_rs_history_analysis,
)
from v38.freshness import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Build display-only RS comparison and leadership persistence")
    parser.add_argument("--ohlcv", required=True)
    parser.add_argument("--rs", default="data/rs.json")
    parser.add_argument("--output", default="data/rs_history.json")
    args = parser.parse_args()

    rs_path = Path(args.rs)
    rs = json.loads(rs_path.read_text(encoding="utf-8"))
    if not isinstance(rs, dict) or not rs.get("session_date"):
        raise SystemExit("rs.json with session_date is required")

    session = str(rs["session_date"])
    ohlcv = pd.read_csv(args.ohlcv)
    analysis = build_rs_history_analysis(ohlcv, rs, session_date=session)
    ready = analysis.get("status") == "READY"
    output = {
        "session_date": session,
        "generated_at": str(rs.get("generated_at") or ""),
        "coverage": 1.0 if ready else 0.0,
        "source": "derived:current V38 verified stock OHLCV; retrospective display only",
        "schema_version": RS_HISTORY_SCHEMA_VERSION,
        "calculation_version": RS_HISTORY_CALCULATION_VERSION,
        **analysis,
    }
    path = atomic_write_json(args.output, output)
    print(json.dumps({
        "path": str(path),
        "session_date": session,
        "status": output.get("status"),
        "reason": output.get("reason"),
        "history_sessions": output.get("history_sessions"),
        "identity_check": output.get("identity_check"),
        "persistence_rows": len((output.get("persistence") or {}).get("rows") or []),
    }, ensure_ascii=False, sort_keys=True))
    if not ready:
        raise SystemExit("RS history failed closed: " + str(output.get("reason")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
