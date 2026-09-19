from __future__ import annotations

import json

import pytest

from v38.ui_view_model import DATA_REQUIRED, READY, STALE, UIViewModelError, build_ui_view_model, write_ui_view_model

SESSION = "2026-09-10"


def dump(root, name, obj):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def meta(**extra):
    out = {
        "session_date": SESSION,
        "generated_at": "2026-09-10T23:29:35Z",
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "fixture.1",
        "calculation_version": "fixture.1",
    }
    out.update(extra)
    return out


def fixtures(root):
    dump(root, "state.json", meta())
    dump(root, "breadth.json", meta(breadth50=39.5015, breadth200=58.5865))
    dump(
        root,
        "f123.json",
        meta(
            f1={"status": "DATA_REQUIRED", "value": None, "severity": "NO_JUDGMENT", "dependency": {"reason": "PIT_OLD_TOP24_MISSING"}},
            f2={"status": "OK", "value": 0.5416666667, "severity": "SEVERE"},
            f3={"status": "DATA_INCOMPLETE", "value": None, "severity": "NO_JUDGMENT"},
        ),
    )
    dump(
        root,
        "rs.json",
        meta(
            coverage=0.9829,
            market_diagnostics={
                "status": "READY",
                "reason": "CURRENT_UNIVERSE_DISPLAY_DIAGNOSTIC_NOT_TRADING_GATE",
                "series": [{"date": SESSION, "observed": 2, "mcclellan": 1.5}],
            },
            rows=[
                {"ticker": "AAA", "price": 10, "rs189": 99, "rs126": 97, "rs63": 91, "ret1": 0.01, "ret20": 0.10, "ddv20": 20_000_000, "sector": "Technology", "industry": "Software", "sparkline": [{"date": "2026-09-09", "close": 9}, {"date": SESSION, "close": 10}]},
                {"ticker": "BBB", "price": 20, "rs189": 98, "rs126": 96, "rs63": 90, "ret1": -0.01, "ret20": 0.05, "ddv20": 30_000_000, "sector": "Technology", "industry": "Software"},
            ],
        ),
    )
    dump(
        root,
        "market_inputs.json",
        meta(
            series={
                "QQQ": [{"date": SESSION, "close": 612.34}],
                "TQQQ": [{"date": SESSION, "close": 98.76}],
                "^VIX": [{"date": SESSION, "close": 15.12}],
                "NQ=F": [{"date": SESSION, "close": 24123.25}],
                "SPY": [{"date": SESSION, "close": 691.23}],
            }
        ),
    )


def metric(out, key):
    return next(x for x in out["daily"]["metrics"] if x["key"] == key)


def test_state_session_is_required(tmp_path):
    with pytest.raises(UIViewModelError):
        build_ui_view_model(tmp_path)


def test_live_breadth_values_are_exposed_without_browser_calculation(tmp_path):
    fixtures(tmp_path)
    out = build_ui_view_model(tmp_path)
    assert metric(out, "breadth50")["display"] == "39.5%"
    assert metric(out, "breadth200")["display"] == "58.6%"
    assert metric(out, "breadth50")["status"] == READY


def test_stale_breadth_is_explicitly_stale(tmp_path):
    fixtures(tmp_path)
    dump(tmp_path, "breadth.json", meta(session_date="2026-09-09", breadth50=60, breadth200=70))
    out = build_ui_view_model(tmp_path)
    assert metric(out, "breadth50")["status"] == STALE
    assert "SESSION_MISMATCH" in metric(out, "breadth50")["reason"]


def test_missing_breadth_never_becomes_zero(tmp_path):
    fixtures(tmp_path)
    (tmp_path / "breadth.json").unlink()
    out = build_ui_view_model(tmp_path)
    assert metric(out, "breadth50")["status"] == DATA_REQUIRED
    assert metric(out, "breadth50")["display"] == "—"


def test_f2_fraction_is_displayed_as_percent(tmp_path):
    fixtures(tmp_path)
    out = build_ui_view_model(tmp_path)
    assert metric(out, "f2")["display"] == "54.2%"
    assert metric(out, "f2")["status"] == READY
    assert metric(out, "f2")["severity"] == "SEVERE"


