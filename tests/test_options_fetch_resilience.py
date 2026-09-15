from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import calculate_options_resilient as resilient


def test_transient_option_error_detection_is_specific():
    assert resilient._is_transient_option_error("YFRateLimitError: Too Many Requests")
    assert resilient._is_transient_option_error("HTTP 429")
    assert resilient._is_transient_option_error("connection reset by peer")
    assert not resilient._is_transient_option_error("NO_VALID_0_45_DTE_CONTRACTS")


def test_full_universe_targets_do_not_apply_rs_or_core_filter():
    rs = {
        "rows": [
            {"ticker": "ZZZ", "price": 10.0, "rs189": 1},
            {"ticker": "AAA", "price": 20.0, "rs189": 99},
            {"ticker": "BAD", "price": None, "rs189": 100},
            {"ticker": "AAA", "price": 20.0, "rs189": 99},
        ]
    }
    assert resilient._all_universe_targets(rs) == ["AAA", "ZZZ"]


def test_same_session_cache_reuses_measured_rows_and_known_no_contract_only():
    previous = {
        "session_date": "2026-09-14",
        "rows": [{"ticker": "AAA"}, {"ticker": "BBB"}],
        "failures": {
            "CCC": "NO_VALID_0_45_DTE_CONTRACTS",
            "DDD": "OPTION_CHAIN_UNAVAILABLE",
        },
    }
    good, no_contract = resilient._same_session_previous_state(
        previous,
        session="2026-09-14",
        targets=["AAA", "BBB", "CCC", "DDD", "EEE"],
    )
    assert good == {"AAA", "BBB"}
    assert no_contract == {"CCC"}

    stale_good, stale_no_contract = resilient._same_session_previous_state(
        previous,
        session="2026-09-15",
        targets=["AAA", "BBB", "CCC"],
    )
    assert stale_good == set()
    assert stale_no_contract == set()


def test_merge_same_session_rows_preserves_real_rows_without_promoting_no_contract():
    previous = {
        "session_date": "2026-09-14",
        "generated_at": "2026-09-15T06:00:00Z",
        "buckets": {
            "0-45": [
                {"ticker": "AAA", "quality": "GOOD", "total_open_interest": 100.0},
                {"ticker": "BBB", "quality": "PARTIAL", "total_open_interest": 50.0},
            ]
        },
        "rows": [
            {"ticker": "AAA", "quality": "GOOD", "total_open_interest": 100.0},
            {"ticker": "BBB", "quality": "PARTIAL", "total_open_interest": 50.0},
        ],
        "failures": {"CCC": "NO_VALID_0_45_DTE_CONTRACTS"},
    }
    out = {
        "buckets": {"0-45": []},
        "rows": [],
        "failures": {
            "AAA": "OPTION_CHAIN_UNAVAILABLE",
            "BBB": "OPTION_CHAIN_UNAVAILABLE",
            "CCC": "OPTION_CHAIN_UNAVAILABLE",
        },
    }
    reused = resilient._merge_same_session_rows(
        out,
        previous,
        session="2026-09-14",
        targets=["AAA", "BBB", "CCC"],
        cached_good={"AAA", "BBB"},
        known_no_contract={"CCC"},
    )
    assert reused == ["AAA", "BBB"]
    assert [row["ticker"] for row in out["rows"]] == ["AAA", "BBB"]
    assert out["failures"] == {"CCC": "NO_VALID_0_45_DTE_CONTRACTS"}
    assert out["rows"][0]["resilience_provenance"]["mode"] == "PRESERVED_LAST_GOOD_SAME_SESSION_TICKER"


def test_upward_structure_uses_observed_geometry_not_direction_field():
    row = {
        "ticker": "AAA",
        "spot": 105.0,
        "gamma_flip": 100.0,
        "call_wall": 115.0,
        "put_wall": 95.0,
        "direction": None,
        "confidence": None,
        "strike_profile": [
            {"strike": 100.0, "call": 200.0, "put": -50.0, "net": 150.0},
            {"strike": 110.0, "call": 100.0, "put": -25.0, "net": 75.0},
        ],
    }
    metrics = resilient._upward_structure(row)
    assert metrics["upward_structure"] is True
    assert metrics["upward_structure_score"] == 4
    assert metrics["call_put_gex_ratio"] == 4.0
    assert row["direction"] is None
    assert row["confidence"] is None


def test_upward_rankings_are_materialized_for_each_dte_bucket():
    bullish = {
        "ticker": "AAA",
        "spot": 105.0,
        "gamma_flip": 100.0,
        "call_wall": 115.0,
        "put_wall": 95.0,
        "net_gex": 100.0,
        "total_open_interest": 1000.0,
        "quality": "GOOD",
        "strike_profile": [{"strike": 100.0, "call": 200.0, "put": -50.0, "net": 150.0}],
    }
    bearish = {
        "ticker": "BBB",
        "spot": 95.0,
        "gamma_flip": 100.0,
        "call_wall": 90.0,
        "put_wall": 100.0,
        "net_gex": -100.0,
        "total_open_interest": 1000.0,
        "quality": "GOOD",
        "strike_profile": [{"strike": 100.0, "call": 20.0, "put": -200.0, "net": -180.0}],
    }
    out = {"buckets": {key: [dict(bullish), dict(bearish)] for key in ("0-6", "7-21", "22-45", "0-45")}}
    resilient._materialize_upward_rankings(out)
    assert set(out["upward_rankings"]) == {"0-6", "7-21", "22-45", "0-45"}
    for rows in out["upward_rankings"].values():
        assert [row["ticker"] for row in rows] == ["AAA"]
        assert rows[0]["upward_rank"] == 1


def test_zero_put_gex_ratio_edge_is_explicitly_undefined_at_wrapper_boundary():
    # The resilient producer can identify Call dominance while the public live
    # entrypoint normalizes non-finite ratios to null before atomic JSON output.
    row = {
        "ticker": "AAA",
        "spot": 105.0,
        "gamma_flip": 100.0,
        "call_wall": 115.0,
        "put_wall": 95.0,
        "strike_profile": [{"strike": 100.0, "call": 200.0, "put": 0.0, "net": 200.0}],
    }
    metrics = resilient._upward_structure(row)
    assert metrics["call_gex_total"] == 200.0
    assert metrics["put_gex_abs_total"] == 0.0


def test_global_transient_circuit_breaker_avoids_hammering(monkeypatch):
    calls: list[str] = []

    def always_rate_limited(yf, ticker, *, spot, session_date):
        calls.append(ticker)
        raise RuntimeError("HTTP 429 Too Many Requests")

    monkeypatch.setattr(resilient, "_fetch_ticker_snapshot_once", always_rate_limited)
    monkeypatch.setattr(resilient.time, "sleep", lambda _seconds: None)

    targets = ["A", "B", "C", "D", "E", "F"]
    snapshots, permanent, transient, global_breaks = resilient._fetch_with_rounds(
        object(),
        targets=targets,
        spots={ticker: 100.0 for ticker in targets},
        session="2026-09-14",
    )

    assert snapshots == {}
    assert permanent == {}
    assert set(transient) == set(targets)
    assert global_breaks == 3
    assert len(calls) == resilient.GLOBAL_TRANSIENT_FAILURE_STREAK * 3
