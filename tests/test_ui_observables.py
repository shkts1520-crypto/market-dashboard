from __future__ import annotations

import json

from v38.mc57_engine import MC57_METRICS
from v38.ui_observables import augment_view_model


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_augments_mc57_internal_history_and_nqsar(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    _write(data / "mc57.json", {
        "session_date": "2026-09-11",
        "status": "READY",
        "calculation_version": "v38-mc57-live-1.1.0",
        "mc57": 33.5,
        "raw": 48.5,
        "ema2_raw": 49.5,
        "z": -0.62,
        "mu_prior": 61.4,
        "sigma_prior": 19.1,
        "metric_scores": {metric: 50.0 for metric in MC57_METRICS},
        "history": [
            {
                "date": "2026-09-10", "mc57": 36.0, "raw": 47.3, "ema2_raw": 51.4, "z": -0.52,
                **{metric: 45.0 for metric in MC57_METRICS},
            },
            {
                "date": "2026-09-11", "mc57": 33.5, "raw": 48.5, "ema2_raw": 49.5, "z": -0.62,
                **{metric: 50.0 for metric in MC57_METRICS},
            },
        ],
    })
    _write(data / "nqsar.json", {
        "session_date": "2026-09-11",
        "status": "READY",
        "input_kind": "RECOVERED_YAHOO_FSM_ESTIMATE",
        "authoritative_exact": False,
        "history": [{"date": "2026-09-11", "state": "Green"}],
    })
    _write(data / "analytics.json", {
        "session_date": "2026-09-11",
        "status": "READY",
        "source": "test",
        "market_diagnostics": {"x": 1},
    })
    view_path = tmp_path / "view.json"
    _write(view_path, {
        "session_date": "2026-09-11",
        "daily": {"history": [{"date": "2026-09-10"}, {"date": "2026-09-11"}]},
    })

    out = augment_view_model(data, view_path)
    detail = out["daily"]["mc57_detail"]
    assert detail["status"] == "READY"
    assert detail["history_sessions"] == 2
    assert detail["fixed57_breadth"]["sma50"] == 50.0
    assert len(detail["series"]["fixed57_breadth_sma200"]) == 2
    assert len(detail["metrics"]) == 12
    assert out["daily"]["pit_breadth_history_sessions"] == 2
    assert out["daily"]["nqsar_input_kind"] == "RECOVERED_YAHOO_FSM_ESTIMATE"
    assert out["daily"]["nqsar_authoritative_exact"] is False
