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
