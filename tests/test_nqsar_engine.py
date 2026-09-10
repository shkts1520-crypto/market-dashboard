import pytest

from v38.nqsar_engine import (
    NQSARError,
    NQSAR_SPEC,
    authoritative_state,
    readiness,
    validate_state,
)

SESSION = "2026-09-08"
GENERATED = "2026-09-10T19:00:00+09:00"


def test_readiness_is_data_required_without_exact_fsm_reference():
    out = readiness(
        session_date=SESSION,
        generated_at=GENERATED,
    )

    assert out["status"] == "DATA_REQUIRED"
    assert out["state"] is None


def test_partial_reference_does_not_unlock_nqsar():
    out = readiness(
        session_date=SESSION,
        generated_at=GENERATED,
        reference={
            "verified": True,
            "fsm_version": "v1",
        },
    )

    assert out["status"] == "DATA_REQUIRED"
    assert (
        "GOLDEN_FIXTURE_SHA256"
        in out["data_required"]
    )


def test_complete_reference_reports_ready_but_does_not_invent_state():
    out = readiness(
        session_date=SESSION,
        generated_at=GENERATED,
        reference={
            "verified": True,
            "fsm_version": "v1",
            "golden_fixture_sha256": "abc",
        },
    )

    assert out["status"] == "READY"
    assert out["state"] is None


def test_state_validation_accepts_only_four_canonical_states():
    for state in (
        "Blue",
        "Green",
        "Yellow",
        "Red",
    ):
        assert validate_state(state) == state

    with pytest.raises(NQSARError):
        validate_state("BLUE")


def test_known_nqsar_indicator_parameters_are_frozen():
    assert NQSAR_SPEC["psar"] == {
        "step": 0.02,
        "increment": 0.02,
        "max": 0.08,
    }

    assert NQSAR_SPEC["ema"] == {
        "span": 21,
        "adjust": False,
    }

    assert NQSAR_SPEC["rsi"] == {
        "period": 14,
        "method": "Wilder",
    }


def test_authoritative_state_requires_source_and_preserves_session():
    with pytest.raises(NQSARError):
        authoritative_state(
            "Blue",
            session_date=SESSION,
            generated_at=GENERATED,
            source="",
        )

    out = authoritative_state(
        "Green",
        session_date=SESSION,
        generated_at=GENERATED,
        source="golden-fixture",
    )

    assert out["state"] == "Green"
    assert out["session_date"] == SESSION
    assert out["source"] == "golden-fixture"
