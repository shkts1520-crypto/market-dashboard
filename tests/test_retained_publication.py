from __future__ import annotations

import json
from pathlib import Path

import pytest

from v38.retained_publication import RetainedPublicationError, validate_retained_publication


SESSION = "2026-09-11"
GENERATED = "2026-09-11T22:29:06Z"


def _meta(schema: str, calculation: str) -> dict:
    return {
        "session_date": SESSION,
        "generated_at": GENERATED,
        "source": "test",
        "schema_version": schema,
        "calculation_version": calculation,
    }


def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _fixture(root: Path) -> None:
    active = 10
    valid = 9
    coverage = valid / active
    _write(
        root / "state.json",
        {**_meta("v38.state.1", "test"), "status": "READY", "coverage": coverage},
    )
    _write(
        root / "rs.json",
        {
            **_meta("v38.rs.1", "test"),
            "coverage": coverage,
            "coverage_detail": {
                "active_universe": active,
                "current_valid_ohlcv": valid,
            },
            "rows": [{"ticker": f"T{i}"} for i in range(valid)],
        },
    )
    _write(
        root / "breadth.json",
        {
            **_meta("v38.breadth.1", "test"),
            "coverage": coverage,
            "coverage_detail": {
                "active_universe": active,
                "current_valid_ohlcv": valid,
            },
        },
    )
    _write(
        root / "acquisition_manifest.json",
        {
            **_meta("v38.acquisition.1", "test"),
            "status": "READY",
            "coverage": coverage,
            "yahoo": {
                "requested": active,
                "target_session_received": valid,
                "target_session_coverage": coverage,
            },
        },
    )
    symbols = ("QQQ", "TQQQ", "^VIX", "NQ=F", "SPY")
    _write(
        root / "market_inputs.json",
        {
            **_meta("v38.market_inputs.1", "test"),
            "coverage": 1.0,
            "required_coverage": 1.0,
            "required_symbols": list(symbols),
            "series": {
                symbol: [{"date": SESSION, "close": 100.0 + i}]
                for i, symbol in enumerate(symbols)
            },
        },
    )


def test_valid_retained_publication_is_accepted(tmp_path: Path) -> None:
    _fixture(tmp_path)
    result = validate_retained_publication(tmp_path, session_date=SESSION)
    assert result["active_universe"] == 10
    assert result["current_valid_ohlcv"] == 9
    assert result["stock_coverage"] == pytest.approx(0.9)
    assert result["required_market_coverage"] == 1.0


def test_retained_publication_rejects_low_actual_stock_coverage(tmp_path: Path) -> None:
    _fixture(tmp_path)
    rs = json.loads((tmp_path / "rs.json").read_text(encoding="utf-8"))
    rs["coverage"] = 0.7
    rs["coverage_detail"]["current_valid_ohlcv"] = 7
    rs["rows"] = rs["rows"][:7]
    _write(tmp_path / "rs.json", rs)
    with pytest.raises(RetainedPublicationError):
        validate_retained_publication(tmp_path, session_date=SESSION)


def test_retained_publication_rejects_missing_required_market_session(tmp_path: Path) -> None:
    _fixture(tmp_path)
    market = json.loads((tmp_path / "market_inputs.json").read_text(encoding="utf-8"))
    market["series"]["QQQ"][-1]["date"] = "2026-09-10"
    _write(tmp_path / "market_inputs.json", market)
    with pytest.raises(RetainedPublicationError, match="QQQ"):
        validate_retained_publication(tmp_path, session_date=SESSION)
