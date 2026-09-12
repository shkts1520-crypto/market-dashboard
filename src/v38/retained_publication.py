from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .live_acquisition import LiveAcquisitionError, MIN_CURRENT_FETCH_COVERAGE, PRIMARY_MARKET_SYMBOLS


class RetainedPublicationError(LiveAcquisitionError):
    """Raised when an already-published session cannot be safely retained."""


def _load_object(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RetainedPublicationError(f"retained publication unreadable: {path}") from exc
    if not isinstance(obj, dict):
        raise RetainedPublicationError(f"retained publication is not an object: {path}")
    return obj


def _number(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise RetainedPublicationError(f"{label}: numeric value required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RetainedPublicationError(f"{label}: numeric value required") from exc
    if not math.isfinite(number):
        raise RetainedPublicationError(f"{label}: finite value required")
    return number


def _positive_int(value: Any, *, label: str) -> int:
    number = _number(value, label=label)
    integer = int(number)
    if integer <= 0 or integer != number:
        raise RetainedPublicationError(f"{label}: positive integer required")
    return integer


def _check_metadata(obj: dict[str, Any], *, name: str, session_date: str) -> None:
    if obj.get("session_date") != session_date:
        raise RetainedPublicationError(
            f"{name}: session mismatch {obj.get('session_date')} != {session_date}"
        )
    for key in ("generated_at", "source", "schema_version", "calculation_version"):
        if not isinstance(obj.get(key), str) or not str(obj[key]).strip():
            raise RetainedPublicationError(f"{name}: {key} missing")


def _coverage(value: Any, *, label: str) -> float:
    coverage = _number(value, label=label)
    if coverage < MIN_CURRENT_FETCH_COVERAGE or coverage > 1.0:
        raise RetainedPublicationError(
            f"{label}: coverage {coverage:.3f} outside retained safety range"
        )
    return coverage


def validate_retained_publication(
    data_dir: str | Path,
    *,
    session_date: str,
) -> dict[str, Any]:
    """Revalidate an already-published session without inventing fresh values.

    This path is only for provider regression: the benchmark provider has fallen
    behind a newer atomic publication already present on main. The retained
    publication must prove its stock coverage and required market-series coverage
    from the persisted authoritative shards themselves. Nothing is backfilled or
    timestamp-refreshed here.
    """
    root = Path(data_dir)
    state = _load_object(root / "state.json")
    rs = _load_object(root / "rs.json")
    breadth = _load_object(root / "breadth.json")
    manifest = _load_object(root / "acquisition_manifest.json")
    market = _load_object(root / "market_inputs.json")

    for name, obj in (
        ("state.json", state),
        ("rs.json", rs),
        ("breadth.json", breadth),
        ("acquisition_manifest.json", manifest),
        ("market_inputs.json", market),
    ):
        _check_metadata(obj, name=name, session_date=session_date)

    if state.get("status") != "READY":
        raise RetainedPublicationError("state.json: retained session is not READY")
    if manifest.get("status") != "READY":
        raise RetainedPublicationError("acquisition_manifest.json: retained session is not READY")

    state_coverage = _coverage(state.get("coverage"), label="state.coverage")
    rs_coverage = _coverage(rs.get("coverage"), label="rs.coverage")
    breadth_coverage = _coverage(breadth.get("coverage"), label="breadth.coverage")

    rs_detail = rs.get("coverage_detail")
    if not isinstance(rs_detail, dict):
        raise RetainedPublicationError("rs.coverage_detail missing")
    active = _positive_int(rs_detail.get("active_universe"), label="rs.active_universe")
    current_valid = _positive_int(
        rs_detail.get("current_valid_ohlcv"), label="rs.current_valid_ohlcv"
    )
    if current_valid > active:
        raise RetainedPublicationError("rs.current_valid_ohlcv exceeds active_universe")
    actual_coverage = current_valid / active
    if actual_coverage < MIN_CURRENT_FETCH_COVERAGE:
        raise RetainedPublicationError(
            f"rs actual coverage too low: {current_valid}/{active}={actual_coverage:.3f}"
        )

    rows = rs.get("rows")
    if not isinstance(rows, list):
        raise RetainedPublicationError("rs.rows must be a list")
    tickers = [
        row.get("ticker")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("ticker"), str) and row.get("ticker").strip()
    ]
    if len(rows) != current_valid or len(tickers) != current_valid or len(set(tickers)) != current_valid:
        raise RetainedPublicationError(
            "rs.rows count/uniqueness does not match current_valid_ohlcv"
        )

    breadth_detail = breadth.get("coverage_detail")
    if not isinstance(breadth_detail, dict):
        raise RetainedPublicationError("breadth.coverage_detail missing")
    if _positive_int(breadth_detail.get("active_universe"), label="breadth.active_universe") != active:
        raise RetainedPublicationError("breadth active_universe disagrees with rs")
    if _positive_int(
        breadth_detail.get("current_valid_ohlcv"), label="breadth.current_valid_ohlcv"
    ) != current_valid:
        raise RetainedPublicationError("breadth current_valid_ohlcv disagrees with rs")

    yahoo = manifest.get("yahoo")
    if not isinstance(yahoo, dict):
        raise RetainedPublicationError("acquisition_manifest.yahoo missing")
    requested = _positive_int(yahoo.get("requested"), label="manifest.yahoo.requested")
    received = _positive_int(
        yahoo.get("target_session_received"), label="manifest.yahoo.target_session_received"
    )
    manifest_coverage = _coverage(
        yahoo.get("target_session_coverage"), label="manifest.yahoo.target_session_coverage"
    )
    if requested != active or received != current_valid:
        raise RetainedPublicationError(
            "manifest Yahoo requested/received disagrees with rs coverage_detail"
        )

    for label, value in (
        ("state.coverage", state_coverage),
        ("rs.coverage", rs_coverage),
        ("breadth.coverage", breadth_coverage),
        ("manifest.yahoo.target_session_coverage", manifest_coverage),
    ):
        if not math.isclose(value, actual_coverage, rel_tol=0.0, abs_tol=1e-12):
            raise RetainedPublicationError(
                f"{label}: {value:.12f} disagrees with actual {actual_coverage:.12f}"
            )

    # Production market_inputs.json contract uses `symbols` and top-level
    # `coverage`. Validate those persisted fields exactly; do not invent a second
    # required_symbols/required_coverage schema just for the retained path.
    symbols = market.get("symbols")
    if (
        not isinstance(symbols, list)
        or len(symbols) != len(PRIMARY_MARKET_SYMBOLS)
        or len(set(symbols)) != len(symbols)
        or set(symbols) != set(PRIMARY_MARKET_SYMBOLS)
    ):
        raise RetainedPublicationError("market_inputs.symbols contract mismatch")
    series = market.get("series")
    if not isinstance(series, dict):
        raise RetainedPublicationError("market_inputs.series missing")

    missing_market: list[str] = []
    for symbol in PRIMARY_MARKET_SYMBOLS:
        rows_for_symbol = series.get(symbol)
        if not isinstance(rows_for_symbol, list):
            missing_market.append(symbol)
            continue
        matching = [
            row for row in rows_for_symbol
            if isinstance(row, dict) and row.get("date") == session_date
        ]
        close = matching[-1].get("close") if matching else None
        try:
            close_number = float(close)
        except (TypeError, ValueError):
            close_number = math.nan
        if not math.isfinite(close_number) or close_number <= 0:
            missing_market.append(symbol)
    if missing_market:
        raise RetainedPublicationError(
            "required market inputs missing retained session: " + ",".join(missing_market)
        )

    market_coverage = _number(market.get("coverage"), label="market_inputs.coverage")
    if not math.isclose(market_coverage, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise RetainedPublicationError(
            f"market_inputs.coverage must be 1.0, got {market_coverage:.3f}"
        )

    return {
        "session_date": session_date,
        "active_universe": active,
        "current_valid_ohlcv": current_valid,
        "stock_coverage": actual_coverage,
        "required_market_symbols": list(PRIMARY_MARKET_SYMBOLS),
        "required_market_coverage": market_coverage,
        "retained_generated_at": state.get("generated_at"),
    }
