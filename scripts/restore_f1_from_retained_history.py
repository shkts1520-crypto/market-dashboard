#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.f123_engine import calculate_f123_from_files
from v38.history_archive import materialize_old_top24_from_history


def _load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"JSON object required: {path}")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore canonical F1 from retained historical stock metrics without re-downloading Yahoo data"
    )
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    root = Path(args.data_dir)
    state = _load(root / "state.json")
    rs = _load(root / "rs.json")
    session = str(state.get("session_date") or "")
    if not session or str(rs.get("session_date") or "") != session:
        raise SystemExit("state/rs session mismatch")

    generated_at = str(state.get("generated_at") or "")
    if not generated_at:
        current = _load(root / "f123.json")
        generated_at = str(current.get("generated_at") or "")
    if not generated_at:
        raise SystemExit("generated_at is required")

    old_top24 = materialize_old_top24_from_history(
        root / "history",
        root / "rs.json",
        root / "old_top24.json",
        target_session=session,
        generated_at=generated_at,
    )
    if old_top24 is None:
        raise SystemExit(
            "retained stock history cannot prove a complete 20-session-lag Top24; refusing to fabricate F1"
        )

    calculate_f123_from_files(
        root / "rs.json",
        root / "f123.json",
        generated_at=generated_at,
        old_top24_path=old_top24,
    )
    out = _load(root / "f123.json")
    f1 = out.get("f1") if isinstance(out.get("f1"), dict) else {}
    dependency = f1.get("dependency") if isinstance(f1.get("dependency"), dict) else {}
    print(json.dumps({
        "session_date": session,
        "status": f1.get("status"),
        "value": f1.get("value"),
        "coverage": f1.get("coverage"),
        "old_top24_count": f1.get("old_top24_count"),
        "observable_count": f1.get("observable_count"),
        "drop_count": f1.get("drop_count"),
        "source": dependency.get("source"),
        "provenance": dependency.get("provenance"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
