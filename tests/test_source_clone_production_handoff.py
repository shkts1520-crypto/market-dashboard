from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_source_clone_from_production.py"
SPEC = importlib.util.spec_from_file_location("prepare_source_clone_from_production", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _fixture(tmp_path: Path, *, handoff_session: str = "2026-09-18") -> tuple[Path, Path]:
    data = tmp_path / "data"
    handoff = tmp_path / "handoff"
    data.mkdir()
    handoff.mkdir()

    _write_json(data / "state.json", {
        "session_date": "2026-09-18",
        "coverage": 1.0,
    })
    _write_json(data / "rs.json", {
        "session_date": "2026-09-18",
        "coverage": 1.0,
        "coverage_detail": {
            "active_universe": 2,
            "current_valid_ohlcv": 2,
        },
    })
    _write_json(data / "mc57.json", {
        "session_date": "2026-09-18",
        "status": "READY",
        "coverage": 1.0,
    })
    _write_json(handoff / "handoff.json", {
        "session_date": handoff_session,
        "active_universe": 2,
        "current_valid_ohlcv": 2,
    })

    with (handoff / "universe.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "session_date"])
        writer.writeheader()
        writer.writerow({"ticker": "AAA", "session_date": "2026-09-18"})
        writer.writerow({"ticker": "BBB", "session_date": "2026-09-18"})

    with (handoff / "ohlcv.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "date", "close"])
        writer.writeheader()
        writer.writerow({"ticker": "AAA", "date": "2026-09-18", "close": 10})
        writer.writerow({"ticker": "BBB", "date": "2026-09-18", "close": 20})

    return data, handoff


def test_valid_production_handoff_is_accepted(tmp_path):
    data, handoff = _fixture(tmp_path)
    audit = module.validate_production_handoff(data, handoff)
    assert audit == {
        "session_date": "2026-09-18",
        "active_universe": 2,
        "current_valid_ohlcv": 2,
        "stock_coverage": 1.0,
        "raw_coverage": 1.0,
    }


def test_session_mismatch_is_rejected(tmp_path):
    data, handoff = _fixture(tmp_path, handoff_session="2026-09-17")
    with pytest.raises(module.ProductionHandoffError, match="handoff session mismatch"):
        module.validate_production_handoff(data, handoff)


def test_workflows_publish_and_reuse_raw_handoff():
    root = Path(__file__).resolve().parents[1]
    production = (root / ".github/workflows/production.yml").read_text(encoding="utf-8")
    clone = (root / ".github/workflows/source-mc57-clone.yml").read_text(encoding="utf-8")

    assert "Upload Production raw acquisition handoff" in production
    assert "v38-production-live-handoff" in production
    assert "Recover Production raw acquisition handoff" in clone
    assert "prepare_source_clone_from_production.py" in clone
    assert "full-universe Yahoo re-download skipped" in clone
