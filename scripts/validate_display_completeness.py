#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


NO_CONTRACT = "NO_VALID_0_45_DTE_CONTRACTS"
MIN_STOCK_COVERAGE = 0.98
OPTION_MIN_PRICE_USD = 5.0
REQUESTED_MIN_MARKET_CAP_USD = 1_000_000.0
FULL_UNIVERSE_BUCKETS = {"0-6", "7-21", "22-45", "0-45"}


def load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise AssertionError(f"missing required file: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise AssertionError(f"expected object: {path}")
    return obj


def _clean_symbols(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value or "").strip().upper() for value in values if str(value or "").strip()]


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _price_filtered_symbols(rows: Any, *, floor: float = OPTION_MIN_PRICE_USD) -> list[str]:
    if not isinstance(rows, list):
        return []
    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        price = _finite(row.get("price"))
        if ticker and price is not None and price >= floor:
            out.add(ticker)
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail publication when display data is genuinely missing")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--site-dir", default="_site")
    args = parser.parse_args()

    root = Path(args.data_dir)
    site = Path(args.site_dir)
    state = load(root / "state.json")
    manifest = load(root / "acquisition_manifest.json")
    rs = load(root / "rs.json")
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
    assert targets > 0, targets
    failures = options.get("failures") or {}
    target_policy = options.get("target_policy") or {}
    full_universe = target_policy.get("status") == "FULL_ACTIVE_UNIVERSE"

    if full_universe:
        policy_targets = _clean_symbols(target_policy.get("targets"))
        published = int(detail.get("published_tickers") or 0)
        resolved = int(detail.get("resolved_tickers") or 0)
        resolution_coverage = float(detail.get("universe_resolution_coverage") or 0.0)
        no_contract = sum(1 for reason in failures.values() if reason == NO_CONTRACT)
        scan = options.get("universe_scan") or {}
        overlay = options.get("chart_overlay_contract") or {}

        # Full Options coverage now means all tickers in the investable Options
        # subset, not every upstream active ticker. The upstream TradingView
        # universe already has market cap >= $200M, which is stricter than the
        # requested >=$1M floor; Options additionally require current price >=$5.
        assert target_policy.get("scope") == "INVESTABLE_PRICE_FILTERED", target_policy
        assert float(target_policy.get("min_price_usd") or 0.0) == OPTION_MIN_PRICE_USD, target_policy
        upstream_mcap = float(target_policy.get("upstream_min_market_cap_usd") or 0.0)
        assert upstream_mcap >= REQUESTED_MIN_MARKET_CAP_USD, target_policy
        expected_policy_targets = _price_filtered_symbols(rs.get("rows"))

        assert overlay.get("all_universe") is True, overlay
        assert 0 < targets <= active, (targets, active)
        assert len(policy_targets) == targets, (len(policy_targets), targets)
        assert len(set(policy_targets)) == targets, "duplicate full-universe option targets"
        assert policy_targets == expected_policy_targets, (
            len(policy_targets), len(expected_policy_targets),
            sorted(set(policy_targets) - set(expected_policy_targets))[:20],
            sorted(set(expected_policy_targets) - set(policy_targets))[:20],
        )
        assert 0 <= published <= resolved <= targets, (published, resolved, targets)
        assert resolved == published + no_contract, (resolved, published, no_contract)
        expected_coverage = resolved / targets
        assert abs(resolution_coverage - expected_coverage) < 1e-12, (resolution_coverage, expected_coverage)

        assert scan.get("mode") == "FULL_ACTIVE_UNIVERSE", scan
        assert scan.get("scope") == "INVESTABLE_PRICE_FILTERED", scan
        assert float(scan.get("min_price_usd") or 0.0) == OPTION_MIN_PRICE_USD, scan
        assert float(scan.get("upstream_min_market_cap_usd") or 0.0) >= REQUESTED_MIN_MARKET_CAP_USD, scan
        assert int(scan.get("target_count") or 0) == targets, scan
        assert int(scan.get("resolved_count") or 0) == resolved, scan
        assert int(scan.get("positioning_count") or 0) == published, scan
        assert int(scan.get("no_valid_0_45_dte_count") or 0) == no_contract, scan
        assert abs(float(scan.get("resolution_coverage") or 0.0) - resolution_coverage) < 1e-12, scan

        rankings = options.get("upward_rankings") or {}
        assert isinstance(rankings, dict), type(rankings).__name__
        assert FULL_UNIVERSE_BUCKETS.issubset(rankings), sorted(rankings)
        published_symbols = {
            str(row.get("ticker") or "").strip().upper()
            for row in (options.get("rows") or []) if isinstance(row, dict)
        }
        assert len(published_symbols) == published, (len(published_symbols), published)
        for bucket in FULL_UNIVERSE_BUCKETS:
            bucket_rows = rankings.get(bucket)
            assert isinstance(bucket_rows, list), (bucket, type(bucket_rows).__name__)
            ranked_symbols = _clean_symbols([
                row.get("ticker") for row in bucket_rows if isinstance(row, dict)
            ])
            assert len(ranked_symbols) == len(set(ranked_symbols)), (bucket, "duplicate ranking tickers")
            assert set(ranked_symbols).issubset(published_symbols), (bucket, sorted(set(ranked_symbols) - published_symbols)[:20])

        if options.get("status") == "READY":
            ready_threshold = float(scan.get("ready_threshold") or 0.98)
            assert scan.get("status") == "READY", scan
            assert resolution_coverage >= ready_threshold, (resolution_coverage, ready_threshold)
        else:
            assert options.get("reason"), "DATA_REQUIRED options must expose a reason"
    else:
        snapshots = int(detail.get("ticker_snapshots") or 0)
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
        published = snapshots
        resolved = snapshots
        resolution_coverage = float(detail.get("ticker_snapshot_coverage") or 0.0)
        no_contract = sum(1 for reason in failures.values() if reason == NO_CONTRACT)

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

    if full_universe:
        search_eligible = set(_price_filtered_symbols(search_rows))
        assert set(policy_targets) == search_eligible, (
            len(set(policy_targets) - search_eligible),
            len(search_eligible - set(policy_targets)),
        )

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
        "options_target_policy": target_policy.get("status"),
        "options_scope": target_policy.get("scope"),
        "options_min_price_usd": target_policy.get("min_price_usd"),
        "options_upstream_min_market_cap_usd": target_policy.get("upstream_min_market_cap_usd"),
        "options_targets": targets,
        "options_resolved": resolved,
        "options_positioning": published,
        "options_resolution_coverage": resolution_coverage,
        "options_no_contract": no_contract,
        "options_fetch_errors": len(options.get("fetch_errors") or {}),
        "priority_chart_targets": chart_target_count,
        "priority_chart_ready": chart_ready_count,
        "vwap_inception_pending": int(vwap.get("inception_pending") or 0),
        "search_uncached_chart_policy": "TRADINGVIEW_LIVE_FALLBACK",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
