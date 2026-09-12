from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from v38.stock_adapter import StockAdapterError, calculate_from_files, calculate_stock_outputs, resolve_active_universe

SESSION = "2026-09-08"
GENERATED = "2026-09-09T05:00:00+09:00"


def make_prices(tickers=("AAA", "BBB", "CCC", "DDD"), periods=260, slopes=None):
    dates = pd.bdate_range(end=SESSION, periods=periods)
    slopes = slopes or {t: i + 1 for i, t in enumerate(tickers)}
    rows = []
    for i, t in enumerate(tickers):
        slope = slopes[t]
        base = 30 + i * 5
        for j, dt in enumerate(dates):
            close = base + slope * j * 0.10
            rows.append(
                {
                    "ticker": t,
                    "date": dt.strftime("%Y-%m-%d"),
                    "open": close * 0.995,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": 2_000_000,
                    "is_complete": True,
                    "split_checked": True,
                    "split_anomaly": False,
                }
            )
    return pd.DataFrame(rows)


def snap_universe(tickers=("AAA", "BBB", "CCC", "DDD"), date=SESSION):
    return pd.DataFrame({"ticker": list(tickers), "session_date": date, "in_universe": True})


def calc(ohlcv=None, universe=None):
    return calculate_stock_outputs(
        ohlcv if ohlcv is not None else make_prices(),
        universe if universe is not None else snap_universe(),
        session_date=SESSION,
        generated_at=GENERATED,
        source="fixture",
    )


def test_static_ticker_list_is_rejected_as_not_pit():
    with pytest.raises(StockAdapterError, match="not PIT"):
        resolve_active_universe(pd.DataFrame({"ticker": ["AAA"]}), SESSION)


def test_snapshot_requires_exact_session_no_previous_snapshot_backfill():
    with pytest.raises(StockAdapterError, match="exact PIT snapshot"):
        resolve_active_universe(snap_universe(date="2026-09-07"), SESSION)


def test_interval_universe_is_point_in_time_and_effective_to_inclusive():
    u = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC"],
            "effective_from": ["2026-01-01", "2026-09-09", "2026-01-01"],
            "effective_to": [None, None, "2026-09-08"],
        }
    )
    assert resolve_active_universe(u, SESSION) == ["AAA", "CCC"]


def test_event_log_uses_latest_membership_event_only_up_to_target():
    u = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA", "BBB", "BBB"],
            "effective_from": ["2026-01-01", "2026-09-01", "2026-01-01", "2026-09-09"],
            "in_universe": [True, False, True, False],
        }
    )
    assert resolve_active_universe(u, SESSION) == ["BBB"]


def test_completed_bar_flag_is_mandatory():
    d = make_prices().drop(columns=["is_complete"])
    with pytest.raises(StockAdapterError, match="is_complete"):
        calc(d)


def test_split_checked_flag_is_mandatory():
    d = make_prices().drop(columns=["split_checked"])
    with pytest.raises(StockAdapterError, match="split_checked"):
        calc(d)


def test_forming_target_bar_is_not_used_and_ticker_is_excluded():
    d = make_prices()
    mask = (d.ticker == "AAA") & (d.date == SESSION)
    d.loc[mask, "is_complete"] = False
    rs, breadth = calc(d)
    ex = {x["ticker"]: x["reasons"] for x in rs["excluded"]}
    assert "NO_COMPLETED_SESSION_BAR" in ex["AAA"]
    assert all(row["ticker"] != "AAA" for row in rs["rows"])
    assert breadth["coverage_detail"]["current_valid_ohlcv"] == 3


def test_unknown_split_status_never_enters_normal_metrics():
    d = make_prices()
    idx = d[(d.ticker == "BBB") & (d.date == SESSION)].index[0]
    d.loc[idx, "split_checked"] = False
    rs, _ = calc(d)
    ex = {x["ticker"]: x["reasons"] for x in rs["excluded"]}
    assert "SPLIT_STATUS_UNKNOWN" in ex["BBB"]
    assert all(row["ticker"] != "BBB" for row in rs["rows"])


def test_abnormal_ohlcv_high_below_low_is_excluded_not_silently_dropped():
    d = make_prices()
    idx = d[(d.ticker == "CCC") & (d.date == SESSION)].index[0]
    d.loc[idx, "high"] = d.loc[idx, "low"] - 1
    rs, _ = calc(d)
    ex = {x["ticker"]: x["reasons"] for x in rs["excluded"]}
    assert "HIGH_BELOW_LOW" in ex["CCC"]


def test_return_formula_is_close_t_over_close_t_minus_p_minus_one():
    d = make_prices(tickers=("AAA",), slopes={"AAA": 1})
    rs, _ = calc(d, snap_universe(("AAA",)))
    row = rs["rows"][0]
    s = d[d.ticker == "AAA"].sort_values("date").close.reset_index(drop=True)
    expected = s.iloc[-1] / s.iloc[-64] - 1
    assert row["ret63"] == pytest.approx(expected, rel=0, abs=1e-14)


