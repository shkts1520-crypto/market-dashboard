#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import pandas as pd

import calculate_options_live_legacy as legacy
from v38.freshness import atomic_write_json
from v38.options_engine import (
    MIN_READY_TARGET_COVERAGE,
    MIN_READY_TICKERS,
    build_options_index,
    expiry_dte,
    frame_to_contracts,
)

CALCULATION_VERSION = "v38-options-live-1.1.0"
TICKER_SPACING_SECONDS = 0.80
EXPIRY_SPACING_SECONDS = 0.15
BATCH_SIZE = 8
BATCH_PAUSE_SECONDS = 3.0
RETRY_ROUND_COOLDOWNS = (20.0, 60.0)
GLOBAL_TRANSIENT_FAILURE_STREAK = 5
TRANSIENT_MARKERS = (
    "too many requests",
    "rate limit",
    "ratelimit",
    "yf ratelimit",
    "429",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
    "remote disconnected",
    "server error",
    "502",
    "503",
    "504",
)


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _is_transient_option_error(value) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in TRANSIENT_MARKERS)


def _same_session_previous_state(previous: dict, *, session: str, targets: list[str]) -> tuple[set[str], set[str]]:
    """Return cached-good and known-no-contract tickers for the same market session.

    Same-session successful rows are authoritative measurements, not a synthetic
    fallback. Reusing them prevents repeat workflow runs from re-requesting every
    chain and materially reduces Yahoo rate-limit pressure.
    """
    if not isinstance(previous, dict) or previous.get("session_date") != session:
        return set(), set()
    target_set = set(targets)
    cached_good = {
        str(row.get("ticker") or "").strip().upper()
        for row in (previous.get("rows") or [])
        if isinstance(row, dict)
    }
    cached_good &= target_set
    failures = previous.get("failures") if isinstance(previous.get("failures"), dict) else {}
    known_no_contract = {
        str(ticker).strip().upper()
        for ticker, reason in failures.items()
        if str(reason) == "NO_VALID_0_45_DTE_CONTRACTS"
    }
    known_no_contract &= target_set
    return cached_good, known_no_contract


def _fetch_ticker_snapshot_once(yf, ticker: str, *, spot: float, session_date: str) -> dict:
    symbol = ticker.replace(".", "-")
    obj = yf.Ticker(symbol)
    try:
        raw_expiries = obj.options or ()
    except Exception as exc:
        raise RuntimeError(f"{ticker}: option expiry fetch failed: {exc}") from exc

    expiries = [
        str(exp)
        for exp in raw_expiries
        if 0 <= expiry_dte(str(exp), session_date) <= 45
    ]
    if not expiries:
        return {
            "spot": spot,
            "contracts": [],
            "available_expiries": [],
            "fetched_expiries": [],
            "fetch_warnings": [],
        }

    contracts = []
    fetched_expiries: list[str] = []
    expiry_errors: dict[str, str] = {}
    for expiry in expiries:
        try:
            chain = obj.option_chain(expiry)
        except Exception as exc:
            expiry_errors[expiry] = str(exc)[:240]
            continue
        fetched_expiries.append(expiry)
        contracts.extend(frame_to_contracts(
            ticker=ticker,
            frame=chain.calls,
            side="call",
            expiry=expiry,
            session_date=session_date,
        ))
        contracts.extend(frame_to_contracts(
            ticker=ticker,
            frame=chain.puts,
            side="put",
            expiry=expiry,
            session_date=session_date,
        ))
        time.sleep(EXPIRY_SPACING_SECONDS)

    if not fetched_expiries and expiry_errors:
        joined = "; ".join(f"{expiry}:{message}" for expiry, message in expiry_errors.items())
        raise RuntimeError(f"{ticker}: all option-chain expiries failed: {joined[:500]}")

    return {
        "spot": spot,
        "contracts": contracts,
        "available_expiries": expiries,
        "fetched_expiries": fetched_expiries,
        "fetch_warnings": [f"{expiry}:{message}" for expiry, message in expiry_errors.items()],
    }


