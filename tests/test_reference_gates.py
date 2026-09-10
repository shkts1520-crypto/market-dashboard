from v38.reference_gates import (
    DATA_REQUIRED,
    READY,
    mc57_reference_gate,
    nqsar_reference_gate,
    overall_reference_status,
)


def test_nqsar_gate_blocks_missing_reference():
    gate = nqsar_reference_gate(None)

    assert gate.status == DATA_REQUIRED
    assert "FSM_VERSION" in gate.missing


def test_nqsar_gate_ready_only_with_verified_fixture():
    gate = nqsar_reference_gate(
        {
            "verified": True,
            "fsm_version": "authoritative-v1",
            "golden_fixture_sha256": "abc",
            "source": "fixture",
        }
    )

    assert gate.status == READY


def test_mc57_gate_requires_exactly_57_unique_tickers():
    gate = mc57_reference_gate(
        {
            "verified": True,
            "etf_universe": [
                f"E{i}"
                for i in range(56)
            ],
            "golden_fixture_sha256": "abc",
        }
    )

    assert gate.status == DATA_REQUIRED

    assert (
        "FIXED_57_ETF_UNIVERSE"
        in gate.missing
    )


def test_overall_reference_status_requires_all_ready():
    nq = nqsar_reference_gate(
        {
            "verified": True,
            "fsm_version": "v1",
            "golden_fixture_sha256": "a",
        }
    )

    mc = mc57_reference_gate(
        {
            "verified": True,
            "etf_universe": [
                f"E{i}"
                for i in range(57)
            ],
            "golden_fixture_sha256": "b",
        }
    )

    assert (
        overall_reference_status(
            nq,
            mc,
        )
        == READY
    )

    assert (
        overall_reference_status(
            nq,
            mc57_reference_gate(None),
        )
        == DATA_REQUIRED
    )
