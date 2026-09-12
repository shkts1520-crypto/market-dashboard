from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any, Iterable

import numpy as np
import pandas as pd

CALCULATION_VERSION = "v38-options-live-1.0.0"
SCHEMA_VERSION = "v38.options.1"

DTE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("0-6", 0, 6),
    ("7-21", 7, 21),
    ("22-45", 22, 45),
    ("0-45", 0, 45),
)

# The exact legacy target-selection producer was not recovered. The old dashboard
# did persist a separate options_targets.json and consumed a separate upstream
# options workflow. Until that producer is recovered, live scanning is restricted
# to current Core12/RS leaders/liquid names and is labelled as a recovered target
# policy rather than the original all-ticker ranking universe.
DEFAULT_TARGET_LIMIT = 24


class OptionsEngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class Contract:
    ticker: str
    expiry: str
    dte: int
    side: str
    strike: float
    open_interest: float
    implied_volatility: float
    bid: float | None
    ask: float | None
    time_years: float


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _mid(bid: Any, ask: Any) -> float | None:
    b = _finite(bid)
    a = _finite(ask)
    if b is None or a is None or b < 0 or a <= 0 or a < b:
        return None
    return (a + b) / 2.0


def bs_gamma(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    implied_volatility: float,
    dividend_yield: float = 0.0,
) -> float | None:
    """Black-Scholes gamma used only to reconstruct option positioning GEX.

    The recovered V38 contract-GEX formula is Gamma*OI*100*Spot^2*0.01.
    The legacy dividend/rate provider was not recovered; live production uses an
    observed short Treasury rate and q=0, recorded in the output contract.
    """
    values = [spot, strike, time_years, implied_volatility]
    if any((not math.isfinite(float(x)) for x in values)):
        return None
    if spot <= 0 or strike <= 0 or time_years <= 0 or implied_volatility <= 0:
        return None
    sqrt_t = math.sqrt(time_years)
    denom = implied_volatility * sqrt_t
    if denom <= 0:
        return None
    d1 = (
        math.log(spot / strike)
        + (rate - dividend_yield + 0.5 * implied_volatility * implied_volatility) * time_years
    ) / denom
    pdf = math.exp(-0.5 * d1 * d1) / math.sqrt(2.0 * math.pi)
    gamma = math.exp(-dividend_yield * time_years) * pdf / (spot * denom)
    return gamma if math.isfinite(gamma) and gamma >= 0 else None


def contract_gex(contract: Contract, *, spot: float, rate: float) -> float | None:
    gamma = bs_gamma(
        spot,
        contract.strike,
        contract.time_years,
        rate,
        contract.implied_volatility,
    )
    if gamma is None:
        return None
    base = gamma * contract.open_interest * 100.0 * spot * spot * 0.01
    return base if contract.side == "call" else -base


def _session_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise OptionsEngineError(f"invalid session date: {value}") from exc


def expiry_dte(expiry: str, session_date: str) -> int:
    try:
        exp = date.fromisoformat(expiry)
    except ValueError as exc:
        raise OptionsEngineError(f"invalid option expiry: {expiry}") from exc
    return (exp - _session_date(session_date)).days


def frame_to_contracts(
    *,
    ticker: str,
    frame: pd.DataFrame,
    side: str,
    expiry: str,
    session_date: str,
) -> list[Contract]:
    if side not in {"call", "put"}:
        raise OptionsEngineError("side must be call or put")
    dte = expiry_dte(expiry, session_date)
    if dte < 0 or dte > 45 or frame is None or frame.empty:
        return []
    # EOD snapshot: use at least one calendar day to avoid a singular gamma on
    # zero-DTE rows. DTE itself remains calendar-day DTE in the published schema.
    time_years = max(float(dte + 1) / 365.0, 1.0 / 365.0)
    out: list[Contract] = []
    for _, raw in frame.iterrows():
        strike = _finite(raw.get("strike"))
        oi = _finite(raw.get("openInterest"))
        iv = _finite(raw.get("impliedVolatility"))
        if strike is None or strike <= 0 or oi is None or oi <= 0 or iv is None or iv <= 0:
            continue
        out.append(
            Contract(
                ticker=ticker,
                expiry=expiry,
                dte=dte,
                side=side,
                strike=strike,
                open_interest=oi,
                implied_volatility=iv,
                bid=_finite(raw.get("bid")),
                ask=_finite(raw.get("ask")),
                time_years=time_years,
            )
        )
    return out


