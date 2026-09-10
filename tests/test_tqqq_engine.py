import pytest
from v38.tqqq_engine import panic_seed, panic_trigger, panic_position_action, TQQQRuleError


def test_seed_requires_all_three_conditions():
    assert panic_seed(vix_close=23,qqq_sma50_atr_deviation=-0.5,qqq_dd10=-0.02)
    assert not panic_seed(vix_close=22.99,qqq_sma50_atr_deviation=-0.5,qqq_dd10=-0.02)
    assert not panic_seed(vix_close=23,qqq_sma50_atr_deviation=-0.49,qqq_dd10=-0.02)
    assert not panic_seed(vix_close=23,qqq_sma50_atr_deviation=-0.5,qqq_dd10=-0.019)


def test_trigger_boundary_requires_seed_age30_rsi30_and_mc57_ge20():
    x=panic_trigger(seed_age_sessions=30,qqq_4h_rsi14=30,mc57=20)
    assert x["trigger"] is True and x["status"]=="OK"
    assert panic_trigger(seed_age_sessions=31,qqq_4h_rsi14=30,mc57=30)["trigger"] is False
    assert panic_trigger(seed_age_sessions=30,qqq_4h_rsi14=30.01,mc57=30)["trigger"] is False
    assert panic_trigger(seed_age_sessions=30,qqq_4h_rsi14=30,mc57=19.99)["trigger"] is False


def test_trigger_needs_mc57_only_after_seed_and_rsi_conditions_are_met():
    assert panic_trigger(seed_age_sessions=None,qqq_4h_rsi14=20,mc57=None)["status"]=="OK"
    assert panic_trigger(seed_age_sessions=31,qqq_4h_rsi14=20,mc57=None)["status"]=="OK"
    x=panic_trigger(seed_age_sessions=10,qqq_4h_rsi14=29,mc57=None)
    assert x["status"]=="DATA_REQUIRED" and x["trigger"] is None


def test_confirmed_trigger_raises_tqqq_from_baseline_to_80_next_open():
    x=panic_position_action(in_panic=False,holding_sessions_completed=0,trigger=True,mc57=25)
    assert x["action"]=="RAISE_TO_80_NEXT_OPEN" and x["target_pct"]==80


def test_no_trigger_keeps_baseline_30():
    x=panic_position_action(in_panic=False,holding_sessions_completed=0,trigger=False,mc57=None)
    assert x["target_pct"]==30


def test_active_panic_holds_80_when_mc57_ge20_before_day10():
    x=panic_position_action(in_panic=True,holding_sessions_completed=9,trigger=False,mc57=20)
    assert x["action"]=="HOLD_80"


def test_mc57_lt20_exits_panic_to_30_next_open():
    x=panic_position_action(in_panic=True,holding_sessions_completed=5,trigger=False,mc57=19.9)
    assert x["action"]=="RETURN_TO_30_NEXT_OPEN" and x["reason"]=="MC57_LT_20"


def test_active_panic_without_mc57_fails_closed():
    x=panic_position_action(in_panic=True,holding_sessions_completed=5,trigger=False,mc57=None)
    assert x["status"]=="DATA_REQUIRED" and x["action"] is None


def test_day10_returns_to_30_even_if_mc57_missing():
    x=panic_position_action(in_panic=True,holding_sessions_completed=10,trigger=False,mc57=None)
    assert x["action"]=="RETURN_TO_30_NEXT_OPEN" and x["target_pct"]==30


def test_unresolved_trigger_does_not_guess_entry():
    x=panic_position_action(in_panic=False,holding_sessions_completed=0,trigger=None,mc57=None)
    assert x["status"]=="DATA_REQUIRED" and x["action"] is None


def test_bad_seed_age_fails():
    with pytest.raises(TQQQRuleError): panic_trigger(seed_age_sessions=-1,qqq_4h_rsi14=20,mc57=25)
