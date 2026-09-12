from v38.tqqq_state import build_tqqq_panic_state


def _daily(session: str, *, seed: bool):
    rows = []
    for i in range(60):
        day = f"2026-07-{(i % 28) + 1:02d}" if i < 40 else f"2026-08-{(i - 39):02d}"
        close = 100.0
        rows.append({"date": day, "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000})
    # Ensure unique, monotone dates are not required by the calculator; only order is.
    rows = [{**row, "date": f"2026-06-{i + 1:02d}"} for i, row in enumerate(rows[:20])]
    rows += [{"date": f"2026-07-{i + 1:02d}", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000} for i in range(20)]
    rows += [{"date": f"2026-08-{i + 1:02d}", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000} for i in range(19)]
    rows.append({"date": session, "open": 96 if seed else 100, "high": 97 if seed else 101, "low": 94 if seed else 99, "close": 95 if seed else 100, "volume": 1_000_000})
    return rows


def _market(session: str, *, seed: bool, prior_rsi=31.0, current_rsi=29.0):
    return {
        "session_date": session,
        "series": {
            "QQQ": _daily(session, seed=seed),
            "^VIX": [{"date": session, "close": 25.0 if seed else 18.0}],
        },
        "qqq_4h_status": "READY",
        "qqq_4h_trading_gate_eligible": True,
        "qqq_4h_latest": {
            "prior_rsi14": prior_rsi,
            "current_rsi14": current_rsi,
            "touch30": prior_rsi > 30 >= current_rsi,
        },
    }


def test_seed_touch_creates_next_open_raise_signal():
    session = "2026-09-11"
    out = build_tqqq_panic_state(
        market_inputs=_market(session, seed=True),
        mc57={"session_date": session, "mc57": 25.0},
        prior_state=None,
        session_date=session,
        generated_at="2026-09-12T00:00:00Z",
    )
    assert out["seed_inputs"]["condition"] is True
    assert out["trigger"]["trigger"] is True
    assert out["action_next_open"] == "RAISE_TO_80_NEXT_OPEN"
    assert out["target_pct_next_open"] == 80
    assert out["panic_active"] is False


def test_pending_entry_rolls_to_active_panic_next_session_and_mc57_exit_works():
    prior_session = "2026-09-10"
    prior = build_tqqq_panic_state(
        market_inputs=_market(prior_session, seed=True),
        mc57={"session_date": prior_session, "mc57": 25.0},
        prior_state=None,
        session_date=prior_session,
        generated_at="2026-09-11T00:00:00Z",
    )
    session = "2026-09-11"
    market = _market(session, seed=False, prior_rsi=35.0, current_rsi=40.0)
    hold = build_tqqq_panic_state(
        market_inputs=market,
        mc57={"session_date": session, "mc57": 25.0},
        prior_state=prior,
        session_date=session,
        generated_at="2026-09-12T00:00:00Z",
    )
    assert hold["panic_active"] is True
    assert hold["holding_sessions_completed"] == 1
    assert hold["action_next_open"] == "HOLD_80"

    exit_state = build_tqqq_panic_state(
        market_inputs=market,
        mc57={"session_date": session, "mc57": 19.9},
        prior_state=prior,
        session_date=session,
        generated_at="2026-09-12T00:00:00Z",
    )
    assert exit_state["panic_active"] is True
    assert exit_state["action_next_open"] == "RETURN_TO_30_NEXT_OPEN"
    assert exit_state["target_pct_next_open"] == 30
