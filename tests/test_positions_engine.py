import pytest
from v38.positions_engine import normal_stock_next_open_action, stop_levels, PositionsRuleError

def test_stop_levels_match_92_and_70_rules():
    x=stop_levels(entry=100,peak_close=150)
    assert x["initial_stop"]==92 and x["winner_trail"]==105 and x["final_stop"]==105

def test_initial_stop_boundary_exits_next_open():
    x=normal_stock_next_open_action(entry=100,close=92,peak_close=110,partial_taken=False,nqsar_state="Green")
    assert x["action"]=="EXIT_ALL_NEXT_OPEN"

def test_partial_profit_boundary_sells_25_percent_once():
    x=normal_stock_next_open_action(entry=100,close=124,peak_close=124,partial_taken=False,nqsar_state="Blue")
    assert x["action"]=="SELL_25_PCT_NEXT_OPEN" and x["sell_fraction"]==0.25

def test_winner_trail_after_partial_exits_remainder():
    x=normal_stock_next_open_action(entry=100,close=105,peak_close=150,partial_taken=True,nqsar_state="Green")
    assert x["action"]=="EXIT_REMAINDER_NEXT_OPEN"

def test_red_has_portfolio_exit_priority():
    x=normal_stock_next_open_action(entry=100,close=130,peak_close=130,partial_taken=False,nqsar_state="Red")
    assert x["reason"]=="NQSAR_RED_PORTFOLIO_EXIT"

@pytest.mark.parametrize("state",["Yellow","Blue","Green"])
def test_non_red_state_does_not_force_exit_when_no_price_rule_hit(state):
    x=normal_stock_next_open_action(entry=100,close=110,peak_close=110,partial_taken=False,nqsar_state=state)
    assert x["action"]=="HOLD"

def test_invalid_peak_fails():
    with pytest.raises(PositionsRuleError): normal_stock_next_open_action(entry=100,close=110,peak_close=109,partial_taken=False,nqsar_state="Green")