def test_f1_dependency_reason_survives_fail_closed(tmp_path):
    fixtures(tmp_path)
    out = build_ui_view_model(tmp_path)
    assert metric(out, "f1")["display"] == "—"
    assert metric(out, "f1")["status"] == DATA_REQUIRED
    assert metric(out, "f1")["reason"] == "PIT_OLD_TOP24_MISSING"


def test_rs_order_is_preserved_and_not_re_ranked(tmp_path):
    fixtures(tmp_path)
    out = build_ui_view_model(tmp_path)
    assert [x["ticker"] for x in out["rs"]["rows"]] == ["AAA", "BBB"]
    assert [x["rank"] for x in out["rs"]["rows"]] == [1, 2]
    assert out["rs"]["rows"][0]["price_display"] == "10.00"
    assert out["rs"]["rows"][0]["rs189_display"] == "99.0"
    assert out["rs"]["rows"][0]["rs63_display"] == "91.0"
    assert out["rs"]["rows"][0]["rs126_display"] == "97.0"
    assert len(out["rs"]["rows"][0]["sparkline"]) == 2
    assert out["rs"]["windows"]["63"][0]["ticker"] == "AAA"
    assert "not Core 12" in out["rs"]["note"]


def test_market_series_summaries_and_current_history_are_exposed(tmp_path):
    fixtures(tmp_path)
    dates = ["2026-09-04", "2026-09-08", "2026-09-09", SESSION]
    dump(
        tmp_path,
        "market_inputs.json",
        meta(series={"QQQ": [
            {"date": day, "close": close, "high": close + 1, "volume": 1000 + i}
            for i, (day, close) in enumerate(zip(dates, (100, 102, 101, 104)))
        ]}),
    )
    out = build_ui_view_model(tmp_path)
    assert len(out["daily"]["market_series"]["QQQ"]) == 4
    assert out["daily"]["market_summaries"]["QQQ"]["change_1d"] == pytest.approx(104 / 101 - 1)
    assert out["daily"]["history"][-1]["date"] == SESSION
    assert out["daily"]["history"][-1]["breadth50"] == pytest.approx(39.5015)
    assert out["daily"]["market_diagnostics"]["status"] == READY
    assert out["daily"]["market_diagnostics"]["series"][-1]["mcclellan"] == pytest.approx(1.5)


def test_rs_view_is_limited_to_first_24_source_rows(tmp_path):
    fixtures(tmp_path)
    rows = [{"ticker": f"X{i:02d}", "price": i + 1, "rs189": 100 - i, "rs63": 90, "ddv20": 1e8} for i in range(30)]
    dump(tmp_path, "rs.json", meta(rows=rows))
    out = build_ui_view_model(tmp_path)
    assert len(out["rs"]["rows"]) == 24
    assert out["rs"]["rows"][-1]["ticker"] == "X23"


def test_market_close_uses_only_target_session_bar(tmp_path):
    fixtures(tmp_path)
    dump(
        tmp_path,
        "market_inputs.json",
        meta(series={"QQQ": [{"date": "2026-09-09", "close": 999}, {"date": SESSION, "close": 612.34}]}),
    )
    out = build_ui_view_model(tmp_path)
    assert metric(out, "market_QQQ")["display"] == "612.34"
    assert metric(out, "market_QQQ")["status"] == READY


def test_missing_nqsar_mc57_and_market_mode_are_not_inferred(tmp_path):
    fixtures(tmp_path)
    out = build_ui_view_model(tmp_path)
    assert metric(out, "nqsar")["display"] == "—"
    assert metric(out, "mc57")["display"] == "—"
    assert metric(out, "market_mode")["display"] == "—"
    assert metric(out, "nqsar")["status"] == DATA_REQUIRED
    assert metric(out, "mc57")["status"] == DATA_REQUIRED


def test_writer_emits_strict_json_without_nan(tmp_path):
    fixtures(tmp_path)
    path = write_ui_view_model(tmp_path, tmp_path / "out.json")
    text = path.read_text(encoding="utf-8")
    assert "NaN" not in text
    obj = json.loads(text)
    assert obj["session_date"] == SESSION


