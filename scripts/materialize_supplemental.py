#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.supplemental_engine import materialize_supplemental_shards


def main() -> int:
    p = argparse.ArgumentParser(description="Materialize fail-closed V38 supplemental shards")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--theme-scores")
    p.add_argument("--positions-ledger")
    args = p.parse_args()

    root = Path(args.data_dir)
    state_path = root / "state.json"
    if not state_path.exists():
        raise SystemExit("state.json is required")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    session = state.get("session_date")
    generated_at = state.get("generated_at")
    if not isinstance(session, str) or not session:
        raise SystemExit("state.session_date is required")
    if not isinstance(generated_at, str) or not generated_at:
        raise SystemExit("state.generated_at is required")

    outputs = materialize_supplemental_shards(
        root,
        session_date=session,
        generated_at=generated_at,
        theme_scores_path=args.theme_scores,
        positions_ledger_path=args.positions_ledger,
    )
    print(json.dumps({"session_date": session, "outputs": [p.as_posix() for p in outputs]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
