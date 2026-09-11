from __future__ import annotations

import pytest

from v38.f123_engine import calculate_f123

SESSION = "2026-09-08"
GENERATED = "2026-09-09T05:00:00+09:00"
SESSION_SEQUENCE_20 = [
    "2026-08-10",
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
    "2026-08-28",
    "2026-08-31",
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-04",
    "2026-09-08",
]


def row(ticker, *, rs189=95.0, rs63=95.0, price=120.0, ddv20=20_000_000.0,
        sma50=110.0, sma200=100.0, ret20=0.10, dist52=-0.05):
    return {
        "ticker": ticker,
        "price": price,
        "ddv20": ddv20,
        "sma50": sma50,
        "sma200": sma200,
        "ret20": ret20,
        "dist52": dist52,
        "rs63": rs63,
        "rs126": 95.0,
        "rs189": rs189,
    }


def rs_obj(rows):
    return {
        "session_date": SESSION,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "v38.rs.1",
        "calculation_version": "fixture",
        "rows": rows,
    }


def old24(names):
    return {
        "session_date": "2026-08-10",
        "target_session_date": SESSION,
        "lag_sessions": 20,
        "pit_frozen": True,
        "calendar_source": "fixture:XNYS/XNAS completed sessions",
        "session_sequence": list(SESSION_SEQUENCE_20),
        "source": "fixture:PIT",
        "calculation_version": "fixture",
        "rows": [{"ticker": t} for t in names],
    }


def test_f1_20_observable_5_drop_is_25pct_and_83pct_partial():
    old_names = [f"T{i:02d}" for i in range(24)]
    rows = []
    for i in range(20):
        rows.append(row(f"T{i:02d}", rs189=100 - i * 0.1, sma50=(90.0 if i < 5 else 110.0)))
    for i in range(24, 44):
        rows.append(row(f"T{i:02d}", rs189=80 - (i - 24) * 0.1, rs63=80.0))
    out = calculate_f123(rs_obj(rows), generated_at=GENERATED, old_top24=old24(old_names))
    f1 = out["f1"]
    assert f1["observable_count"] == 20
    assert f1["drop_count"] == 5
    assert f1["value"] == pytest.approx(0.25)
    assert f1["coverage"] == pytest.approx(20 / 24)
    assert f1["status"] == "PARTIAL"
    assert f1["severity"] == "CAUTION"
    assert f1["unknown_count"] == 4
    assert f1["dependency"]["session_sequence_count"] == 21
    assert f1["dependency"]["lag_sessions"] == 20


def test_f1_below_70pct_coverage_is_data_incomplete_and_not_fabricated():
    old_names = [f"T{i:02d}" for i in range(24)]
    rows = [row(f"T{i:02d}", rs189=100 - i) for i in range(16)]
    out = calculate_f123(rs_obj(rows), generated_at=GENERATED, old_top24=old24(old_names))
    assert out["f1"]["coverage"] == pytest.approx(16 / 24)
    assert out["f1"]["value"] is None
    assert out["f1"]["status"] == "DATA_INCOMPLETE"


def test_f1_refuses_unproven_old_top24_provenance():
    bad = {"session_date": "2026-08-10", "rows": [{"ticker": "AAA"}]}
    out = calculate_f123(rs_obj([row("AAA")]), generated_at=GENERATED, old_top24=bad)
    assert out["f1"]["status"] == "DATA_REQUIRED"
    assert out["f1"]["dependency"]["reason"] == "PIT_OLD_TOP24_PROVENANCE_UNVERIFIED"


def test_f1_rejects_old_fixture_that_is_only_19_sessions_back():
    bad = old24(["AAA"])
    bad["session_date"] = "2026-08-11"
    bad["session_sequence"] = bad["session_sequence"][1:]
    out = calculate_f123(rs_obj([row("AAA")]), generated_at=GENERATED, old_top24=bad)
    dep = out["f1"]["dependency"]
    assert out["f1"]["status"] == "DATA_REQUIRED"
    assert dep["reason"] == "PIT_OLD_TOP24_PROVENANCE_UNVERIFIED"
    assert dep["sequence_count"] == 20


def test_f1_rejects_target_session_mismatch():
    bad = old24(["AAA"])
    bad["target_session_date"] = "2026-09-04"
    out = calculate_f123(rs_obj([row("AAA")]), generated_at=GENERATED, old_top24=bad)
    assert out["f1"]["status"] == "DATA_REQUIRED"
    assert out["f1"]["dependency"]["detail"] == "target_session_date does not match current rs.session_date"


def test_f2_valid20_below85_8_is_40pct_severe():
    rows = []
    for i in range(30):
        rs63 = (80.0 if i < 8 else (None if 20 <= i < 24 else 90.0))
        rows.append(row(f"T{i:02d}", rs189=100 - i * 0.5, rs63=rs63))
    out = calculate_f123(rs_obj(rows), generated_at=GENERATED)
    f2 = out["f2"]
    assert f2["top24_count"] == 24
    assert f2["observable_count"] == 20
    assert f2["weak_count"] == 8
    assert f2["value"] == pytest.approx(0.40)
    assert f2["severity"] == "SEVERE"


def test_f3_queue10_bad6_is_60pct_severe():
    rows = []
    for i in range(10):
        rows.append(row(f"T{i:02d}", rs189=95 - i * 0.5, ret20=(-0.01 if i < 6 else 0.05), dist52=-0.05))
    out = calculate_f123(rs_obj(rows), generated_at=GENERATED)
    f3 = out["f3"]
    assert f3["queue_count"] == 10
    assert f3["break_count"] == 6
    assert f3["value"] == pytest.approx(0.60)
    assert f3["severity"] == "SEVERE"


def test_f3_queue_below_3_has_no_judgment():
    rows = [row("AAA", rs189=95), row("BBB", rs189=90)]
    out = calculate_f123(rs_obj(rows), generated_at=GENERATED)
    assert out["f3"]["queue_count"] == 2
    assert out["f3"]["value"] is None
    assert out["f3"]["status"] == "NO_JUDGMENT"
    assert out["f3"]["severity"] == "NO_JUDGMENT"


def test_f3_missing_ret20_or_dist52_is_data_incomplete_not_false():
    rows = [row("AAA", rs189=95), row("BBB", rs189=94), row("CCC", rs189=93, dist52=None)]
    out = calculate_f123(rs_obj(rows), generated_at=GENERATED)
    assert out["f3"]["queue_count"] == 3
    assert out["f3"]["observable_count"] == 2
    assert out["f3"]["value"] is None
    assert out["f3"]["status"] == "DATA_INCOMPLETE"
