#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.authority_status import sync_acquisition_manifest
from v38.history_archive import stage_session_snapshot
from v38.rs_history import write_rs_history
from v38.supplemental_engine import materialize_supplemental_shards


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _materialize_confirmed_empty_ledger(root: Path, *, session: str, generated_at: str) -> Path | None:
    """Turn the user's explicit EMPTY portfolio setting into a current-session ledger.

    This avoids misreporting an intentional zero-position portfolio as missing data.
    Switching config/portfolio_state.json away from EMPTY immediately stops this
    behavior and restores the explicit ledger requirement.
    """
    config = _load(Path("config/portfolio_state.json"))
    if str(config.get("mode") or "").upper() != "EMPTY":
        return None
    ledger = {
        "session_date": session,
        "generated_at": generated_at,
        "coverage": 1.0,
        "source": "user-confirmed-empty:config/portfolio_state.json",
        "schema_version": "v38.positions_ledger.1",
        "calculation_version": "v38-user-confirmed-empty-ledger-1.0.0",
        "status": "READY",
        "ledger_version": "EMPTY",
        "rows": [],
        "note": str(config.get("note") or "No open positions."),
        "confirmed_at": config.get("confirmed_at"),
    }
    path = root / "positions_ledger.json"
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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

    empty_ledger = _materialize_confirmed_empty_ledger(
        root,
        session=session,
        generated_at=generated_at,
    )
    ledger_arg = args.positions_ledger or (str(empty_ledger) if empty_ledger is not None else None)

    outputs = materialize_supplemental_shards(
        root,
        session_date=session,
        generated_at=generated_at,
        theme_scores_path=args.theme_scores,
        positions_ledger_path=ledger_arg,
    )

    # Refresh the current observed session even when the workflow is retaining an
    # already-published market session.  This is not a historical backfill: it only
    # rewrites the current session from current authoritative shards and preserves
    # the actually accumulated archive.
    history_snapshot, history_index = stage_session_snapshot(
        root,
        root / "history",
        root / "history",
    )
    rs_history = write_rs_history(
        root / "history",
        root / "rs.json",
        root / "rs_history.json",
        session_date=session,
        generated_at=generated_at,
    )

    manifest = sync_acquisition_manifest(root)
    print(
        json.dumps(
            {
                "session_date": session,
                "positions_mode": "EMPTY" if empty_ledger is not None else "LEDGER_REQUIRED",
                "positions_ledger": empty_ledger.as_posix() if empty_ledger is not None else ledger_arg,
                "outputs": [p.as_posix() for p in outputs],
                "history_snapshot": history_snapshot.as_posix(),
                "history_index": history_index.as_posix(),
                "rs_history": rs_history.as_posix(),
                "authority_manifest": manifest.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
