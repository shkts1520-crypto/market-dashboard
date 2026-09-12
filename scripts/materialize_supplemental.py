#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from v38.authority_status import sync_acquisition_manifest
from v38.f123_display import complete_f123_file
from v38.history_archive import stage_session_snapshot
from v38.rs_history import write_rs_history
from v38.supplemental_engine import materialize_supplemental_shards
from v38.tqqq_state import materialize_tqqq_panic_state


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _is_production_context() -> bool:
    event = str(os.environ.get("GITHUB_EVENT_NAME") or "").strip().lower()
    return event not in {"", "pull_request", "pull_request_target"}


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


def _reconstruct_history_if_production(root: Path, *, generated_at: str) -> Path | None:
    """Rebuild the original two-year display window in production.

    Pull-request verification never performs network acquisition. Main/scheduled/
    manual runs fetch 3 years of stock OHLC so the two-year Breadth display has the
    required 200-session indicator warm-up, and fetch 2 years for market ratios.
    These histories remain display-only and never become trading gates.
    """
    if not _is_production_context():
        return None

    command = [
        sys.executable,
        "scripts/reconstruct_display_history_2y.py",
        "--data-dir", str(root),
        "--generated-at", generated_at,
    ]
    subprocess.run(command, check=True)

    outputs = (
        root / "history" / "reconstructed_stock_metrics.json",
        root / "history" / "market_diagnostics_2y.json",
        root / "history" / "market_series_2y.json",
    )
    for output in outputs:
        if not output.is_file() or output.stat().st_size <= 0:
            raise SystemExit(f"two-year display reconstruction missing output: {output}")
    return outputs[0]


def _materialize_tqqq_if_ready(root: Path, *, session: str, generated_at: str) -> Path | None:
    market_inputs = _load(root / "market_inputs.json")
    mc57 = _load(root / "mc57.json")
    ready = market_inputs.get("session_date") == session and mc57.get("session_date") == session
    if not ready:
        if _is_production_context():
            raise SystemExit("current-session market_inputs.json and mc57.json are required for TQQQ panic state")
        return None
    return materialize_tqqq_panic_state(
        root,
        session_date=session,
        generated_at=generated_at,
    )


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

    # Reuse the same downloaded historical market data for Breadth, RS and F1/F2/F3.
    # This happens before UI/publish materialization so reconstructed display values
    # are actually visible in the same production run instead of one run later.
    reconstructed_history = _reconstruct_history_if_production(
        root,
        generated_at=generated_at,
    )
    f123_completion = complete_f123_file(
        root,
        session_date=session,
        generated_at=generated_at,
    )

    # TQQQ Panic is a persistent state machine.  It consumes the canonical QQQ 4H
    # input and current MC57 after both have been acquired for this session.
    tqqq_state = _materialize_tqqq_if_ready(
        root,
        session=session,
        generated_at=generated_at,
    )

    outputs = materialize_supplemental_shards(
        root,
        session_date=session,
        generated_at=generated_at,
        theme_scores_path=args.theme_scores,
        positions_ledger_path=ledger_arg,
    )

    # Refresh the current observed session after reconstruction. The exact current
    # session remains authoritative and overrides display-only reconstructed values.
    history_snapshot, history_index = stage_session_snapshot(
        root,
        root / "history",
        root / "history",
    )
    rs_history = write_rs_history(
        root / "history",
        root / "rs.json",
        root / "history" / "rs_history.json",
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
                "historical_reconstruction": reconstructed_history.as_posix() if reconstructed_history is not None else None,
                "f123_display_completion": f123_completion.as_posix() if f123_completion is not None else None,
                "tqqq_panic_state": tqqq_state.as_posix() if tqqq_state is not None else None,
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