def _merge_same_session_rows(
    out: dict,
    previous: dict,
    *,
    session: str,
    targets: list[str],
    cached_good: set[str],
    known_no_contract: set[str],
) -> list[str]:
    if previous.get("session_date") != session:
        return []
    target_set = set(targets)
    reusable = cached_good & target_set
    if not reusable and not known_no_contract:
        return []

    previous_buckets = previous.get("buckets") if isinstance(previous.get("buckets"), dict) else {}
    current_buckets = out.get("buckets") if isinstance(out.get("buckets"), dict) else {}
    reused: set[str] = set()
    quality_order = {"GOOD": 0, "PARTIAL": 1}

    for bucket, rows in current_buckets.items():
        if not isinstance(rows, list):
            continue
        current_tickers = {
            str(row.get("ticker") or "").strip().upper()
            for row in rows if isinstance(row, dict)
        }
        prior_rows = previous_buckets.get(bucket) if isinstance(previous_buckets.get(bucket), list) else []
        for prior in prior_rows:
            if not isinstance(prior, dict):
                continue
            ticker = str(prior.get("ticker") or "").strip().upper()
            if ticker not in reusable or ticker in current_tickers:
                continue
            restored = copy.deepcopy(prior)
            restored["resilience_provenance"] = {
                "mode": "PRESERVED_LAST_GOOD_SAME_SESSION_TICKER",
                "source_generated_at": previous.get("generated_at"),
            }
            rows.append(restored)
            current_tickers.add(ticker)
            reused.add(ticker)
        rows.sort(key=lambda row: (
            quality_order.get(str(row.get("quality")), 9),
            -float(row.get("total_open_interest") or 0.0),
            str(row.get("ticker") or ""),
        ))
        for rank, row in enumerate(rows, start=1):
            row["data_rank"] = rank

    failures = out.get("failures") if isinstance(out.get("failures"), dict) else {}
    for ticker in reused:
        failures.pop(ticker, None)
    for ticker in known_no_contract:
        if ticker not in reused:
            failures[ticker] = "NO_VALID_0_45_DTE_CONTRACTS"
    out["failures"] = failures
    out["rows"] = current_buckets.get("0-45", [])

    successes = len({
        str(row.get("ticker") or "").strip().upper()
        for row in out.get("rows", [])
        if isinstance(row, dict)
    })
    coverage = successes / len(targets) if targets else 0.0
    out["coverage"] = coverage
    ready = successes >= MIN_READY_TICKERS and coverage >= MIN_READY_TARGET_COVERAGE
    out["status"] = "READY" if ready else "DATA_REQUIRED"
    out["reason"] = None if ready else "OPTION_CHAIN_COVERAGE_BELOW_MINIMUM"
    return sorted(reused)


