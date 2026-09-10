import pytest
from v38.panic_reset_engine import activation, entry_signal, admission, holding_action, PanicResetRuleError

def test_activation_boundaries():
    assert activation(theme_rs_pct=80,rank_improvement_20d=15,theme_above_ema21_pct=60)
    assert not activation(theme_rs_pct=79.9,rank_improvement_20d=15,theme_above_ema21_pct=60)
    assert not activation(theme_rs_pct=80,rank_improvement_20d=14.9,theme_above_ema21_pct=60)
    assert not activation(theme_rs_pct=80,rank_improvement_20d=15,theme_above_ema21_pct=59.9)

def test_entry_signal_requires_top3_and_first_rsi_up_after_touch():
    assert entry_signal(activation_ok=True,rsi30_touched_within_20=True,first_rsi_up_day_after_touch=True,theme_rs63_rank=3)
    assert not entry_signal(activation_ok=True,rsi30_touched_within_20=True,first_rsi_up_day_after_touch=True,theme_rs63_rank=4)
    assert not entry_signal(activation_ok=True,rsi30_touched_within_20=True,first_rsi_up_day_after_touch=False,theme_rs63_rank=1)

def test_admission_uses_2_9_pct_and_caps():
    x=admission(signal=True,current_total_slots=3,current_same_theme_slots=1,sessions_since_exit=20)
    assert x["admit"] is True and x["position_pct"]==2.9
    assert admission(signal=True,current_total_slots=4,current_same_theme_slots=0,sessions_since_exit=None)["reason"]=="TOTAL_SLOT_CAP"
    assert admission(signal=True,current_total_slots=0,current_same_theme_slots=2,sessions_since_exit=None)["reason"]=="SAME_THEME_SLOT_CAP"

def test_cooldown_boundary_is_20_sessions():
    assert admission(signal=True,current_total_slots=0,current_same_theme_slots=0,sessions_since_exit=19)["admit"] is False
    assert admission(signal=True,current_total_slots=0,current_same_theme_slots=0,sessions_since_exit=20)["admit"] is True

def test_fixed_hold_has_no_initial_stop_or_averaging():
    x=holding_action(holding_sessions_completed=19)
    assert x["action"]=="HOLD" and x["initial_stop_enabled"] is False and x["averaging_enabled"] is False

def test_exit_after_20_completed_holding_sessions():
    assert holding_action(holding_sessions_completed=20)["action"]=="EXIT_NEXT_OPEN"

def test_invalid_counts_fail():
    with pytest.raises(PanicResetRuleError): admission(signal=True,current_total_slots=-1,current_same_theme_slots=0,sessions_since_exit=None)
