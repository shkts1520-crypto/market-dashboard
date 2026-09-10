from __future__ import annotations

import copy

import pytest

from v38.market_engine import MarketEngineError, calculate_market_outputs, determine_market_mode

SESSION = "2026-09-08"
GENERATED = "2026-09-10T11:30:00+09:00"


def rs_fixture():
    return {
        "session_date": SESSION,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "v38.rs.1",
        "calculation_version": "fixture",
        "rows": [
            {"ticker": "AAA", "price": 100, "ddv20": 20_000_000, "sma50": 90, "sma200": 80, "rs63": 95, "rs126": 94, "rs189": 96},
            {"ticker": "BBB", "price": 100, "ddv20": 20_000_000, "sma50": 90, "sma200": 80, "rs63": 90, "rs126": 91, "rs189": 92},
            {"ticker": "CCC", "price": 100, "ddv20": 20_000_000, "sma50": 90, "sma200": 80, "rs63": 80, "rs126": 90, "rs189": 99},
        ],
    }


def breadth_fixture(b50=61.0):
    return {"session_date": SESSION, "generated_at": GENERATED, "coverage": 1.0, "source": "fixture", "schema_version": "v38.breadth.1", "calculation_version": "fixture", "breadth50": b50, "breadth200": 70.0}


def nq_fixture(state="Blue"):
    return {"session_date": SESSION, "generated_at": GENERATED, "coverage": 1.0, "source": "fixture", "schema_version": "v38.nqsar.1", "calculation_version": "fixture", "state": state}


def classes_fixture(include_all=True):
    rows = [
        {"ticker": "AAA", "structural_clinical_biotech": False},
        {"ticker": "BBB", "structural_clinical_biotech": False},
    ]
    if include_all:
        rows.append({"ticker": "CCC", "structural_clinical_biotech": False})
    return {"session_date": SESSION, "coverage": 1.0, "source": "fixture", "classification_version": "c1", "rows": rows}


def themes_fixture():
    return {"session_date": SESSION, "coverage": 1.0, "source": "fixture", "calculation_version": "loo1", "rows": [
        {"ticker": "AAA", "peer_theme_score": 50},
        {"ticker": "BBB", "peer_theme_score": 100},
        {"ticker": "CCC", "peer_theme_score": 100},
    ]}


def test_market_mode_thresholds_exact():
    assert determine_market_mode("Blue", 60)[0] == "ATTACK"
    assert determine_market_mode("Green", 59.999)[0] == "SELECTIVE"
    assert determine_market_mode("Blue", 50)[0] == "SELECTIVE"
    assert determine_market_mode("Green", 49.999)[0] == "STOP"
    assert determine_market_mode("Yellow", 99)[0] == "STOP"
    assert determine_market_mode("Red", 99)[0] == "DEFENSE"


def test_blue_green_missing_breadth_is_data_required_not_zero():
    mode, slots, reason = determine_market_mode("Blue", None)
    assert (mode, slots, reason) == ("DATA_REQUIRED", 0, "BREADTH50_MISSING")


def test_red_does_not_require_breadth_to_determine_defense():
    assert determine_market_mode("Red", None)[0] == "DEFENSE"


def test_selective_does_not_force_existing_trim_and_caps_new_total_slots_at_4():
    m, core = calculate_market_outputs(rs_fixture(), breadth_fixture(55), nq_fixture("Green"), classifications=classes_fixture(), generated_at=GENERATED)
    assert m["market_mode"] == "SELECTIVE"
    assert m["max_new_total_slots"] == 4
    assert m["rules"]["selective_forced_trim"] is False
    assert core["ranking_status"] == "OK"
    assert [r["ticker"] for r in core["ranking"]] == ["AAA", "BBB"]


def test_eligibility_exact_final_rules_and_rs63_failure():
    _, core = calculate_market_outputs(rs_fixture(), breadth_fixture(55), nq_fixture(), classifications=classes_fixture(), generated_at=GENERATED)
    by = {r["ticker"]: r for r in core["assessed"]}
    assert by["AAA"]["eligibility_status"] == "ELIGIBLE"
    assert by["BBB"]["eligibility_status"] == "ELIGIBLE"
    assert by["CCC"]["eligibility_status"] == "INELIGIBLE"
    assert "RS63_LT_85_OR_MISSING" in by["CCC"]["eligibility_reasons"]


