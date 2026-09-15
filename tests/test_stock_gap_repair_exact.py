from __future__ import annotations

import pandas as pd

import v38.stock_gap_repair_exact as exact


def test_existing_history_rows_keeps_only_valid_observed_rows(tmp_path):
    path = tmp_path / "ohlcv.csv"
    pd.DataFrame([
        {"ticker": "AAA", "date": "2026-09-11", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1000, "is_complete": True, "split_checked": True, "split_anomaly": False},
        {"ticker": "AAA", "date": "2026-09-12", "open": None, "high": None, "low": None, "close": None, "volume": 1000, "is_complete": True, "split_checked": True, "split_anomaly": False},
        {"ticker": "BBB", "date": "2026-09-11", "open": 20, "high": 21, "low": 19, "close": 20.5, "volume": 2000, "is_complete": True, "split_checked": True, "split_anomaly": False},
    ]).to_csv(path, index=False)

    rows = exact._existing_history_rows(path, "AAA")
    assert [row["date"] for row in rows] == ["2026-09-11"]
    assert rows[0]["close"] == 10.5


def test_wrapper_runs_exact_nasdaq_only_for_remaining(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(
        exact.base,
        "repair_failed_live_tickers",
        lambda *args, **kwargs: {"status": "PARTIAL", "repaired": ["DONE"], "remaining": ["AAA", "BBB"]},
    )

    def fake_second(*args, **kwargs):
        calls.append(kwargs["remaining"])
        return {"status": "PARTIAL", "repaired": ["AAA"], "remaining": ["BBB"]}

    monkeypatch.setattr(exact, "_repair_remaining_with_exact_nasdaq", fake_second)
    result = exact.repair_failed_live_tickers(tmp_path, tmp_path, generated_at="2026-09-15T00:00:00Z")

    assert calls == [["AAA", "BBB"]]
    assert result == {"status": "PARTIAL", "repaired": ["AAA", "DONE"], "remaining": ["BBB"]}


def test_exact_repair_requires_exact_date_observation(monkeypatch, tmp_path):
    data = tmp_path / "data"
    work = tmp_path / "work"
    data.mkdir(); work.mkdir()
    (work / "universe.csv").write_text("ticker\nAAA\n", encoding="utf-8")
    pd.DataFrame([
        {"ticker": "AAA", "date": "2026-09-11", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1000, "is_complete": True, "split_checked": True, "split_anomaly": False},
    ]).to_csv(work / "ohlcv.csv", index=False)
    (data / "state.json").write_text('{"session_date":"2026-09-14","coverage":0.9}', encoding="utf-8")
    (data / "acquisition_manifest.json").write_text('{"session_date":"2026-09-14","yahoo":{"failed_tickers":["AAA"],"requested":1,"target_session_received":0,"history_received":1}}', encoding="utf-8")

    monkeypatch.setattr(exact.base, "_nasdaq_historical_current_bar", lambda **kwargs: None)
    result = exact._repair_remaining_with_exact_nasdaq(
        data,
        work,
        generated_at="2026-09-15T00:00:00Z",
        remaining=["AAA"],
    )
    assert result == {"status": "UNRESOLVED", "repaired": [], "remaining": ["AAA"]}
