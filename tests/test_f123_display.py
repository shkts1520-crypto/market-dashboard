import pytest

from v38.f123_display import complete_f123_for_display


def test_reconstructed_f1_and_partial_f3_are_display_overrides_only():
    session = "2026-09-11"
    f123 = {
        "session_date": session,
        "generated_at": "old",
        "status": "READY",
        "f1": {
            "value": None,
            "status": "DATA_REQUIRED",
            "dependency": {"status": "DATA_REQUIRED", "reason": "PIT_OLD_TOP24_MISSING"},
        },
        "f2": {"value": 0.25, "status": "OK"},
        "f3": {
            "value": None,
            "status": "DATA_INCOMPLETE",
            "queue_count": 307,
            "observable_count": 304,
            "break_count": 185,
        },
    }
    reconstructed = {
        "session_date": session,
        "status": "READY",
        "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
        "rows": [
            {
                "date": session,
                "f1": {
                    "value": 0.25,
                    "status": "FULL",
                    "severity": "CAUTION",
                    "coverage": 1.0,
                    "old_top24_count": 24,
                    "observable_count": 24,
                    "drop_count": 6,
                },
            }
        ],
    }
    out = complete_f123_for_display(
        f123,
        reconstructed,
        session_date=session,
        generated_at="new",
    )
    assert out["f1"]["value"] is None
    assert out["f1"]["status"] == "DATA_REQUIRED"
    assert out["f3"]["value"] is None
    assert out["f3"]["status"] == "DATA_INCOMPLETE"

    f1_display = out["display_overrides"]["f1"]
    assert f1_display["value"] == 0.25
    assert f1_display["display_only"] is True
    assert f1_display["trading_gate_eligible"] is False
    assert f1_display["display_source"] == "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC_NOT_PIT"

    f3_display = out["display_overrides"]["f3"]
    assert f3_display["status"] == "PARTIAL"
    assert f3_display["value"] == pytest.approx(185 / 307)
    assert f3_display["coverage"] == pytest.approx(304 / 307)
    assert f3_display["display_only"] is True
    assert out["display_completion_policy"]["hard_gate"] is False


def test_exact_pit_f1_is_never_overwritten_or_given_override():
    session = "2026-09-11"
    f123 = {
        "session_date": session,
        "f1": {
            "value": 0.1,
            "status": "FULL",
            "dependency": {"status": "OK"},
        },
        "f3": {"value": 0.2, "status": "OK", "queue_count": 10, "observable_count": 10, "break_count": 2},
    }
    reconstructed = {
        "session_date": session,
        "status": "READY",
        "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
        "rows": [{"date": session, "f1": {"value": 0.9, "status": "FULL"}}],
    }
    out = complete_f123_for_display(
        f123,
        reconstructed,
        session_date=session,
        generated_at="new",
    )
    assert out["f1"]["value"] == 0.1
    assert out["f1"]["dependency"]["status"] == "OK"
    assert "f1" not in out["display_overrides"]