def test_structural_clinical_biotech_is_excluded():
    c = classes_fixture()
    c["rows"][0]["structural_clinical_biotech"] = True
    _, core = calculate_market_outputs(rs_fixture(), breadth_fixture(55), nq_fixture(), classifications=c, generated_at=GENERATED)
    by = {r["ticker"]: r for r in core["assessed"]}
    assert by["AAA"]["eligibility_status"] == "INELIGIBLE"
    assert "STRUCTURAL_CLINICAL_BIOTECH" in by["AAA"]["eligibility_reasons"]


def test_missing_classification_is_data_required_not_assumed_false():
    _, core = calculate_market_outputs(rs_fixture(), breadth_fixture(55), nq_fixture(), classifications=classes_fixture(False), generated_at=GENERATED)
    by = {r["ticker"]: r for r in core["assessed"]}
    assert by["CCC"]["eligibility_status"] == "DATA_REQUIRED"
    assert core["ranking_status"] == "DATA_REQUIRED"


def test_attack_requires_peer_theme_coverage_and_does_not_neutral_fill_missing():
    themes = themes_fixture()
    themes["rows"] = [x for x in themes["rows"] if x["ticker"] != "BBB"]
    _, core = calculate_market_outputs(rs_fixture(), breadth_fixture(65), nq_fixture(), classifications=classes_fixture(), theme_scores=themes, generated_at=GENERATED)
    assert core["market_mode"] == "ATTACK"
    assert core["ranking_status"] == "DATA_REQUIRED"
    assert core["ranking_reason"] == "PEER_THEME_COVERAGE_INCOMPLETE"
    assert core["ranking"] == []


def test_attack_formula_is_70_rs189_30_theme_and_tiebreaks():
    _, core = calculate_market_outputs(rs_fixture(), breadth_fixture(65), nq_fixture(), classifications=classes_fixture(), theme_scores=themes_fixture(), generated_at=GENERATED)
    assert core["ranking_status"] == "OK"
    by = {r["ticker"]: r for r in core["ranking"]}
    assert by["AAA"]["final_score"] == pytest.approx(.7 * 96 + .3 * 50)
    assert by["BBB"]["final_score"] == pytest.approx(.7 * 92 + .3 * 100)
    assert [r["ticker"] for r in core["ranking"]] == ["BBB", "AAA"]


def test_selective_ignores_theme_score_even_if_supplied():
    _, core = calculate_market_outputs(rs_fixture(), breadth_fixture(55), nq_fixture(), classifications=classes_fixture(), theme_scores=themes_fixture(), generated_at=GENERATED)
    by = {r["ticker"]: r for r in core["ranking"]}
    assert by["AAA"]["final_score"] == 96
    assert by["AAA"]["peer_theme_score"] is None


def test_session_mismatch_is_stale_error():
    b = breadth_fixture()
    b["session_date"] = "2026-09-07"
    with pytest.raises(MarketEngineError, match="STALE shard session mismatch"):
        calculate_market_outputs(rs_fixture(), b, nq_fixture(), classifications=classes_fixture(), generated_at=GENERATED)


def test_nqsar_invalid_state_rejected():
    with pytest.raises(MarketEngineError, match="Blue/Green/Yellow/Red"):
        calculate_market_outputs(rs_fixture(), breadth_fixture(), nq_fixture("Purple"), classifications=classes_fixture(), generated_at=GENERATED)


def test_stop_defense_are_not_rank_exit_rules():
    for state, b50, expected in [("Yellow", 80, "STOP"), ("Red", 80, "DEFENSE"), ("Blue", 40, "STOP")]:
        _, core = calculate_market_outputs(rs_fixture(), breadth_fixture(b50), nq_fixture(state), classifications=classes_fixture(), generated_at=GENERATED)
        assert core["market_mode"] == expected
        assert core["rules"]["rank_decline_exit"] is False
        assert core["rules"]["theme_decline_exit"] is False