def test_ratio_observations_require_current_session_rows(tmp_path):
    fixtures(tmp_path)
    prior = "2026-09-09"
    dump(
        tmp_path,
        "market_inputs.json",
        meta(series={
            "XLY": [{"date": "2026-09-08", "close": 100}, {"date": prior, "close": 101}],
            "XLP": [{"date": "2026-09-08", "close": 50}, {"date": prior, "close": 51}],
            "HYG": [{"date": prior, "close": 80}],
            "IEF": [{"date": prior, "close": 90}],
            "^VIX": [{"date": prior, "close": 15}],
            "^VIX3M": [{"date": prior, "close": 17}],
            "^VXN": [{"date": prior, "close": 18}],
        }),
    )
    out = build_ui_view_model(tmp_path)
    obs = out["daily"]["card_observations"]
    assert obs["risk_rotation"]["status"] == DATA_REQUIRED
    assert obs["risk_rotation"]["current"] is None
    assert obs["risk_rotation"]["reason"] == "SESSION_BAR_MISSING"
    assert obs["credit_ratio"]["status"] == DATA_REQUIRED
    assert obs["vix_term"]["status"] == DATA_REQUIRED
    assert obs["expected_move"]["status"] == DATA_REQUIRED
    assert obs["expected_move"]["spy_1m_pct"] is None
    assert obs["expected_move"]["qqq_1m_pct"] is None


def test_ratio_and_expected_move_ready_only_on_current_session(tmp_path):
    fixtures(tmp_path)
    prior = "2026-09-09"
    dump(
        tmp_path,
        "market_inputs.json",
        meta(series={
            "XLY": [{"date": prior, "close": 100}, {"date": SESSION, "close": 102}],
            "XLP": [{"date": prior, "close": 50}, {"date": SESSION, "close": 51}],
            "HYG": [{"date": prior, "close": 80}, {"date": SESSION, "close": 81}],
            "IEF": [{"date": prior, "close": 90}, {"date": SESSION, "close": 90.5}],
            "^VIX": [{"date": prior, "close": 15}, {"date": SESSION, "close": 16}],
            "^VIX3M": [{"date": prior, "close": 17}, {"date": SESSION, "close": 18}],
            "^VXN": [{"date": prior, "close": 18}, {"date": SESSION, "close": 19}],
        }),
    )
    out = build_ui_view_model(tmp_path)
    obs = out["daily"]["card_observations"]
    assert obs["risk_rotation"]["status"] == READY
    assert obs["risk_rotation"]["current"] == pytest.approx(102 / 51)
    assert obs["credit_ratio"]["status"] == READY
    assert obs["vix_term"]["status"] == READY
    assert obs["expected_move"]["status"] == READY
    assert obs["expected_move"]["reason"] == "CURRENT_SESSION_IV"


def test_market_summary_hides_stale_current_values(tmp_path):
    fixtures(tmp_path)
    dump(
        tmp_path,
        "market_inputs.json",
        meta(series={
            "QQQ": [
                {"date": "2026-09-08", "close": 100, "high": 101},
                {"date": "2026-09-09", "close": 102, "high": 103},
            ]
        }),
    )
    out = build_ui_view_model(tmp_path)
    summary = out["daily"]["market_summaries"]["QQQ"]
    assert summary["status"] == DATA_REQUIRED
    assert summary["reason"] == "SESSION_BAR_MISSING"
    assert summary["close"] is None
    assert summary["change_1d"] is None


def test_market_summary_is_ready_on_exact_session(tmp_path):
    fixtures(tmp_path)
    dump(
        tmp_path,
        "market_inputs.json",
        meta(series={
            "QQQ": [
                {"date": "2026-09-09", "close": 100, "high": 101},
                {"date": SESSION, "close": 102, "high": 103},
            ]
        }),
    )
    out = build_ui_view_model(tmp_path)
    summary = out["daily"]["market_summaries"]["QQQ"]
    assert summary["status"] == READY
    assert summary["reason"] == "CURRENT_SESSION_CLOSE"
    assert summary["close"] == pytest.approx(102)
    assert summary["change_1d"] == pytest.approx(0.02)
