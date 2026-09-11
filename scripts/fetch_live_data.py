#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from v38.f123_engine import calculate_f123_from_files
from v38.live_acquisition import (
    LiveAcquisitionError,
    choose_completed_session,
    download_market_inputs,
    download_stock_ohlcv,
    fetch_benchmark_frames,
    fetch_tradingview_response,
    frame_dates,
    manifest_object,
    parse_tradingview_universe,
    previous_active_universe,
    state_object,
    validate_universe_count,
    write_json,
    write_universe_csv,
)
from v38.market_engine import calculate_market_from_files
from v38.market_status import normalize_market_statuses
from v38.nqsar_input import NQSARInputError, normalize_nqsar_file
from v38.stock_adapter import calculate_from_files
from v38.supplemental_engine import materialize_supplemental_shards


def _atomic_promote(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=dst.name + ".", dir=dst.parent)
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        shutil.copyfile(src, tmp_path)
        os.replace(tmp_path, dst)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _current_path(path: Path, session_date: str) -> Path | None:
    obj = _load(path)
    return path if obj is not None and obj.get("session_date") == session_date else None


def _copy_current(src: Path, stage: Path, session_date: str, relative_name: str) -> Path | None:
    current = _current_path(src, session_date)
    if current is None:
        return None
    dst = stage / relative_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(current, dst)
    return dst


def _validate_same_session(stage: Path, expected: str, names: tuple[str, ...]) -> None:
    for name in names:
        path = stage / name
        if not path.exists():
            raise LiveAcquisitionError(f"{name}: required staged output missing")
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("session_date") != expected:
            raise LiveAcquisitionError(
                f"{name}: session mismatch {obj.get('session_date')} != {expected}"
            )
        if not obj.get("generated_at"):
            raise LiveAcquisitionError(f"{name}: generated_at missing")
        for key in ("source", "schema_version", "calculation_version"):
            if not isinstance(obj.get(key), str) or not obj[key].strip():
                raise LiveAcquisitionError(f"{name}: {key} missing")


