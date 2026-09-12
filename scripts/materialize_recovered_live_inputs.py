#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from v38.intraday_inputs import IntradayInputError, fetch_and_patch_qqq_intraday
from v38.market_engine import calculate_market_from_files
from v38.peer_theme_engine import (
    PeerThemeError,
    augment_rs_peer_theme_inputs,
    write_strict_loo_peer_theme_scores,
)
from v38.recovered_live_inputs import (
    build_classifications,
    build_recovered_nqsar,
    build_rotation_diagnostics,
    fetch_tradingview_fundamentals,
    write_json,
)
from v38.recovered_theme import write_theme_outputs
from v38.stock_gap_repair import repair_failed_live_tickers

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
    """Prefer the complete split legacy map when present."""
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


def _live_work_dir() -> Path | None:
    explicit = os.environ.get("V38_LIVE_WORK_DIR")
    if explicit:
        path = Path(explicit)
        return path if path.is_dir() else None
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp:
        path = Path(runner_temp) / "v38-live"
        return path if path.is_dir() else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover current V38 non-options inputs from legacy acquisition/calculation logic without restoring obsolete trading rules"
    )
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--theme-map", default="config/theme_s2t.json.gz.b64")
    parser.add_argument("--theme-overrides", default="config/theme_manual_overrides.json")
    parser.add_argument("--no-fundamentals", action="store_true")
    parser.add_argument("--no-intraday", action="store_true")
    args = parser.parse_args()

    root = Path(args.data_dir)
    state = _load(root / "state.json")
    if not state:
        raise SystemExit("state.json is required")
    session = str(state.get("session_date") or "")
    generated_at = str(state.get("generated_at") or "")
    if not session or not generated_at:
        raise SystemExit("state session_date/generated_at are required")

    work = _live_work_dir()
    gap_repair = {"status": "NOT_RUN", "repaired": [], "remaining": []}
    if work is not None and (work / "ohlcv.csv").is_file() and (work / "universe.csv").is_file():
        gap_repair = repair_failed_live_tickers(
            root,
            work,
            generated_at=generated_at,
        )

    rs = _load(root / "rs.json")
    breadth = _load(root / "breadth.json")
    market_inputs = _load(root / "market_inputs.json")
    if not rs or not breadth or not market_inputs:
        raise SystemExit("rs/breadth/market_inputs are required")

    peer_input_status = "PREEXISTING"
    if work is not None and (work / "ohlcv.csv").is_file():
        try:
            rs = augment_rs_peer_theme_inputs(root / "rs.json", work / "ohlcv.csv")
            peer_input_status = "REFRESHED_FROM_CURRENT_OHLCV"
        except PeerThemeError as exc:
            peer_input_status = f"DATA_REQUIRED:{exc}"

    intraday_status = str(market_inputs.get("qqq_4h_status") or "DATA_REQUIRED")
    if not args.no_intraday:
        try:
            market_inputs = fetch_and_patch_qqq_intraday(
                root / "market_inputs.json",
                target_session=session,
                generated_at=generated_at,
            )
            intraday_status = str(market_inputs.get("qqq_4h_status") or "DATA_REQUIRED")
        except IntradayInputError as exc:
            intraday_status = f"DATA_REQUIRED:{exc}"

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
        membership_path, recovered_rotation_path, _neutral_theme_scores_path = write_theme_outputs(
            root,
            rs,
            session_date=session,
            generated_at=generated_at,
            theme_map_path=theme_map_path,
            theme_overrides_path=args.theme_overrides,
        )
    finally:
        if cleanup_theme_map:
            theme_map_path.unlink(missing_ok=True)

    theme_membership = _load(membership_path)
    theme_scores_path = write_strict_loo_peer_theme_scores(
        root / "rs.json",
        membership_path,
        root / "theme_scores.json",
        session_date=session,
        generated_at=generated_at,
    )
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
    score_detail = theme_scores.get("coverage_detail", {}) if isinstance(theme_scores, dict) else {}
    print(json.dumps({
        "session_date": session,
        "nqsar": nqsar.get("state"),
        "nqsar_mode": nqsar_mode,
        "nqsar_authoritative_exact": bool(nqsar.get("authoritative_exact")),
        "qqq_4h_status": intraday_status,
        "qqq_4h_trading_gate_eligible": bool(market_inputs.get("qqq_4h_trading_gate_eligible")),
        "stock_gap_repair_status": gap_repair.get("status"),
        "stock_gap_repaired": gap_repair.get("repaired"),
        "stock_gap_remaining": gap_repair.get("remaining"),
        "classification_rows": len(classifications.get("rows") or []),
        "classification_revenue_coverage": classifications.get("coverage_detail", {}).get("revenue_ttm_available"),
        "theme_rows": len(theme_scores.get("rows") or []),
        "theme_tag_exact": tag_detail.get("exact"),
        "theme_tag_manual": tag_detail.get("manual"),
        "theme_tag_inferred": tag_detail.get("inferred"),
        "theme_tag_unmapped": tag_detail.get("unmapped"),
        "theme_membership_coverage": theme_membership.get("coverage") if isinstance(theme_membership, dict) else None,
        "theme_trade_score_policy": "strict_loo_equal_weight_a_b_c",
        "theme_trade_score_ready": score_detail.get("strict_loo_ready"),
        "theme_trade_score_partial": score_detail.get("partial_neutral_component"),
        "peer_theme_input_status": peer_input_status,
        "peer_theme_input_coverage": rs.get("peer_theme_input_coverage"),
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
