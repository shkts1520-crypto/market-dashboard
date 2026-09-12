#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.market_engine import calculate_market_from_files
from v38.recovered_live_inputs import (
    build_classifications,
    build_recovered_nqsar,
    build_rotation_diagnostics,
    fetch_tradingview_fundamentals,
    write_json,
)
from v38.recovered_theme import write_theme_outputs

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


def _resolve_theme_map(configured: str, root: Path) -> tuple[Path, bool]:
    """Prefer the complete split legacy map when present.

    GitHub connector payloads have a practical per-call size ceiling, so the
    recovered 5k+ ticker map is committed as ordered base64 chunks. They are
    concatenated losslessly at runtime and decoded by recovered_theme.py.
    """
    configured_path = Path(configured)
    parts = sorted(configured_path.parent.glob("theme_s2t.part*.b64"))
    if not parts:
        return configured_path, False
    if len(parts) < 2:
        raise SystemExit(f"incomplete split theme map: found {len(parts)} part(s)")
    combined = "".join(part.read_text(encoding="utf-8").strip() for part in parts)
    if len(combined) < 40000:
        raise SystemExit(f"split theme map unexpectedly small: {len(combined)} base64 chars")
    temp_path = root / ".theme_s2t_recovered.b64"
    temp_path.write_text(combined, encoding="utf-8")
    return temp_path, True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover current V38 non-options inputs from legacy acquisition/calculation logic without restoring obsolete trading rules"
    )
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--theme-map", default="config/theme_s2t.json.gz.b64")
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
    write_json(root / "classifications.json", classifications)

    theme_map_path, cleanup_theme_map = _resolve_theme_map(args.theme_map, root)
    try:
        membership_path, recovered_rotation_path, theme_scores_path = write_theme_outputs(
            root,
            rs,
            session_date=session,
            generated_at=generated_at,
            theme_map_path=theme_map_path,
        )
    finally:
        if cleanup_theme_map:
            theme_map_path.unlink(missing_ok=True)
    theme_membership = _load(membership_path)
    theme_scores = _load(theme_scores_path)

    analytics = build_rotation_diagnostics(
        rs,
        session_date=session,
        generated_at=generated_at,
    )
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
    tag_detail = theme_membership.get("coverage_detail", {}) if isinstance(theme_membership, dict) else {}
    print(json.dumps({
        "session_date": session,
        "nqsar": nqsar.get("state"),
        "nqsar_mode": nqsar_mode,
        "nqsar_authoritative_exact": bool(nqsar.get("authoritative_exact")),
        "classification_rows": len(classifications.get("rows") or []),
        "classification_revenue_coverage": classifications.get("coverage_detail", {}).get("revenue_ttm_available"),
        "theme_rows": len(theme_scores.get("rows") or []),
        "theme_tag_exact": tag_detail.get("exact"),
        "theme_tag_inferred": tag_detail.get("inferred"),
        "theme_tag_unmapped": tag_detail.get("unmapped"),
        "theme_membership_coverage": theme_membership.get("coverage") if isinstance(theme_membership, dict) else None,
        "theme_trade_score_policy": "neutral_50_until_full_LOO_restored",
        "theme_rotation_recovered": recovered_rotation_path.as_posix(),
        "rotation_industries": len(analytics.get("industry") or []),
        "rotation_sectors": len(analytics.get("sector") or []),
        "market_mode": market.get("market_mode"),
        "core12_ranking_status": core.get("ranking_status"),
        "core12_rows": len(core.get("ranking") or []),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
