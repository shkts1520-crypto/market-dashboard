import pytest

from v38.f123_display import complete_f123_for_display


def test_reconstructed_f1_is_used_only_when_exact_pit_is_missing_and_f3_partial_keeps_full_denominator():
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
    assert out["f1"]["value"] == 0.25
    assert out["f1"]["status"] == "FULL"
    assert out["f1"]["display_only"] is True
    assert out["f1"]["display_source"] == "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC_NOT_PIT"
    assert out["f3"]["status"] == "PARTIAL"
    assert out["f3"]["value"] == pytest.approx(185 / 307)
    assert out["f3"]["coverage"] == pytest.approx(304 / 307)
    assert out["display_completion_policy"]["hard_gate"] is False


def test_exact_pit_f1_is_never_overwritten():
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