def _strike_profile(
    contracts: Iterable[Contract], *, spot: float, rate: float
) -> list[dict[str, float]]:
    by_strike: dict[float, dict[str, float]] = {}
    for contract in contracts:
        gex = contract_gex(contract, spot=spot, rate=rate)
        if gex is None:
            continue
        row = by_strike.setdefault(contract.strike, {"call": 0.0, "put": 0.0, "net": 0.0})
        row[contract.side] += gex
        row["net"] += gex
    return [
        {"strike": strike, **by_strike[strike]}
        for strike in sorted(by_strike)
    ]


def gamma_flip(
    contracts: Iterable[Contract], *, spot: float, rate: float, points: int = 121
) -> tuple[float | None, list[dict[str, float]]]:
    contracts = list(contracts)
    if not contracts or spot <= 0:
        return None, []
    strikes = [c.strike for c in contracts if c.strike > 0]
    if not strikes:
        return None, []
    lower = max(0.01, min(spot * 0.70, min(strikes) * 0.95))
    upper = max(spot * 1.30, max(strikes) * 1.05)
    if upper <= lower:
        return None, []
    grid = np.linspace(lower, upper, max(21, int(points)))
    profile: list[dict[str, float]] = []
    for grid_spot in grid:
        total = 0.0
        observed = 0
        for contract in contracts:
            gex = contract_gex(contract, spot=float(grid_spot), rate=rate)
            if gex is not None:
                total += gex
                observed += 1
        if observed:
            profile.append({"spot": float(grid_spot), "gex": float(total)})
    crossings: list[float] = []
    for left, right in zip(profile, profile[1:]):
        x0, y0 = left["spot"], left["gex"]
        x1, y1 = right["spot"], right["gex"]
        if y0 == 0:
            crossings.append(x0)
            continue
        if y0 * y1 < 0 and y1 != y0:
            crossings.append(x0 + (0.0 - y0) * (x1 - x0) / (y1 - y0))
    flip = min(crossings, key=lambda x: abs(x - spot)) if crossings else None
    return (float(flip) if flip is not None else None), profile


def expected_move(
    contracts: Iterable[Contract], *, spot: float
) -> tuple[float | None, str | None, float | None]:
    """Nearest-expiry ATM call-mid + put-mid, never a VIX substitute."""
    calls: dict[tuple[str, float], Contract] = {}
    puts: dict[tuple[str, float], Contract] = {}
    for contract in contracts:
        key = (contract.expiry, contract.strike)
        (calls if contract.side == "call" else puts)[key] = contract
    candidates: list[tuple[int, float, str, float]] = []
    for key, call in calls.items():
        put = puts.get(key)
        if put is None:
            continue
        c_mid = _mid(call.bid, call.ask)
        p_mid = _mid(put.bid, put.ask)
        if c_mid is None or p_mid is None:
            continue
        move = c_mid + p_mid
        if move <= 0:
            continue
        candidates.append((call.dte, abs(call.strike - spot), call.expiry, move))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda item: (item[0], item[1]))
    dte, _, expiry, move = candidates[0]
    return float(move), expiry, float(move / spot) if spot > 0 else None


