from __future__ import annotations

import pytest

from v38.authority_contracts import AuthorityContractError, validate_authority
from v38.mc57_engine import MC57_METRICS

SESSION = "2026-09-10"
GEN = "2026-09-11T12:00:00Z"


def common(**extra):
    return {
        "session_date": SESSION,
        "generated_at": GEN,
        "source": "test-authority",
        "coverage": 1.0,
        **extra,
    }


def test_nqsar_state_promotes_without_recomputing_fsm():
    target, obj = validate_authority("nqsar", common(state="Green"), expected_session=SESSION)
    assert target == "nqsar.json"
    assert obj["status"] == "READY"
    assert obj["state"] == "Green"
    assert obj["fsm_recomputed"] is False


def test_nqsar_exp_state_id_mapping_is_frozen():
    _, obj = validate_authority("nqsar", common(exp_state_id=3), expected_session=SESSION)
    assert obj["state"] == "Red"


def test_nqsar_rejects_unknown_state():
    with pytest.raises(AuthorityContractError):
        validate_authority("nqsar", common(state="Purple"), expected_session=SESSION)


def classification_payload():
    return common(
        classification_version="clinical-v1",
        rows=[
            {
                "ticker": "AAA",
                "structural_clinical_biotech": False,
                "rationale": "authoritative classifier output",
                "effective_from": "2026-01-01",
                "effective_to": None,
            },
            {
                "ticker": "BBB",
                "structural_clinical_biotech": True,
                "rationale": "authoritative classifier output",
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
            },
        ],
    )


def test_classification_requires_effective_current_rows():
    target, obj = validate_authority("classifications", classification_payload(), expected_session=SESSION)
    assert target == "classifications.json"
    assert len(obj["rows"]) == 2
    assert obj["classification_version"] == "clinical-v1"


def test_classification_rejects_out_of_effective_range():
    payload = classification_payload()
    payload["rows"][0]["effective_to"] = "2026-01-31"
    with pytest.raises(AuthorityContractError):
        validate_authority("classifications", payload, expected_session=SESSION)


def theme_payload():
    return common(
        upstream_calculation_version="peer-theme-upstream-v1",
        pit=True,
        strict_loo=True,
        rows=[
            {
                "ticker": "AAA",
                "theme_id": "T100",
                "theme_rs63_percentile": 90.0,
                "rank_acceleration_percentile": 60.0,
                "ema21_breadth_score": 75.0,
                "peer_theme_score": 75.0,
            }
        ],
    )


def test_peer_theme_requires_strict_loo_and_pit():
    target, obj = validate_authority("theme_scores", theme_payload(), expected_session=SESSION)
    assert target == "theme_scores.json"
    assert obj["strict_loo"] is True
    assert obj["pit"] is True


def test_peer_theme_rejects_non_mean_score():
    payload = theme_payload()
    payload["rows"][0]["peer_theme_score"] = 80.0
    with pytest.raises(AuthorityContractError):
        validate_authority("theme_scores", payload, expected_session=SESSION)


def mc57_payload():
    scores = {name: 50.0 for name in MC57_METRICS}
    return common(
        member_set_version="fixed57-v1",
        golden_fixture_version="mc57-golden-v1",
        members=[f"T{i:02d}" for i in range(57)],
        metric_scores=scores,
        raw=50.0,
        ema2_raw=60.0,
        mu_prior=50.0,
        sigma_prior=10.0,
        z=1.0,
        mc57=75.0,
        calibration_lookback_sessions=3780,
        upstream_calculation_version="mc57-upstream-v1",
    )


def test_mc57_requires_exact_fixed57_and_math():
    target, obj = validate_authority("mc57", mc57_payload(), expected_session=SESSION)
    assert target == "mc57.json"
    assert obj["fixed_member_count"] == 57
    assert obj["metric_count"] == 12
    assert obj["mc57"] == 75.0


def test_mc57_rejects_member_count_56():
    payload = mc57_payload()
    payload["members"].pop()
    with pytest.raises(AuthorityContractError):
        validate_authority("mc57", payload, expected_session=SESSION)


def test_mc57_rejects_wrong_transform():
    payload = mc57_payload()
    payload["mc57"] = 74.0
    with pytest.raises(AuthorityContractError):
        validate_authority("mc57", payload, expected_session=SESSION)


def options_payload():
    return common(
        provider="authoritative-options-provider",
        upstream_calculation_version="options-upstream-v1",
        sign_model="calls_positive_puts_negative",
        rows=[
            {
                "ticker": "AAA",
                "dte_bucket": "0-6",
                "spot": 100.0,
                "call_wall": 105.0,
                "put_wall": 95.0,
                "gamma_flip": 99.0,
                "net_gex": 123456.0,
                "expected_move": 4.0,
                "direction": "UP",
                "confidence": "MEDIUM",
                "quality": "FULL",
            }
        ],
    )


def test_options_preserves_upstream_direction_confidence_quality():
    target, obj = validate_authority("options", options_payload(), expected_session=SESSION)
    assert target == "options/index.json"
    assert obj["rows"][0]["direction"] == "UP"
    assert obj["gex_formula"] == "Gamma*OI*100*Spot^2*0.01"


def test_options_rejects_wrong_sign_model():
    payload = options_payload()
    payload["sign_model"] = "unsigned"
    with pytest.raises(AuthorityContractError):
        validate_authority("options", payload, expected_session=SESSION)


def positions_payload():
    return common(
        ledger_version="broker-ledger-v1",
        cash=1000.0,
        portfolio_empty=False,
        flows=[],
        rows=[
            {
                "position_id": "AAA-20260901",
                "ticker": "AAA",
                "sleeve": "NORMAL_STOCK",
                "quantity": 10,
                "entry_date": "2026-09-01",
                "entry": 100.0,
                "close": 120.0,
                "peak_close": 125.0,
                "partial_taken": False,
            }
        ],
    )


def test_positions_requires_explicit_ledger_state():
    target, obj = validate_authority("positions", positions_payload(), expected_session=SESSION)
    assert target == "positions_ledger.json"
    assert obj["cash"] == 1000.0
    assert obj["rows"][0]["partial_taken"] is False


def test_empty_positions_requires_explicit_portfolio_empty():
    payload = common(ledger_version="v1", cash=0.0, rows=[], flows=[])
    with pytest.raises(AuthorityContractError):
        validate_authority("positions", payload, expected_session=SESSION)
    payload["portfolio_empty"] = True
    _, obj = validate_authority("positions", payload, expected_session=SESSION)
    assert obj["rows"] == []


def test_all_authorities_reject_session_mismatch():
    with pytest.raises(AuthorityContractError):
        validate_authority("nqsar", common(state="Blue"), expected_session="2026-09-09")