def _fetch_with_rounds(
    yf,
    *,
    targets: list[str],
    spots: dict[str, float],
    session: str,
) -> tuple[dict[str, dict], dict[str, str], dict[str, str], int]:
    snapshots: dict[str, dict] = {}
    permanent_errors: dict[str, str] = {}
    transient_errors: dict[str, str] = {}
    pending = list(targets)
    global_breaks = 0

    total_rounds = 1 + len(RETRY_ROUND_COOLDOWNS)
    for round_index in range(total_rounds):
        if not pending:
            break
        if round_index > 0:
            cooldown = RETRY_ROUND_COOLDOWNS[round_index - 1]
            print(f"options retry round {round_index + 1}/{total_rounds}: cooling down {cooldown:.0f}s for {len(pending)} tickers")
            time.sleep(cooldown)

        retry_next: list[str] = []
        transient_streak = 0
        round_targets = list(pending)
        for position, ticker in enumerate(round_targets, start=1):
            spot = spots.get(ticker)
            if spot is None:
                permanent_errors[ticker] = "CURRENT_SPOT_MISSING"
                continue
            try:
                snapshots[ticker] = _fetch_ticker_snapshot_once(
                    yf,
                    ticker,
                    spot=spot,
                    session_date=session,
                )
                transient_errors.pop(ticker, None)
                transient_streak = 0
                status = "ok"
            except Exception as exc:
                message = str(exc)[:500]
                if _is_transient_option_error(message):
                    transient_errors[ticker] = message
                    retry_next.append(ticker)
                    transient_streak += 1
                    status = "transient"
                else:
                    permanent_errors[ticker] = message
                    transient_streak = 0
                    status = "failed"
            print(f"options round {round_index + 1} {position}/{len(round_targets)} {ticker} {status}")

            if transient_streak >= GLOBAL_TRANSIENT_FAILURE_STREAK:
                remaining = round_targets[position:]
                retry_next.extend(t for t in remaining if t not in retry_next)
                global_breaks += 1
                print(
                    f"options circuit breaker: {GLOBAL_TRANSIENT_FAILURE_STREAK} consecutive transient failures; "
                    f"deferring {len(remaining)} remaining tickers"
                )
                break

            if position % BATCH_SIZE == 0 and position < len(round_targets):
                time.sleep(BATCH_PAUSE_SECONDS)
            else:
                time.sleep(TICKER_SPACING_SECONDS)

        pending = [ticker for ticker in retry_next if ticker not in snapshots and ticker not in permanent_errors]

    for ticker in pending:
        transient_errors.setdefault(ticker, "TRANSIENT_OPTION_FETCH_RETRIES_EXHAUSTED")
    return snapshots, permanent_errors, transient_errors, global_breaks


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate resilient live V38 option positioning from Yahoo chains")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--target-limit", type=int, default=legacy.DEFAULT_TARGET_LIMIT)
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("yfinance==0.2.66 is required") from exc

    root = Path(args.data_dir)
    state = legacy._load(root / "state.json")
    rs = legacy._load(root / "rs.json")
    core12 = legacy._load(root / "core12.json")
    previous = legacy._load(root / "options" / "index.json")
    session = str(state.get("session_date") or "")
    if not session:
        raise SystemExit("state.json session_date is required")
    if rs.get("session_date") != session:
        raise SystemExit("rs.json is not current session")

    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    effective_limit = max(int(args.target_limit), legacy.CHART_TARGET_FLOOR)
    targets = legacy._chart_targets(rs, core12, requested_limit=effective_limit)
    if not targets:
        raise SystemExit("no option targets resolved")
    spots = legacy._spot_map(rs)

    try:
        rate, rate_source, rate_observed_date = legacy._risk_free_rate(
            yf,
            session_date=session,
            previous=previous,
        )
    except Exception as exc:
        if previous.get("session_date") == session and previous.get("status") == "READY":
            preserved = copy.deepcopy(previous)
            preserved["generated_at"] = generated_at
            preserved["calculation_version"] = CALCULATION_VERSION
            preserved["resilience"] = {
                "mode": "PRESERVED_LAST_GOOD_SAME_SESSION",
                "trigger": "RISK_FREE_RATE_TEMPORARILY_UNAVAILABLE",
                "error": str(exc)[:400],
                "source_generated_at": previous.get("generated_at"),
            }
            atomic_write_json(root / "options" / "index.json", preserved)
            print(json.dumps({
                "session_date": session,
                "status": preserved.get("status"),
                "coverage": preserved.get("coverage"),
                "resilience": preserved["resilience"],
            }, sort_keys=True))
            return 0
        return legacy.main()

    cached_good, known_no_contract = _same_session_previous_state(
        previous,
        session=session,
        targets=targets,
    )
    unresolved = [
        ticker for ticker in targets
        if ticker not in cached_good and ticker not in known_no_contract
    ]
    if cached_good or known_no_contract:
        print(json.dumps({
            "options_same_session_resume": True,
            "cached_good": len(cached_good),
            "known_no_contract": len(known_no_contract),
            "unresolved": len(unresolved),
            "targets": len(targets),
        }, sort_keys=True))

    snapshots, permanent_errors, transient_errors, global_breaks = _fetch_with_rounds(
        yf,
        targets=unresolved,
        spots=spots,
        session=session,
    )

    out = build_options_index(
        session_date=session,
        generated_at=generated_at,
        targets=targets,
        snapshots=snapshots,
        rate=rate,
        previous=previous,
    )
    reused_tickers = _merge_same_session_rows(
        out,
        previous,
        session=session,
        targets=targets,
        cached_good=cached_good,
        known_no_contract=known_no_contract,
    )

    fetch_errors = dict(permanent_errors)
    fetch_errors.update(transient_errors)
    out["calculation_version"] = CALCULATION_VERSION
    out["risk_free_rate"] = rate
    out["risk_free_rate_source"] = rate_source
    out["risk_free_rate_observed_date"] = rate_observed_date
    out["fetch_errors"] = fetch_errors
    out["chart_overlay_contract"] = {
        "requested_cli_limit": int(args.target_limit),
        "effective_target_floor": legacy.CHART_TARGET_FLOOR,
        "target_priority": "Core12, RS63 Top10, RS126 Top10, RS189 Top24, then deterministic standard targets",
        "chart_bucket_default": "0-45",
    }
    out["resilience"] = {
        "mode": "INCREMENTAL_SAME_SESSION_CACHE_AND_BACKOFF",
        "same_session_cache_hits": len(reused_tickers),
        "same_session_known_no_contract": len(known_no_contract),
        "fresh_snapshot_count": len(snapshots),
        "transient_error_count": len(transient_errors),
        "permanent_error_count": len(permanent_errors),
        "global_circuit_breaks": global_breaks,
        "retry_rounds": 1 + len(RETRY_ROUND_COOLDOWNS),
        "ticker_spacing_seconds": TICKER_SPACING_SECONDS,
        "batch_size": BATCH_SIZE,
        "batch_pause_seconds": BATCH_PAUSE_SECONDS,
        "note": "Only same-session measured option rows are reused; prior-session rows are never promoted as current data.",
    }
    out["coverage_detail"] = {
        "target_count": len(targets),
        "fresh_ticker_snapshots": len(snapshots),
        "same_session_reused_tickers": len(reused_tickers),
        "known_no_contract": len(known_no_contract),
        "published_tickers": len({
            str(row.get("ticker") or "").strip().upper()
            for row in out.get("rows", [])
            if isinstance(row, dict)
        }),
        "bucket_row_counts": {
            key: len(rows) for key, rows in (out.get("buckets") or {}).items()
            if isinstance(rows, list)
        },
    }

    path = atomic_write_json(root / "options" / "index.json", out)
    print(json.dumps({
        "path": str(path),
        "session_date": session,
        "status": out.get("status"),
        "coverage": out.get("coverage"),
        "targets": len(targets),
        "fresh_snapshots": len(snapshots),
        "reused_same_session": len(reused_tickers),
        "known_no_contract": len(known_no_contract),
        "transient_errors": len(transient_errors),
        "permanent_errors": len(permanent_errors),
        "global_circuit_breaks": global_breaks,
        "rows_0_45": len((out.get("buckets") or {}).get("0-45", [])),
        "risk_free_rate": rate,
        "risk_free_rate_source": rate_source,
        "risk_free_rate_observed_date": rate_observed_date,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