def aggregate_bucket(
    *,
    ticker: str,
    contracts: Iterable[Contract],
    spot: float,
    rate: float,
    bucket: str,
) -> dict[str, Any] | None:
    contracts = list(contracts)
    if not contracts:
        return None
    profile = _strike_profile(contracts, spot=spot, rate=rate)
    if not profile:
        return None
    call_rows = [row for row in profile if row["call"] > 0]
    put_rows = [row for row in profile if row["put"] < 0]
    call_wall = max(call_rows, key=lambda row: row["call"])["strike"] if call_rows else None
    put_wall = min(put_rows, key=lambda row: row["put"])["strike"] if put_rows else None
    net_gex = float(sum(row["net"] for row in profile))
    flip, grid = gamma_flip(contracts, spot=spot, rate=rate)
    em, em_expiry, em_pct = expected_move(contracts, spot=spot)
    total_abs = float(sum(abs(row["net"]) for row in profile))
    max_abs = max((abs(row["net"]) for row in profile), default=0.0)
    concentration = max_abs / total_abs if total_abs > 0 else None
    expiries = sorted({c.expiry for c in contracts})
    quote_valid = sum(1 for c in contracts if _mid(c.bid, c.ask) is not None)
    quote_coverage = quote_valid / len(contracts) if contracts else 0.0
    quality = "GOOD" if len(contracts) >= 30 and len(expiries) >= 1 and quote_coverage >= 0.30 else "PARTIAL"
    return {
        "ticker": ticker,
        "bucket": bucket,
        "spot": float(spot),
        "call_wall": float(call_wall) if call_wall is not None else None,
        "put_wall": float(put_wall) if put_wall is not None else None,
        "gamma_flip": flip,
        "net_gex": net_gex,
        "expected_move": em,
        "expected_move_pct": em_pct,
        "expected_move_expiry": em_expiry,
        "spot_vs_flip": (
            "ABOVE_FLIP" if flip is not None and spot > flip
            else "BELOW_FLIP" if flip is not None and spot < flip
            else None
        ),
        "net_gex_sign": "POSITIVE" if net_gex > 0 else "NEGATIVE" if net_gex < 0 else "FLAT",
        "call_wall_distance_pct": (call_wall / spot - 1.0) if call_wall is not None else None,
        "put_wall_distance_pct": (put_wall / spot - 1.0) if put_wall is not None else None,
        "concentration": concentration,
        "direction": None,
        "confidence": None,
        "quality": quality,
        "valid_contracts": len(contracts),
        "quote_mid_coverage": quote_coverage,
        "expiration_count": len(expiries),
        "expiries": expiries,
        "total_open_interest": float(sum(c.open_interest for c in contracts)),
        "strike_profile": profile,
        "gamma_profile": grid,
        "note": "Direction/Confidence legacy producer not recovered; raw positioning components are shown without a fabricated directional score.",
    }


def bucket_contracts(contracts: Iterable[Contract]) -> dict[str, list[Contract]]:
    rows = list(contracts)
    return {
        label: [c for c in rows if low <= c.dte <= high]
        for label, low, high in DTE_BUCKETS
    }


def select_targets(
    rs: dict[str, Any],
    core12: dict[str, Any] | None,
    *,
    limit: int = DEFAULT_TARGET_LIMIT,
) -> list[str]:
    """Recovered interim target policy, explicitly not the missing legacy producer."""
    if limit <= 0:
        return []
    rows = rs.get("rows") if isinstance(rs, dict) else None
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    out: list[str] = []

    def add(ticker: Any) -> None:
        text = str(ticker or "").strip().upper()
        if text and text not in out:
            out.append(text)

    ranking = core12.get("ranking") if isinstance(core12, dict) else None
    if isinstance(ranking, list):
        for row in ranking:
            if isinstance(row, dict):
                add(row.get("ticker"))

    by_rs = sorted(
        rows,
        key=lambda row: (-(_finite(row.get("rs189")) or -1e100), str(row.get("ticker") or "")),
    )
    for row in by_rs[: max(12, limit)]:
        add(row.get("ticker"))

    by_liquidity = sorted(
        rows,
        key=lambda row: (-(_finite(row.get("ddv20")) or -1e100), str(row.get("ticker") or "")),
    )
    for row in by_liquidity[: max(12, limit)]:
        add(row.get("ticker"))

    return out[:limit]


