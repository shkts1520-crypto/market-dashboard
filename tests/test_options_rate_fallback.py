from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "calculate_options_live.py"
spec = importlib.util.spec_from_file_location("calculate_options_live", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_yahoo_irx_frame_records_rate_and_observation_date():
    frame = pd.DataFrame(
        {"Close": [3.95, 4.00]},
        index=pd.to_datetime(["2026-09-09", "2026-09-10"]),
    )
    rate, observed = module._rate_from_yahoo_frame(frame, session_date="2026-09-11")
    assert rate == 0.04
    assert observed == "2026-09-10"


def test_previous_measured_rate_is_allowed_only_when_recent():
    previous = {
        "risk_free_rate": 0.04,
        "risk_free_rate_source": "FRED:DGS3MO",
        "risk_free_rate_observed_date": "2026-09-10",
    }
    rate, observed, source = module._previous_risk_free_rate(previous, "2026-09-11")
    assert rate == 0.04
    assert observed == "2026-09-10"
    assert source == "CACHED:FRED:DGS3MO"


def test_previous_measured_rate_rejects_stale_values():
    previous = {
        "risk_free_rate": 0.04,
        "risk_free_rate_source": "FRED:DGS3MO",
        "risk_free_rate_observed_date": "2026-08-01",
    }
    try:
        module._previous_risk_free_rate(previous, "2026-09-11")
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale measured rate must not be reused")


def test_risk_free_resolver_uses_fred_when_both_yahoo_paths_fail(monkeypatch):
    class FakeTicker:
        def history(self, **kwargs):
            raise RuntimeError("history unavailable")

    class FakeYf:
        def download(self, *args, **kwargs):
            raise RuntimeError("download unavailable")

        def Ticker(self, symbol):
            assert symbol == "^IRX"
            return FakeTicker()

    monkeypatch.setattr(module, "_fred_risk_free_rate", lambda session: (0.04, "2026-09-10"))
    rate, source, observed = module._risk_free_rate(
        FakeYf(), session_date="2026-09-11", previous={}
    )
    assert rate == 0.04
    assert source == "FRED:DGS3MO"
    assert observed == "2026-09-10"