def _resolve_optional(args_value: str | None, default_path: Path, session_date: str) -> Path | None:
    if args_value:
        path = Path(args_value)
        return _current_path(path, session_date)
    return _current_path(default_path, session_date)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Acquire, calculate and materialize current authoritative V38 data"
    )
    p.add_argument("--data-dir", default="data")
    p.add_argument("--work-dir")
    p.add_argument("--generated-at")
    p.add_argument("--sar-state", default="sar_state.txt")
    p.add_argument("--old-top24")
    p.add_argument("--classifications")
    p.add_argument("--theme-scores")
    p.add_argument("--positions-ledger")
    p.add_argument("--mc57")
    p.add_argument("--options-index")
    args = p.parse_args()

    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("yfinance==0.2.66 is required for live acquisition") from exc

    generated_at = (
        args.generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    data_dir = Path(args.data_dir)
    work_root = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix="v38-live-"))
    work_root.mkdir(parents=True, exist_ok=True)
    stage = work_root / "stage"
    stage.mkdir(parents=True, exist_ok=True)

    benchmarks = fetch_benchmark_frames(yf)
    session_date = choose_completed_session(
        frame_dates(benchmarks["QQQ"]),
        frame_dates(benchmarks["SPY"]),
    )

    tv_response = fetch_tradingview_response()
    universe_rows, universe_stats = parse_tradingview_universe(
        tv_response,
        session_date=session_date,
    )
    previous_count = previous_active_universe(data_dir / "rs.json")
    validate_universe_count(len(universe_rows), previous_count)
    universe_stats["previous_active_universe"] = previous_count
    universe_stats["count_guard_ratio"] = 0.80

    universe_path = write_universe_csv(work_root / "universe.csv", universe_rows)
    ohlcv_path = work_root / "ohlcv.csv"
    yahoo_stats = download_stock_ohlcv(
        yf,
        [row["ticker"] for row in universe_rows],
        target_session=session_date,
        output_path=ohlcv_path,
    )

    source = "TradingView america/scan universe + Yahoo Finance/yfinance 0.2.66 adjusted by Adj Close"
    rs_path, breadth_path = calculate_from_files(
        ohlcv_path,
        universe_path,
        stage,
        session_date=session_date,
        generated_at=generated_at,
        source=source,
    )

    old_top24 = _resolve_optional(args.old_top24, data_dir / "old_top24.json", session_date)
    # old_top24.session_date is intentionally old, so target_session_date rather than
    # top-level session_date determines whether it belongs to this calculation.
    if args.old_top24:
        candidate = Path(args.old_top24)
    else:
        candidate = data_dir / "old_top24.json"
    old_obj = _load(candidate)
    if old_obj is not None and old_obj.get("target_session_date") == session_date:
        old_top24 = candidate
    else:
        old_top24 = None

    f123_path = stage / "f123.json"
    calculate_f123_from_files(
        rs_path,
        f123_path,
        generated_at=generated_at,
        old_top24_path=old_top24,
    )

    market_inputs = download_market_inputs(
        yf,
        target_session=session_date,
        generated_at=generated_at,
    )
    write_json(stage / "market_inputs.json", market_inputs)

    nqsar_status = "DATA_REQUIRED"
    nqsar_source: Path | None = None
    explicit_sar = Path(args.sar_state)
    if explicit_sar.exists():
        nqsar_source = explicit_sar
    elif (data_dir / "nqsar.json").exists():
        nqsar_source = data_dir / "nqsar.json"

    if nqsar_source is not None:
        try:
            normalize_nqsar_file(
                nqsar_source,
                stage / "nqsar.json",
                expected_session_date=session_date,
                as_of=generated_at,
            )
            nqsar_status = "READY"
        except NQSARInputError as exc:
            nqsar_status = f"DATA_REQUIRED:{exc}"

    classifications = _resolve_optional(
        args.classifications,
        data_dir / "classifications.json",
        session_date,
    )
    theme_scores = _resolve_optional(
        args.theme_scores,
        data_dir / "theme_scores.json",
        session_date,
    )
    positions_ledger = _resolve_optional(
        args.positions_ledger,
        data_dir / "positions_ledger.json",
        session_date,
    )

    if (stage / "nqsar.json").exists():
        calculate_market_from_files(
            rs_path,
            breadth_path,
            stage / "nqsar.json",
            stage,
            generated_at=generated_at,
            classifications_path=classifications,
            theme_scores_path=theme_scores,
        )
        normalize_market_statuses(stage, session_date=session_date)

    # Preserve only current-session optional authorities. Stale authorities are not
    # copied into the staged publication and therefore cannot look current.
    mc57_source = Path(args.mc57) if args.mc57 else data_dir / "mc57.json"
    options_source = Path(args.options_index) if args.options_index else data_dir / "options" / "index.json"
    _copy_current(mc57_source, stage, session_date, "mc57.json")
    _copy_current(options_source, stage, session_date, "options/index.json")
    if theme_scores is not None:
        _copy_current(theme_scores, stage, session_date, "theme_scores.json")
    if positions_ledger is not None:
        _copy_current(positions_ledger, stage, session_date, "positions_ledger.json")
    if classifications is not None:
        _copy_current(classifications, stage, session_date, "classifications.json")
    if old_top24 is not None:
        dst = stage / "old_top24.json"
        shutil.copyfile(old_top24, dst)

    coverage = float(yahoo_stats["target_session_coverage"])
    write_json(
        stage / "state.json",
        state_object(
            session_date=session_date,
            generated_at=generated_at,
            coverage=coverage,
        ),
    )
    write_json(
        stage / "acquisition_manifest.json",
        manifest_object(
            session_date=session_date,
            generated_at=generated_at,
            universe_stats=universe_stats,
            yahoo_stats=yahoo_stats,
            nqsar_status=nqsar_status,
        ),
    )

    materialize_supplemental_shards(
        stage,
        session_date=session_date,
        generated_at=generated_at,
        theme_scores_path=stage / "theme_scores.json" if (stage / "theme_scores.json").exists() else None,
        positions_ledger_path=stage / "positions_ledger.json" if (stage / "positions_ledger.json").exists() else None,
    )
    normalize_market_statuses(stage, session_date=session_date)

    required = (
        "rs.json",
        "breadth.json",
        "f123.json",
        "market_inputs.json",
        "state.json",
        "acquisition_manifest.json",
        "market_state.json",
        "core12.json",
        "mc57.json",
        "positions.json",
        "rotation.json",
        "weekly.json",
        "options/index.json",
        "publish.json",
        "rules.json",
    )
    _validate_same_session(stage, session_date, required)

    promoted = list(required)
    for optional_name in (
        "nqsar.json",
        "theme_scores.json",
        "positions_ledger.json",
        "classifications.json",
        "old_top24.json",
    ):
        if (stage / optional_name).exists():
            if optional_name != "old_top24.json":
                _validate_same_session(stage, session_date, (optional_name,))
            promoted.append(optional_name)

    for name in promoted:
        _atomic_promote(stage / name, data_dir / name)

    print(
        json.dumps(
            {
                "status": "READY",
                "session_date": session_date,
                "generated_at": generated_at,
                "active_universe": len(universe_rows),
                "yahoo_target_coverage": coverage,
                "nqsar_status": nqsar_status,
                "f1_old_top24_status": "READY" if old_top24 is not None else "DATA_REQUIRED",
                "published": promoted,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