def test_display_sparkline_and_universe_metadata_are_preserved_without_affecting_rank():
    d = make_prices(tickers=("AAA",), slopes={"AAA": 1})
    universe = snap_universe(("AAA",))
    universe["name"] = "Alpha"
    universe["sector"] = "Technology"
    universe["industry"] = "Software"
    universe["exchange"] = "NASDAQ"
    rs, _ = calc(d, universe)
    row = rs["rows"][0]
    assert row["name"] == "Alpha"
    assert row["sector"] == "Technology"
    assert row["industry"] == "Software"
    assert row["exchange"] == "NASDAQ"
    assert len(row["sparkline"]) == 63
    assert row["sparkline"][-1]["date"] == SESSION
    assert row["sparkline"][-1]["close"] == pytest.approx(row["price"])
    assert row["ret1"] == pytest.approx(
        d.close.iloc[-1] / d.close.iloc[-2] - 1.0
    )
    diagnostics = rs["market_diagnostics"]
    assert diagnostics["status"] == "READY"
    assert diagnostics["series"][-1]["date"] == SESSION
    assert diagnostics["series"][-1]["observed"] == 1
    assert diagnostics["reason"] == "CURRENT_UNIVERSE_DISPLAY_DIAGNOSTIC_NOT_TRADING_GATE"


def test_display_metadata_does_not_leak_a_future_membership_event():
    d = make_prices(tickers=("AAA",), slopes={"AAA": 1})
    universe = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            "effective_from": ["2026-01-01", "2026-09-09"],
            "in_universe": [True, False],
            "name": ["Current Name", "Future Name"],
        }
    )
    rs, _ = calc(d, universe)
    assert rs["rows"][0]["name"] == "Current Name"


def test_rs_percentiles_are_cross_sectional_and_top_is_100():
    rs, _ = calc()
    by = {x["ticker"]: x for x in rs["rows"]}
    vals = sorted(x["rs189"] for x in by.values())
    assert vals == pytest.approx([25.0, 50.0, 75.0, 100.0])
    top = max(by.values(), key=lambda x: x["ret189"])
    assert top["rs189"] == pytest.approx(100.0)


def test_equal_return_ties_receive_same_percentile_and_ticker_order_is_stable():
    d = make_prices(slopes={"AAA": 1, "BBB": 1, "CCC": 3, "DDD": 4})
    # Force AAA/BBB identical close path to create an exact tie.
    aa = d[d.ticker == "AAA"].sort_values("date").close.to_numpy()
    bb_idx = d[d.ticker == "BBB"].sort_values("date").index
    d.loc[bb_idx, "close"] = aa
    d.loc[bb_idx, "high"] = aa * 1.01
    d.loc[bb_idx, "low"] = aa * 0.99
    rs, _ = calc(d)
    rows = rs["rows"]
    by = {x["ticker"]: x for x in rows}
    assert by["AAA"]["rs189"] == by["BBB"]["rs189"]
    tied = [x["ticker"] for x in rows if x["rs189"] == by["AAA"]["rs189"]]
    assert tied == sorted(tied)


def test_rs_universe_applies_price_and_ddv20_filters_without_changing_breadth_membership():
    d = make_prices()
    # AAA has valid SMA but insufficient dollar volume for RS.
    d.loc[d.ticker == "AAA", "volume"] = 1_000
    rs, breadth = calc(d)
    assert rs["coverage_detail"]["rs189_universe"] == 3
    assert breadth["coverage_detail"]["valid_sma50_count"] == 4


def test_breadth_missing_sma_is_excluded_from_denominator_not_false():
    tickers = ("AAA", "BBB", "CCC", "DDD")
    d = make_prices(tickers=tickers)
    # DDD only has 20 rows -> no SMA50, but remains valid current OHLCV.
    keep = (d.ticker != "DDD") | (d.groupby("ticker").cumcount() >= 240)
    d = d[keep].copy()
    _, breadth = calc(d)
    assert breadth["coverage_detail"]["valid_sma50_count"] == 3
    # All three long-history series are increasing and above SMA50.
    assert breadth["breadth50"] == pytest.approx(100.0)


def test_breadth_exact_3_of_4_is_75_percent():
    d = make_prices(slopes={"AAA": 1, "BBB": 2, "CCC": 3, "DDD": -1})
    _, breadth = calc(d)
    assert breadth["coverage_detail"]["valid_sma50_count"] == 4
    assert breadth["breadth50"] == pytest.approx(75.0)


