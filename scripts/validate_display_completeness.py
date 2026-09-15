#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


NO_CONTRACT = "NO_VALID_0_45_DTE_CONTRACTS"
MIN_STOCK_COVERAGE = 0.98


def load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise AssertionError(f"missing required file: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise AssertionError(f"expected object: {path}")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail publication when display data is genuinely missing")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--site-dir", default="_site")
    args = parser.parse_args()

    root = Path(args.data_dir)
    site = Path(args.site_dir)
    state = load(root / "state.json")
    manifest = load(root / "acquisition_manifest.json")
    options = load(root / "options" / "index.json")
    search = load(root / "history" / "search_index.json")
    vwap = load(root / "history" / "vwap_restore.json")

    session = str(state.get("session_date") or "")
    assert session, "state.session_date missing"
    assert state.get("status") == "READY", state.get("status")
    assert float(state.get("coverage") or 0.0) >= MIN_STOCK_COVERAGE, state.get("coverage")

    yahoo = manifest.get("yahoo") or {}
    requested = int(yahoo.get("requested") or 0)
    received = int(yahoo.get("target_session_received") or 0)
    assert requested > 0, requested
    assert received / requested >= MIN_STOCK_COVERAGE, (received, requested)
    assert float(yahoo.get("target_session_coverage") or 0.0) >= MIN_STOCK_COVERAGE
    failed_tickers = yahoo.get("failed_tickers") or []
    assert len(failed_tickers) <= requested - received, (len(failed_tickers), requested - received)

    universe = manifest.get("universe") or {}
    active = int(universe.get("active_universe") or 0)
    assert active == requested, (active, requested)

    assert options.get("session_date") == session
    assert options.get("status") in {"READY", "DATA_REQUIRED"}, options.get("status")
    detail = options.get("coverage_detail") or {}
    targets = int(detail.get("target_count") or 0)
    snapshots = int(detail.get("ticker_snapshots") or 0)
    assert targets > 0, targets
    failures = options.get("failures") or {}
    if options.get("status") == "READY":
        assert snapshots == targets, (snapshots, targets)
        assert float(detail.get("ticker_snapshot_coverage") or 0.0) == 1.0
        assert not (options.get("fetch_errors") or {}), options.get("fetch_errors")
        invalid_failure_codes = {
            ticker: reason for ticker, reason in failures.items() if reason != NO_CONTRACT
        }
        assert not invalid_failure_codes, invalid_failure_codes
    else:
        assert options.get("reason"), "DATA_REQUIRED options must expose a reason"

    chart_contract = options.get("chart_ohlc_contract") or {}
    chart_target_count = int(chart_contract.get("target_count") or 0)
    chart_ready_count = int(chart_contract.get("ready_count") or 0)
    if options.get("status") == "READY":
        assert chart_contract.get("status") == "READY", chart_contract
        assert chart_target_count > 0, chart_contract
        assert chart_ready_count == chart_target_count, chart_contract
        assert float(chart_contract.get("coverage") or 0.0) == 1.0, chart_contract

    assert search.get("session_date") == session
    assert search.get("status") == "READY", search.get("status")
    search_rows = search.get("rows") or []
    assert isinstance(search_rows, list)
    assert active > 0, active
    search_coverage = len(search_rows) / active
    assert search_coverage >= MIN_STOCK_COVERAGE, (len(search_rows), active, search_coverage)
    search_tickers = {
        str(row.get("ticker") or "").strip().upper()
        for row in search_rows if isinstance(row, dict)
    }
    assert len(search_tickers) == len(search_rows), (len(search_tickers), len(search_rows))
    unindexed = active - len(search_rows)
    assert unindexed <= len(failed_tickers), (unindexed, len(failed_tickers))

    assert vwap.get("session_date") == session
    assert vwap.get("status") == "READY", vwap.get("status")
    assert int(vwap.get("inception_pending") or 0) == 0, vwap.get("inception_pending")
    attempted = int(vwap.get("inception_bootstrap_attempted") or 0)
    boot_ready = int(vwap.get("inception_bootstrap_ready") or 0)
    assert boot_ready == attempted, (boot_ready, attempted)

    fallback_asset = site / "assets" / "v38-tradingview-fallback.js"
    fallback = fallback_asset.read_text(encoding="utf-8")
    assert "embed-widget-advanced-chart.js" in fallback
    assert "tradingview-live" in fallback
    assert NO_CONTRACT in fallback

    index = (site / "index.html").read_text(encoding="utf-8")
    assert "assets/v38-tradingview-fallback.js" in index

    print(json.dumps({
        "status": "READY",
        "session_date": session,
        "stock_requested": requested,
        "stock_received": received,
        "stock_failed": len(failed_tickers),
        "search_rows": len(search_rows),
        "search_coverage": search_coverage,
        "search_unindexed": unindexed,
        "options_targets": targets,
        "options_snapshots": snapshots,
        "options_no_contract": len(failures),
        "options_fetch_errors": len(options.get("fetch_errors") or {}),
        "priority_chart_targets": chart_target_count,
        "priority_chart_ready": chart_ready_count,
        "vwap_inception_pending": int(vwap.get("inception_pending") or 0),
        "search_uncached_chart_policy": "TRADINGVIEW_LIVE_FALLBACK",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
