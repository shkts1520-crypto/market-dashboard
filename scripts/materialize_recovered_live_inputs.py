#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.market_engine import calculate_market_from_files
from v38.recovered_live_inputs import (
    build_classifications,
    build_neutral_theme_scores,
    build_recovered_nqsar,
    build_rotation_diagnostics,
    fetch_tradingview_fundamentals,
    write_json,
)

AUTHORITATIVE_INPUT_KINDS = {"state", "EXP_STATE_ID"}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _current_authoritative_nqsar(obj: dict, session: str) -> bool:
    if obj.get("session_date") != session or obj.get("status") not in {"READY", "AUTHORITATIVE_INPUT"}:
        return False
    if obj.get("authoritative_exact") is True:
        return True
    return str(obj.get("input_kind") or "") in AUTHORITATIVE_INPUT_KINDS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover current V38 non-options inputs from legacy acquisition/calculation logic without restoring obsolete trading rules"
    )
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--no-fundamentals", action="store_true")
    args = parser.parse_args()

    root = Path(args.data_dir)
    state = _load(root / "state.json")
    rs = _load(root / "rs.json")
    breadth = _load(root / "breadth.json")
    market_inputs = _load(root / "market_inputs.json")
    if not state or not rs or not breadth or not market_inputs:
        raise SystemExit("state/rs/breadth/market_inputs are required")
    session = str(state.get("session_date") or "")
    generated_at = str(state.get("generated_at") or "")
    if not session or not generated_at:
        raise SystemExit("state session_date/generated_at are required")

    existing_nqsar = _load(root / "nqsar.json")
    if _current_authoritative_nqsar(existing_nqsar, session):
        nqsar = existing_nqsar
        nqsar_mode = "PRESERVED_AUTHORITATIVE"
    else:
        nqsar = build_recovered_nqsar(
            market_inputs,
            session_date=session,
            generated_at=generated_at,
        )
        write_json(root / "nqsar.json", nqsar)
        nqsar_mode = "RECOVERED_YAHOO_FSM_ESTIMATE"

    fundamentals = {} if args.no_fundamentals else fetch_tradingview_fundamentals()
    classifications = build_classifications(
        rs,
        fundamentals,
        session_date=session,
        generated_at=generated_at,
    )
    theme_scores = build_neutral_theme_scores(
        rs,
        session_date=session,
        generated_at=generated_at,
    )
    analytics = build_rotation_diagnostics(
        rs,
        session_date=session,
        generated_at=generated_at,
    )
    write_json(root / "classifications.json", classifications)
    write_json(root / "theme_scores.json", theme_scores)
    write_json(root / "analytics.json", analytics)

    market_path, core12_path = calculate_market_from_files(
        root / "rs.json",
        root / "breadth.json",
        root / "nqsar.json",
        root,
        generated_at=generated_at,
        classifications_path=root / "classifications.json",
        theme_scores_path=root / "theme_scores.json",
    )
    market = _load(market_path)
    core = _load(core12_path)
    print(json.dumps({
        "session_date": session,
        "nqsar": nqsar.get("state"),
        "nqsar_mode": nqsar_mode,
        "nqsar_authoritative_exact": bool(nqsar.get("authoritative_exact")),
        "classification_rows": len(classifications.get("rows") or []),
        "classification_revenue_coverage": classifications.get("coverage_detail", {}).get("revenue_ttm_available"),
        "theme_rows": len(theme_scores.get("rows") or []),
        "theme_missing_policy": "neutral_50",
        "rotation_industries": len(analytics.get("industry") or []),
        "rotation_sectors": len(analytics.get("sector") or []),
        "market_mode": market.get("market_mode"),
        "core12_ranking_status": core.get("ranking_status"),
        "core12_rows": len(core.get("ranking") or []),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
