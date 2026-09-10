from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from v38.calculate_pipeline import OUTPUT_NAMES, calculate_pipeline, validate_staged_outputs
from v38.market_engine import MarketEngineError

SESSION = "2026-09-08"
GENERATED = "2026-09-09T05:00:00+09:00"


def write_inputs(tmp_path: Path, *, nqsar_session=SESSION):
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    dates = pd.bdate_range(end=SESSION, periods=260)
    rows = []
    for i, t in enumerate(tickers):
        for j, dt in enumerate(dates):
            close = 30 + i * 5 + (i + 1) * j * 0.10
            rows.append({
                "ticker": t,
                "date": dt.strftime("%Y-%m-%d"),
                "open": close * 0.995,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 2_000_000,
                "is_complete": True,
                "split_checked": True,
                "split_anomaly": False,
            })
    ohlcv = tmp_path / "ohlcv.csv"
    universe = tmp_path / "universe.csv"
    nqsar = tmp_path / "nqsar.json"
    pd.DataFrame(rows).to_csv(ohlcv, index=False)
    pd.DataFrame({"ticker": tickers, "session_date": SESSION, "in_universe": True}).to_csv(universe, index=False)
    nqsar.write_text(json.dumps({
        "session_date": nqsar_session,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "v38.nqsar.1",
        "calculation_version": "fixture",
        "state": "Green",
    }), encoding="utf-8")
    return ohlcv, universe, nqsar


def test_pipeline_calculates_validates_then_publishes_five_current_shards(tmp_path: Path):
    ohlcv, universe, nqsar = write_inputs(tmp_path)
    out = tmp_path / "data"
    paths = calculate_pipeline(
        ohlcv_path=ohlcv,
        universe_path=universe,
        nqsar_path=nqsar,
        output_dir=out,
        session_date=SESSION,
        generated_at=GENERATED,
        stock_source="fixture",
    )
    assert tuple(p.name for p in paths) == OUTPUT_NAMES
    for p in paths:
        obj = json.loads(p.read_text())
        assert obj["session_date"] == SESSION
        assert obj["generated_at"] == GENERATED
        assert obj["source"]
        assert obj["schema_version"]
        assert obj["calculation_version"]
    # Missing PIT old Top24 is disclosed; it is not fabricated.
    assert json.loads((out / "f123.json").read_text())["f1"]["status"] == "DATA_REQUIRED"
    # Missing structural-biotech/theme dependencies prevent an actionable Attack ranking.
    assert json.loads((out / "core12.json").read_text())["ranking_status"] == "DATA_REQUIRED"


def test_pipeline_does_not_publish_staged_files_when_nqsar_session_is_stale(tmp_path: Path):
    ohlcv, universe, nqsar = write_inputs(tmp_path, nqsar_session="2026-09-07")
    out = tmp_path / "data"
    out.mkdir()
    sentinel = out / "rs.json"
    sentinel.write_text("SENTINEL", encoding="utf-8")
    with pytest.raises(MarketEngineError, match="STALE shard session mismatch"):
        calculate_pipeline(
            ohlcv_path=ohlcv,
            universe_path=universe,
            nqsar_path=nqsar,
            output_dir=out,
            session_date=SESSION,
            generated_at=GENERATED,
            stock_source="fixture",
        )
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL"
    assert not (out / "breadth.json").exists()


def test_staged_validator_rejects_missing_common_contract_field(tmp_path: Path):
    for name in OUTPUT_NAMES:
        (tmp_path / name).write_text(json.dumps({
            "session_date": SESSION,
            "generated_at": GENERATED,
            "coverage": 1.0,
            "source": "fixture",
            "schema_version": "x",
            "calculation_version": "x",
        }), encoding="utf-8")
    obj = json.loads((tmp_path / "core12.json").read_text())
    obj.pop("source")
    (tmp_path / "core12.json").write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(Exception, match="missing metadata: source"):
        validate_staged_outputs(tmp_path, session_date=SESSION, generated_at=GENERATED)


def test_pipeline_is_deterministic_for_fixed_inputs(tmp_path: Path):
    ohlcv, universe, nqsar = write_inputs(tmp_path)
    out1 = tmp_path / "data1"
    out2 = tmp_path / "data2"
    kwargs = dict(
        ohlcv_path=ohlcv,
        universe_path=universe,
        nqsar_path=nqsar,
        session_date=SESSION,
        generated_at=GENERATED,
        stock_source="fixture",
    )
    calculate_pipeline(output_dir=out1, **kwargs)
    calculate_pipeline(output_dir=out2, **kwargs)
    for name in OUTPUT_NAMES:
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()
