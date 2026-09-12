from __future__ import annotations

import math

import pandas as pd

from v38.options_engine import (
    Contract,
    aggregate_bucket,
    bs_gamma,
    build_options_index,
    expected_move,
    frame_to_contracts,
    select_targets,
)


def contract(side, strike, oi=1000, iv=0.40, bid=2.0, ask=2.4, dte=10, ticker="TEST"):
    return Contract(
        ticker=ticker,
        expiry="2026-09-21",
        dte=dte,
        side=side,
        strike=float(strike),
        open_interest=float(oi),
        implied_volatility=float(iv),
        bid=float(bid) if bid is not None else None,
        ask=float(ask) if ask is not None else None,
        time_years=float(dte + 1) / 365.0,
    )


def test_bs_gamma_is_positive_and_finite():
    gamma = bs_gamma(100.0, 100.0, 30 / 365.0, 0.04, 0.30)
    assert gamma is not None
    assert math.isfinite(gamma)
    assert gamma > 0


def test_frame_to_contracts_uses_calendar_dte_and_requires_oi_iv():
    frame = pd.DataFrame([
        {"strike": 100, "openInterest": 200, "impliedVolatility": 0.25, "bid": 2.0, "ask": 2.4},
        {"strike": 105, "openInterest": 0, "impliedVolatility": 0.30, "bid": 1.0, "ask": 1.2},
        {"strike": 110, "openInterest": 50, "impliedVolatility": 8.0, "bid": 0.1, "ask": 0.2},
    ])
    rows = frame_to_contracts(
        ticker="TEST",
        frame=frame,
        side="call",
        expiry="2026-09-18",
        session_date="2026-09-11",
    )
    assert len(rows) == 1
    assert rows[0].dte == 7
    assert rows[0].strike == 100


def test_expected_move_is_atm_call_mid_plus_put_mid():
    rows = [
        contract("call", 100, bid=3.0, ask=3.4),
        contract("put", 100, bid=2.0, ask=2.4),
        contract("call", 105, bid=1.0, ask=1.4),
        contract("put", 105, bid=5.0, ask=5.4),
    ]
    move, expiry, pct = expected_move(rows, spot=101.0)
    assert expiry == "2026-09-21"
    assert move == 5.4
    assert pct is not None and abs(pct - 5.4 / 101.0) < 1e-12


def test_aggregate_bucket_has_signed_walls_and_no_fabricated_direction():
    rows = [
        contract("call", 95, oi=100, iv=0.35),
        contract("call", 100, oi=5000, iv=0.35),
        contract("call", 105, oi=200, iv=0.35),
        contract("put", 90, oi=100, iv=0.35),
        contract("put", 95, oi=6000, iv=0.35),
        contract("put", 100, oi=200, iv=0.35),
    ]
    out = aggregate_bucket(ticker="TEST", contracts=rows, spot=100.0, rate=0.04, bucket="7-21")
    assert out is not None
    assert out["call_wall"] == 100.0
    assert out["put_wall"] == 95.0
    assert out["direction"] is None
    assert out["confidence"] is None
    assert out["quality"] in {"GOOD", "PARTIAL"}
    assert out["valid_contracts"] == len(rows)


def test_build_options_index_preserves_null_flip_not_zero_and_requires_minimum_coverage():
    rows = [
        contract("call", 100, oi=1000, iv=0.30),
        contract("call", 105, oi=800, iv=0.30),
    ]
    obj = build_options_index(
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
        targets=["TEST"],
        snapshots={"TEST": {"spot": 100.0, "contracts": rows}},
        rate=0.04,
    )
    assert obj["status"] == "DATA_REQUIRED"
    row = obj["buckets"]["0-45"][0]
    assert row["gamma_flip"] is None
    assert row["gamma_flip"] != 0.0


def test_build_options_index_ready_with_three_successful_tickers():
    snapshots = {}
    targets = ["AAA", "BBB", "CCC", "DDD"]
    for ticker in targets[:3]:
        rows = [
            contract("call", 100, oi=1000, iv=0.30, ticker=ticker),
            contract("put", 100, oi=900, iv=0.30, ticker=ticker),
            contract("call", 105, oi=700, iv=0.32, ticker=ticker),
            contract("put", 95, oi=650, iv=0.31, ticker=ticker),
        ]
        snapshots[ticker] = {"spot": 100.0, "contracts": rows}
    obj = build_options_index(
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
        targets=targets,
        snapshots=snapshots,
        rate=0.04,
    )
    assert obj["status"] == "READY"
    assert obj["coverage"] == 0.75
    assert len(obj["buckets"]["0-45"]) == 3


def test_select_targets_is_deterministic_core_then_rs_then_liquidity():
    rs = {"rows": [
        {"ticker": "AAA", "rs189": 90, "ddv20": 10},
        {"ticker": "BBB", "rs189": 99, "ddv20": 20},
        {"ticker": "CCC", "rs189": 80, "ddv20": 1000},
    ]}
    core = {"ranking": [{"ticker": "AAA"}]}
    assert select_targets(rs, core, limit=3) == ["AAA", "BBB", "CCC"]
