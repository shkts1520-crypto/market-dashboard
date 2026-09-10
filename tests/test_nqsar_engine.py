import pytest

from v38.nqsar_engine import (
    EXP_STATE_ID_TO_STATE,
    NQSARError,
    NQSAR_SPEC,
    authoritative_state,
    parse_authoritative_input,
    parse_sar_state_text,
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


@pytest.mark.parametrize(
    ("exp_state_id", "expected"),
    sorted(EXP_STATE_ID_TO_STATE.items()),
)
def test_parse_authoritative_exp_state_ids(
    exp_state_id,
    expected,
):
    out = parse_authoritative_input(
        {
            "session_date": SESSION,
            "generated_at": "2026-09-08T16:05:00-04:00",
            "source": "NQ.csv:EXP_STATE_ID",
            "exp_state_id": exp_state_id,
        },
        expected_session_date=SESSION,
        as_of=GENERATED,
    )

    assert out["state"] == expected
    assert out["exp_state_id"] == exp_state_id
    assert out["input_kind"] == "EXP_STATE_ID"


@pytest.mark.parametrize(
    "bad_session",
    [
        "2026-09-07",
        "2026-09-09",
    ],
)
def test_parse_authoritative_input_rejects_stale_or_future_session(
    bad_session,
):
    with pytest.raises(NQSARError):
        parse_authoritative_input(
            {
                "session_date": bad_session,
                "generated_at": "2026-09-08T16:05:00-04:00",
                "source": "sar_state.txt",
                "state": "Blue",
            },
            expected_session_date=SESSION,
            as_of=GENERATED,
        )


def test_parse_authoritative_input_rejects_missing_future_and_conflicting_metadata():
    with pytest.raises(NQSARError):
        parse_authoritative_input(
            {
                "generated_at": "2026-09-08T16:05:00-04:00",
                "source": "sar_state.txt",
                "state": "Blue",
            },
            expected_session_date=SESSION,
            as_of=GENERATED,
        )

    with pytest.raises(NQSARError):
        parse_authoritative_input(
            {
                "session_date": SESSION,
                "generated_at": "2026-09-11T00:00:00+09:00",
                "source": "sar_state.txt",
                "state": "Blue",
            },
            expected_session_date=SESSION,
            as_of=GENERATED,
        )

    with pytest.raises(NQSARError):
        parse_authoritative_input(
            {
                "session_date": SESSION,
                "generated_at": "2026-09-08T16:05:00-04:00",
                "source": "NQ.csv:EXP_STATE_ID",
                "state": "Blue",
                "exp_state_id": 3,
            },
            expected_session_date=SESSION,
            as_of=GENERATED,
        )


def test_parse_sar_state_text_accepts_recovered_json_aliases():
    samples = [
        '{"asof":"2026-09-08","color":"blue"}',
        '{"date":"2026-09-08","state":"Green"}',
        '{"session":"2026-09-08","sar":"YELLOW"}',
    ]

    expected = [
        "Blue",
        "Green",
        "Yellow",
    ]

    for raw, state in zip(
        samples,
        expected,
        strict=True,
    ):
        out = parse_sar_state_text(
            raw,
            generated_at="2026-09-08T16:05:00-04:00",
            expected_session_date=SESSION,
            as_of=GENERATED,
        )

        assert out["state"] == state
        assert out["source"] == "sar_state.txt"


def test_parse_sar_state_text_accepts_recovered_csvish_format():
    out = parse_sar_state_text(
        "2026-09-08,Red",
        generated_at="2026-09-08T16:05:00-04:00",
        expected_session_date=SESSION,
        as_of=GENERATED,
    )

    assert out["state"] == "Red"
    assert out["session_date"] == SESSION


def test_parse_sar_state_text_rejects_undated_stale_and_future_text():
    with pytest.raises(NQSARError):
        parse_sar_state_text(
            "Blue",
            generated_at="2026-09-08T16:05:00-04:00",
            expected_session_date=SESSION,
            as_of=GENERATED,
        )

    with pytest.raises(NQSARError):
        parse_sar_state_text(
            "2026-09-07,Blue",
            generated_at="2026-09-08T16:05:00-04:00",
            expected_session_date=SESSION,
            as_of=GENERATED,
        )

    with pytest.raises(NQSARError):
        parse_sar_state_text(
            '{"asof":"2026-09-09","color":"Blue"}',
            generated_at="2026-09-08T16:05:00-04:00",
            expected_session_date=SESSION,
            as_of=GENERATED,
        )
