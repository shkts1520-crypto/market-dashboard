from __future__ import annotations

import json

from v38.ui_polish import attach_reconstructed_stock_ui


def _metric(key, value=None, status="DATA_REQUIRED"):
    return {
        "key": key,
        "label": key,
        "value": value,
        "display": "—" if value is None else str(value),
        "status": status,
        "reason": "TEST",
    }


def _base_view(session="2026-09-11"):
    required = [
        "market_mode", "nqsar", "breadth50", "breadth200", "mc57",
        "f1", "f2", "f3", "market_QQQ", "market_TQQQ", "market_^VIX",
        "market_NQ=F", "market_SPY",
    ]
    metrics = [_metric(key, 1.0, "READY") for key in required]
    for row in metrics:
        if row["key"] == "f1":
            row.update(value=None, display="—", status="DATA_REQUIRED")
    return {
        "session_date": session,
        "daily": {
            "status": "DATA_REQUIRED",
            "metrics": metrics,
            "history": [
                {
                    "date": session,
                    "breadth50": 60.0,
                    "breadth200": 59.0,
                    "f1": None,
                    "f2": 0.20,
                    "f3": 0.30,
                    "full_v38_ready": False,
                }
            ],
        },
    }


def _write_reconstruction(root, session="2026-09-11"):
    path = root / "history" / "reconstructed_stock_metrics.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "session_date": session,
                "status": "READY",
                "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED",
                "session_count": 126,
                "first_session": "2026-03-13",
                "latest_session": session,
                "current_universe_count": 3390,
                "survivorship_warning": True,
                "trading_gate_eligible": False,
                "source": "TEST_RECON",
                "rows": [
                    {
                        "date": session,
                        "breadth50": 61.0,
                        "breadth200": 60.0,
                        "f1": {
                            "value": 0.25,
                            "status": "FULL",
                            "coverage": 1.0,
                            "old_top24_count": 24,
                            "observable_count": 24,
                            "drop_count": 6,
                        },
                        "f2": {"value": 0.20, "status": "OK"},
                        "f3": {"value": 0.30, "status": "OK"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_reconstructed_f1_fills_display_only_and_does_not_erase_observed_breadth(tmp_path):
    session = "2026-09-11"
    _write_reconstruction(tmp_path, session)
    (tmp_path / "f123.json").write_text(
        json.dumps(
            {
                "session_date": session,
                "f1": {"value": None, "status": "DATA_REQUIRED"},
                "f2": {"value": 0.20, "status": "OK", "weak_count": 2, "weak": ["A", "B"]},
                "f3": {"value": 0.30, "status": "OK", "break_count": 3, "broken": ["C"]},
            }
        ),
        encoding="utf-8",
    )
    view = _base_view(session)

    out = attach_reconstructed_stock_ui(view, tmp_path)
    daily = out["daily"]
    f1 = next(row for row in daily["metrics"] if row["key"] == "f1")
    assert f1["status"] == "READY"
    assert f1["value"] == 0.25
    assert f1["display"] == "25.0%"
    assert f1["display_provenance"] == "CURRENT_UNIVERSE_RECONSTRUCTED_DISPLAY_ONLY"
    assert f1["trading_gate_eligible"] is False
    assert daily["f123_detail"]["f1"]["trading_gate_eligible"] is False
    assert daily["f123_detail"]["f2"]["weak"] == ["A", "B"]
    assert daily["f123_detail"]["f3"]["broken"] == ["C"]
    # Exact observed breadth remains authoritative; only its missing F1 gap is filled.
    assert daily["history"][-1]["breadth50"] == 60.0
    assert daily["history"][-1]["breadth200"] == 59.0
    assert daily["history"][-1]["f1"] == 0.25
    assert daily["history"][-1]["history_kind"] == "OBSERVED_SESSION_WITH_RECONSTRUCTED_GAPS"
    assert daily["status"] == "READY"


def test_exact_f1_wins_over_reconstructed_display_value(tmp_path):
    session = "2026-09-11"
    _write_reconstruction(tmp_path, session)
    (tmp_path / "f123.json").write_text(
        json.dumps(
            {
                "session_date": session,
                "f1": {"value": 0.125, "status": "FULL", "dropped": ["X"]},
                "f2": {"value": 0.20, "status": "OK"},
                "f3": {"value": 0.30, "status": "OK"},
            }
        ),
        encoding="utf-8",
    )
    out = attach_reconstructed_stock_ui(_base_view(session), tmp_path)
    detail = out["daily"]["f123_detail"]["f1"]
    metric = next(row for row in out["daily"]["metrics"] if row["key"] == "f1")
    assert detail["value"] == 0.125
    assert detail["display_provenance"] == "CURRENT_SESSION_EXACT"
    assert metric["value"] == 0.125
    assert metric["display"] == "12.5%"
