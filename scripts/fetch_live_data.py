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
from v38.nqsar_input import NQSARInputError, normalize_nqsar_file
from v38.stock_adapter import calculate_from_files


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


def _validate_same_session(stage: Path, expected: str, names: tuple[str, ...]) -> None:
    for name in names:
        obj = json.loads((stage / name).read_text(encoding="utf-8"))
        if obj.get("session_date") != expected:
            raise LiveAcquisitionError(
                f"{name}: session mismatch {obj.get('session_date')} != {expected}"
            )
        if not obj.get("generated_at"):
            raise LiveAcquisitionError(f"{name}: generated_at missing")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Acquire current authoritative V38 stock and market inputs"
    )
    p.add_argument("--data-dir", default="data")
    p.add_argument("--work-dir")
    p.add_argument("--generated-at")
    p.add_argument("--sar-state", default="sar_state.txt")
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
    f123_path = stage / "f123.json"
    calculate_f123_from_files(
        rs_path,
        f123_path,
        generated_at=generated_at,
        old_top24_path=None,
    )

    market_inputs = download_market_inputs(
        yf,
        target_session=session_date,
        generated_at=generated_at,
    )
    write_json(stage / "market_inputs.json", market_inputs)

    nqsar_status = "DATA_REQUIRED"
    sar_state = Path(args.sar_state)
    if sar_state.exists():
        try:
            normalize_nqsar_file(
                sar_state,
                stage / "nqsar.json",
                expected_session_date=session_date,
                as_of=generated_at,
            )
            nqsar_status = "READY"
        except NQSARInputError as exc:
            nqsar_status = f"DATA_REQUIRED:{exc}"

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

    required = (
        "rs.json",
        "breadth.json",
        "f123.json",
        "market_inputs.json",
        "state.json",
        "acquisition_manifest.json",
    )
    _validate_same_session(stage, session_date, required)

    promoted = list(required)
    if (stage / "nqsar.json").exists():
        _validate_same_session(stage, session_date, ("nqsar.json",))
        promoted.append("nqsar.json")

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
                "published": promoted,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
