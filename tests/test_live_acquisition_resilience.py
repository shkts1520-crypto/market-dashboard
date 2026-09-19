from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import v38.live_acquisition as live


TARGET = "2026-09-18"


def _raw(symbols: list[str], *, include_target: bool = True) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    dates = ["2026-09-17", TARGET] if include_target else ["2026-09-17"]
    index = pd.to_datetime(dates)
    frames = {}
    for i, symbol in enumerate(symbols, start=1):
        base = 100.0 + i
        frames[symbol] = pd.DataFrame(
            {
                "Open": [base] * len(index),
                "High": [base + 2.0] * len(index),
                "Low": [base - 2.0] * len(index),
                "Close": [base + 1.0] * len(index),
                "Adj Close": [base + 1.0] * len(index),
                "Volume": [1_000_000.0] * len(index),
            },
            index=index,
        )
    return pd.concat(frames, axis=1)


class _NoTickerFallback:
    class _Ticker:
        def history(self, **kwargs):
            return pd.DataFrame()

    def Ticker(self, symbol: str):
        return self._Ticker()


def test_adaptive_retry_recovers_only_missing_tickers_in_smaller_batches(tmp_path, monkeypatch):
    calls: list[tuple[int, int | bool]] = []

    def fake_download(yf, symbols, *, period, threads):
        calls.append((len(symbols), threads))
        # Simulate a rate-limited wide request: half of the names arrive.
        if len(symbols) > 10:
            return _raw(symbols[: len(symbols) // 2])
        # Smaller retry requests succeed.
        return _raw(symbols)

    monkeypatch.setattr(live, "_download", fake_download)
    monkeypatch.setattr(live.time, "sleep", lambda _: None)

    out = tmp_path / "ohlcv.csv"
    stats = live.download_stock_ohlcv(
        _NoTickerFallback(),
        [f"T{i:02d}" for i in range(20)],
        target_session=TARGET,
        output_path=out,
        chunk_size=20,
    )

    assert stats["target_session_coverage"] == 1.0
    assert stats["failed_tickers"] == []
    assert calls[0] == (20, 4)
    assert any(size == 10 and threads == 2 for size, threads in calls)
    assert stats["adaptive_retry_rounds"][0]["recovered"] == 10

    frame = pd.read_csv(out)
    target = frame[frame["date"].astype(str) == TARGET]
    assert target["ticker"].nunique() == 20
    assert not frame.duplicated(["ticker", "date"]).any()


def test_stale_history_is_never_relabelled_as_target_session(tmp_path, monkeypatch):
    def fake_download(yf, symbols, *, period, threads):
        return _raw(symbols, include_target=False)

    monkeypatch.setattr(live, "_download", fake_download)
    monkeypatch.setattr(live.time, "sleep", lambda _: None)

    with pytest.raises(live.LiveAcquisitionError, match="after adaptive retries"):
        live.download_stock_ohlcv(
            _NoTickerFallback(),
            ["AAA", "BBB", "CCC", "DDD"],
            target_session=TARGET,
            output_path=tmp_path / "ohlcv.csv",
            chunk_size=4,
        )


def test_total_yahoo_outage_still_fails_closed_after_retries(tmp_path, monkeypatch):
    calls = 0

    def fake_download(yf, symbols, *, period, threads):
        nonlocal calls
        calls += 1
        return pd.DataFrame()

    monkeypatch.setattr(live, "_download", fake_download)
    monkeypatch.setattr(live.time, "sleep", lambda _: None)

    with pytest.raises(live.LiveAcquisitionError, match=r"0/5=0\.000"):
        live.download_stock_ohlcv(
            _NoTickerFallback(),
            ["AAA", "BBB", "CCC", "DDD", "EEE"],
            target_session=TARGET,
            output_path=tmp_path / "ohlcv.csv",
            chunk_size=5,
        )

    assert calls >= 4
