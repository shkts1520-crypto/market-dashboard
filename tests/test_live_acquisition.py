from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from v38.live_acquisition import (
    CLASS_PAIRS,
    SESSION_CUTOFF_ET,
    LiveAcquisitionError,
    adjusted_ohlcv_rows,
    build_tradingview_payload,
    choose_completed_session,
    manifest_object,
    market_rows,
    parse_tradingview_universe,
    select_yfinance_symbol_frame,
    state_object,
    validate_universe_count,
    yahoo_symbol,
)


def _tv_item(
    symbol: str,
    *,
    close: float = 10.0,
    mcap: float = 1_000_000_000.0,
    description: str = "Example Corp",
    sector: str = "Health Technology",
    industry: str = "Biotechnology",
    exchange: str | None = None,
):
    ex = exchange or symbol.split(":", 1)[0]
    ticker = symbol.split(":", 1)[1]
    return {
        "s": symbol,
        "d": [
            ticker,
            description,
            close,
            mcap,
            sector,
            industry,
            "stock",
            "common",
            ex,
        ],
    }


def _frame(rows):
    return pd.DataFrame(rows).set_index("Date")


def test_tradingview_payload_pins_exchanges_and_floors():
    payload = build_tradingview_payload()
    assert payload["range"] == [0, 10000]
    filters = {row["left"]: row for row in payload["filter"]}
    assert filters["exchange"]["right"] == ["NYSE", "NASDAQ", "AMEX"]
    assert filters["market_cap_basic"]["right"] == 200_000_000.0
    assert filters["close"]["right"] == 1.0


def test_parse_tradingview_basic_snapshot():
    rows, stats = parse_tradingview_universe(
        {"totalCount": 1, "data": [_tv_item("NASDAQ:NVDA")]},
        session_date="2026-09-10",
    )
    assert rows[0]["ticker"] == "NVDA"
    assert rows[0]["session_date"] == "2026-09-10"
    assert rows[0]["in_universe"] is True
    assert stats["active_universe"] == 1
    assert stats["biotech_heuristic_applied"] is False


def test_parse_reapplies_price_and_market_cap_floor_locally():
    response = {
        "data": [
            _tv_item("NYSE:AAA", close=0.99),
            _tv_item("NYSE:BBB", mcap=199_999_999),
            _tv_item("NYSE:CCC", close=2.0, mcap=300_000_000),
        ]
    }
    rows, stats = parse_tradingview_universe(response, session_date="2026-09-10")
    assert [row["ticker"] for row in rows] == ["CCC"]
    assert stats["below_floor_rows"] == 2


def test_parse_excludes_slash_space_and_special_security_description():
    response = {
        "data": [
            _tv_item("NYSE:ABC/PA"),
            _tv_item("NYSE:ABC X"),
            _tv_item("NYSE:WARR", description="Example Warrant"),
            _tv_item("NYSE:GOOD", description="Example Corporation"),
        ]
    }
    rows, stats = parse_tradingview_universe(response, session_date="2026-09-10")
    assert [row["ticker"] for row in rows] == ["GOOD"]
    assert stats["special_security_rows"] == 3


def test_parse_applies_only_explicit_historical_duplicate_class_pairs():
    items = []
    for keep, drop in CLASS_PAIRS:
        items.append(_tv_item(f"NASDAQ:{keep}", mcap=2_000_000_000))
        items.append(_tv_item(f"NASDAQ:{drop}", mcap=2_000_000_000))
    rows, stats = parse_tradingview_universe({"data": items}, session_date="2026-09-10")
    names = {row["ticker"] for row in rows}
    for keep, drop in CLASS_PAIRS:
        assert keep in names
        assert drop not in names
    assert stats["duplicate_class_rows"] == len(CLASS_PAIRS)


def test_small_healthcare_biotech_is_not_heuristically_removed():
    rows, stats = parse_tradingview_universe(
        {
            "data": [
                _tv_item(
                    "NASDAQ:BIOX",
                    mcap=500_000_000,
                    sector="Health Technology",
                    industry="Biotechnology",
                )
            ]
        },
        session_date="2026-09-10",
    )
    assert [row["ticker"] for row in rows] == ["BIOX"]
    assert stats["biotech_heuristic_applied"] is False


def test_universe_count_guard_allows_first_run_and_exact_80pct_floor():
    validate_universe_count(1, None)
    validate_universe_count(80, 100)


def test_universe_count_guard_rejects_below_80pct():
    with pytest.raises(LiveAcquisitionError, match="count guard failed"):
        validate_universe_count(79, 100)


def test_yahoo_symbol_maps_dot_class_only():
    assert yahoo_symbol("brk.b") == "BRK-B"
    assert yahoo_symbol("NVDA") == "NVDA"


def test_completed_session_cutoff_is_1615_et():
    assert SESSION_CUTOFF_ET.hour == 16
    assert SESSION_CUTOFF_ET.minute == 15