def build_options_index(
    *,
    session_date: str,
    generated_at: str,
    targets: list[str],
    snapshots: dict[str, dict[str, Any]],
    rate: float,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bucket_rows: dict[str, list[dict[str, Any]]] = {label: [] for label, _, _ in DTE_BUCKETS}
    failures: dict[str, str] = {}
    for ticker in targets:
        snap = snapshots.get(ticker)
        if not isinstance(snap, dict):
            failures[ticker] = "OPTION_CHAIN_UNAVAILABLE"
            continue
        spot = _finite(snap.get("spot"))
        contracts = snap.get("contracts")
        if spot is None or not isinstance(contracts, list):
            failures[ticker] = "OPTION_CHAIN_INVALID"
            continue
        typed = [c for c in contracts if isinstance(c, Contract)]
        buckets = bucket_contracts(typed)
        valid_any = False
        for label, _, _ in DTE_BUCKETS:
            row = aggregate_bucket(
                ticker=ticker,
                contracts=buckets[label],
                spot=spot,
                rate=rate,
                bucket=label,
            )
            if row is not None:
                valid_any = True
                bucket_rows[label].append(row)
        if not valid_any:
            failures[ticker] = "NO_VALID_0_45_DTE_CONTRACTS"

    quality_order = {"GOOD": 0, "PARTIAL": 1}
    for label in bucket_rows:
        bucket_rows[label].sort(
            key=lambda row: (
                quality_order.get(str(row.get("quality")), 9),
                -float(row.get("total_open_interest") or 0.0),
                str(row.get("ticker") or ""),
            )
        )
        for rank, row in enumerate(bucket_rows[label], start=1):
            row["data_rank"] = rank

    successes = len(targets) - len(failures)
    coverage = successes / len(targets) if targets else 0.0
    previous_history = previous.get("history") if isinstance(previous, dict) else None
    history: dict[str, list[dict[str, Any]]] = {}
    if isinstance(previous_history, dict):
        for ticker, rows in previous_history.items():
            if isinstance(rows, list):
                history[str(ticker)] = [dict(x) for x in rows if isinstance(x, dict)][-59:]
    for row in bucket_rows["0-45"]:
        ticker = str(row["ticker"])
        entry = {
            "date": session_date,
            "spot": row.get("spot"),
            "call_wall": row.get("call_wall"),
            "put_wall": row.get("put_wall"),
            "gamma_flip": row.get("gamma_flip"),
            "net_gex": row.get("net_gex"),
            "expected_move": row.get("expected_move"),
        }
        prior = [x for x in history.get(ticker, []) if x.get("date") != session_date]
        history[ticker] = (prior + [entry])[-60:]

    status = "READY" if successes > 0 else "DATA_REQUIRED"
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": coverage,
        "source": "Yahoo Finance option chains via yfinance 0.2.66; recovered V38 GEX/Wall/Flip/Expected-Move contract",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": status,
        "reason": None if status == "READY" else "NO_VALID_OPTION_CHAINS",
        "target_policy": {
            "status": "RECOVERED_INTERIM_NOT_LEGACY_EXACT",
            "method": "Core12 first, then RS189 leaders, then highest DDV20; deterministic cap",
            "limit": len(targets),
            "targets": targets,
            "note": "Legacy options_targets producer was not recovered; this target policy is explicitly separated from the final ranking rules.",
        },
        "model_contract": {
            "dte": "calendar days",
            "buckets": [label for label, _, _ in DTE_BUCKETS],
            "contract_gex": "Gamma*OI*100*Spot^2*0.01; calls positive, puts negative",
            "gamma": "Black-Scholes gamma from chain impliedVolatility, observed short Treasury rate, q=0",
            "call_wall": "strike with maximum aggregated positive Call GEX",
            "put_wall": "strike with minimum signed Put GEX",
            "net_gex": "sum signed contract GEX",
            "gamma_flip": "aggregate GEX zero crossing on spot grid; linear interpolation; nearest valid crossing to spot",
            "expected_move": "nearest-expiry ATM-near call mid + put mid; never VIX-derived",
            "direction": "UNRECOVERED_LEGACY_UPSTREAM_MODEL_NOT_FABRICATED",
            "confidence": "UNRECOVERED_LEGACY_UPSTREAM_MODEL_NOT_FABRICATED",
        },
        "risk_free_rate": rate,
        "rate_source": "Yahoo ^IRX latest completed close / 100",
        "buckets": bucket_rows,
        "rows": bucket_rows["0-45"],
        "failures": failures,
        "history": history,
        "ordering": "Data quality then total OI; not a directional ranking because legacy Direction/Confidence producer is unrecovered.",
    }