def test_breadth200_is_null_below_max30_or_60pct_guard():
    tickers = tuple(f"T{i:02d}" for i in range(20))
    d = make_prices(tickers=tickers, slopes={t: 1 + i / 10 for i, t in enumerate(tickers)})
    _, breadth = calc(d, snap_universe(tickers))
    assert breadth["coverage_detail"]["valid_sma200_count"] == 20
    assert breadth["coverage_detail"]["min_sma200_count"] == 30
    assert breadth["breadth200"] is None
    assert breadth["breadth200_status"] == "DATA_INCOMPLETE"


def test_breadth200_calculates_when_guard_is_met():
    tickers = tuple(f"T{i:02d}" for i in range(50))
    slopes = {t: (1 if i < 40 else -1) for i, t in enumerate(tickers)}
    d = make_prices(tickers=tickers, slopes=slopes)
    _, breadth = calc(d, snap_universe(tickers))
    assert breadth["coverage_detail"]["min_sma200_count"] == 30
    assert breadth["coverage_detail"]["valid_sma200_count"] == 50
    assert breadth["breadth200"] == pytest.approx(80.0)


def test_output_is_deterministic_with_fixed_fixture_and_generated_at(tmp_path: Path):
    d = make_prices()
    u = snap_universe()
    op = tmp_path / "ohlcv.csv"
    up = tmp_path / "universe.csv"
    d.to_csv(op, index=False)
    u.to_csv(up, index=False)
    out1 = tmp_path / "o1"
    out2 = tmp_path / "o2"
    calculate_from_files(op, up, out1, session_date=SESSION, generated_at=GENERATED, source="fixture")
    calculate_from_files(op, up, out2, session_date=SESSION, generated_at=GENERATED, source="fixture")
    assert (out1 / "rs.json").read_bytes() == (out2 / "rs.json").read_bytes()
    assert (out1 / "breadth.json").read_bytes() == (out2 / "breadth.json").read_bytes()
    # Also prove JSON contains no NaN/Infinity spellings.
    assert "NaN" not in (out1 / "rs.json").read_text()


def test_future_ohlcv_rows_do_not_change_target_session_outputs():
    d = make_prices()
    rs1, b1 = calc(d)
    fut = d[d.date == SESSION].copy()
    fut["date"] = "2026-09-09"
    fut["close"] *= 9
    fut["high"] *= 9
    fut["low"] *= 9
    d2 = pd.concat([d, fut], ignore_index=True)
    rs2, b2 = calc(d2)
    assert rs1 == rs2
    assert b1 == b2


def test_invalid_effective_to_is_rejected_not_treated_as_open_ended():
    u = pd.DataFrame({"ticker": ["AAA"], "effective_from": ["2026-01-01"], "effective_to": ["broken-date"]})
    with pytest.raises(StockAdapterError, match="effective_to"):
        resolve_active_universe(u, SESSION)


def test_effective_from_only_is_rejected_because_removals_are_not_pit_provable():
    u = pd.DataFrame({"ticker": ["AAA"], "effective_from": ["2026-01-01"]})
    with pytest.raises(StockAdapterError, match="insufficient PIT evidence"):
        resolve_active_universe(u, SESSION)


def test_unresolved_historical_incomplete_bar_does_not_get_bridged():
    d = make_prices()
    # Make one historical dependency date incomplete with no final duplicate.
    target_idx = d[d.ticker == "AAA"].sort_values("date").index[-10]
    d.loc[target_idx, "is_complete"] = False
    rs, _ = calc(d)
    ex = {x["ticker"]: x["reasons"] for x in rs["excluded"]}
    assert "INCOMPLETE_BAR_IN_DEPENDENCY" in ex["AAA"]
    assert all(row["ticker"] != "AAA" for row in rs["rows"])


def test_ret20_and_high52_use_final_audited_definitions():
    d = make_prices(tickers=("AAA",), slopes={"AAA": 1}, periods=260)
    rs, _ = calc(d, snap_universe(("AAA",)))
    row = rs["rows"][0]
    g = d[d.ticker == "AAA"].sort_values("date").reset_index(drop=True)
    expected_ret20 = g.close.iloc[-1] / g.close.iloc[-21] - 1.0
    expected_high52 = g.high.iloc[-252:].max()
    assert row["ret20"] == pytest.approx(expected_ret20, rel=0, abs=1e-14)
    assert row["high52"] == pytest.approx(expected_high52, rel=0, abs=1e-14)
    assert row["dist52"] == pytest.approx(g.close.iloc[-1] / expected_high52 - 1.0, rel=0, abs=1e-14)


def test_high52_is_null_with_fewer_than_252_completed_sessions():
    d = make_prices(tickers=("AAA",), slopes={"AAA": 1}, periods=220)
    rs, _ = calc(d, snap_universe(("AAA",)))
    row = rs["rows"][0]
    assert row["high52"] is None
    assert row["dist52"] is None