def test_completed_session_after_close_can_use_current_session():
    got = choose_completed_session(
        ["2026-09-09", "2026-09-10"],
        ["2026-09-09", "2026-09-10"],
        now_utc=datetime(2026, 9, 10, 21, 0, tzinfo=timezone.utc),
    )
    assert got == "2026-09-10"


def test_completed_session_at_1614_et_falls_back_to_prior():
    got = choose_completed_session(
        ["2026-09-09", "2026-09-10"],
        ["2026-09-09", "2026-09-10"],
        now_utc=datetime(2026, 9, 10, 20, 14, tzinfo=timezone.utc),
    )
    assert got == "2026-09-09"


def test_completed_session_at_1615_et_accepts_current():
    got = choose_completed_session(
        ["2026-09-09", "2026-09-10"],
        ["2026-09-09", "2026-09-10"],
        now_utc=datetime(2026, 9, 10, 20, 15, tzinfo=timezone.utc),
    )
    assert got == "2026-09-10"


def test_completed_session_before_close_falls_back_to_prior():
    got = choose_completed_session(
        ["2026-09-09", "2026-09-10"],
        ["2026-09-09", "2026-09-10"],
        now_utc=datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc),
    )
    assert got == "2026-09-09"


def test_completed_session_requires_common_qqq_spy_date():
    got = choose_completed_session(
        ["2026-09-09", "2026-09-10"],
        ["2026-09-08", "2026-09-09"],
        now_utc=datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc),
    )
    assert got == "2026-09-09"


def test_adjusted_ohlcv_uses_adj_close_factor_for_ohlc_not_volume():
    frame = _frame(
        [
            {
                "Date": "2026-09-10",
                "Open": 100.0,
                "High": 110.0,
                "Low": 90.0,
                "Close": 100.0,
                "Adj Close": 50.0,
                "Volume": 1234.0,
            }
        ]
    )
    row = adjusted_ohlcv_rows(frame, ticker="X", target_session="2026-09-10")[0]
    assert row["open"] == 50.0
    assert row["high"] == 55.0
    assert row["low"] == 45.0
    assert row["close"] == 50.0
    assert row["volume"] == 1234.0
    assert row["split_checked"] is True


def test_missing_adj_close_does_not_claim_split_checked_or_prices():
    frame = _frame(
        [
            {
                "Date": "2026-09-10",
                "Open": 100.0,
                "High": 110.0,
                "Low": 90.0,
                "Close": 100.0,
                "Volume": 1234.0,
            }
        ]
    )
    row = adjusted_ohlcv_rows(frame, ticker="X", target_session="2026-09-10")[0]
    assert row["split_checked"] is False
    assert row["close"] is None
    assert row["high"] is None


def test_yfinance_multiindex_selects_symbol_level():
    idx = pd.to_datetime(["2026-09-10"])
    cols = pd.MultiIndex.from_tuples(
        [("NVDA", "Close"), ("NVDA", "Adj Close"), ("AAPL", "Close")]
    )
    raw = pd.DataFrame([[100.0, 99.0, 200.0]], index=idx, columns=cols)
    out = select_yfinance_symbol_frame(raw, "NVDA")
    assert list(out.columns) == ["close", "adj_close"]
    assert float(out.iloc[0]["close"]) == 100.0


def test_market_rows_drops_future_and_caps_history():
    idx = pd.date_range("2025-01-01", periods=300, freq="D")
    frame = pd.DataFrame(
        {
            "Open": range(1, 301),
            "High": range(2, 302),
            "Low": range(0, 300),
            "Close": range(1, 301),
            "Adj Close": range(1, 301),
            "Volume": [1000] * 300,
        },
        index=idx,
    )
    target = idx[-2].strftime("%Y-%m-%d")
    rows = market_rows(frame, target_session=target, max_rows=260)
    assert len(rows) == 260
    assert rows[-1]["date"] == target


def test_state_and_manifest_keep_unresolved_authorities_fail_closed():
    state = state_object(
        session_date="2026-09-10",
        generated_at="2026-09-11T00:00:00Z",
        coverage=0.99,
    )
    assert state["status"] == "READY"
    assert state["session_date"] == "2026-09-10"
    assert state["session_contract"]["cutoff_et"] == "16:15"
    assert state["session_contract"]["timezone"] == "America/New_York"

    manifest = manifest_object(
        session_date="2026-09-10",
        generated_at="2026-09-11T00:00:00Z",
        universe_stats={"active_universe": 3500},
        yahoo_stats={"target_session_coverage": 0.99},
        nqsar_status="DATA_REQUIRED",
    )
    assert manifest["session_contract"]["cutoff_et"] == "16:15"
    assert manifest["mc57_status"] == "DATA_REQUIRED"
    assert manifest["structural_clinical_biotech_status"] == "DATA_REQUIRED"
    assert manifest["peer_theme_status"] == "DATA_REQUIRED"
    assert manifest["options_status"] == "DATA_REQUIRED"
    assert manifest["positions_status"] == "DATA_REQUIRED"
