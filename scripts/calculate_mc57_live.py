#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yfinance as yf

from v38.mc57_history import HISTORY_CONTRACT_VERSION, enrich_mc57_history
from v38.mc57_live import (
    CALCULATION_VERSION,
    FIXED_57_ETFS,
    build_mc57_object,
    download_fixed57_adjusted_closes,
    load_verified_reference,
    write_mc57_json,
)


def _load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return obj


def main() -> int:
    p = argparse.ArgumentParser(description="Calculate production MC57 from the recovered fixed 57-ETF contract")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--reference", default="config/mc57_reference.json")
    p.add_argument("--golden-fixture", default="tests/fixtures/mc57_recovery_golden_20260909_11.json")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    root = Path(args.data_dir)
    state_path = root / "state.json"
    if not state_path.is_file():
        raise SystemExit("state.json is required before MC57 calculation")
    state = _load(state_path)
    session = state.get("session_date")
    generated_at = state.get("generated_at")
    if not isinstance(session, str) or not session:
        raise SystemExit("state.session_date is required")
    if not isinstance(generated_at, str) or not generated_at:
        raise SystemExit("state.generated_at is required")

    reference = load_verified_reference(args.reference, args.golden_fixture)
    output = root / "mc57.json"
    if output.is_file() and not args.force:
        try:
            existing = _load(output)
        except Exception:
            existing = {}
        ref = existing.get("reference") if isinstance(existing.get("reference"), dict) else {}
        if (
            existing.get("session_date") == session
            and existing.get("status") == "READY"
            and existing.get("calculation_version") == CALCULATION_VERSION
            and existing.get("history_contract_version") == HISTORY_CONTRACT_VERSION
            and existing.get("etf_universe") == list(FIXED_57_ETFS)
            and ref.get("golden_fixture_sha256") == reference.get("golden_fixture_sha256")
        ):
            print(json.dumps({
                "session_date": session,
                "status": "READY",
                "reused": True,
                "mc57": existing.get("mc57"),
                "coverage": existing.get("coverage"),
                "history_sessions": existing.get("history_window_sessions"),
            }, sort_keys=True))
            return 0

    closes, fetch_stats = download_fixed57_adjusted_closes(yf, target_session=session)
    obj = build_mc57_object(
        closes=closes,
        target_session=session,
        generated_at=generated_at,
        reference=reference,
        fetch_stats=fetch_stats,
    )
    obj = enrich_mc57_history(obj, closes=closes, target_session=session)
    write_mc57_json(output, obj)
    print(json.dumps({
        "session_date": session,
        "status": obj["status"],
        "reused": False,
        "mc57": obj["mc57"],
        "raw": obj["raw"],
        "coverage": obj["coverage"],
        "current_close_count": obj["coverage_detail"]["current_close_count"],
        "history_sessions": obj.get("history_window_sessions"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
