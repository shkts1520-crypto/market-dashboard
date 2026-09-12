from __future__ import annotations

import json
from pathlib import Path

import pytest

import v38.recovered_theme as rt


def _rows():
    return {
        "rows": [
            {"ticker": "AAA", "industry": "Industry X", "sector": "S", "rs63": 90.0, "rs189": 90.0, "ret1": 0.01, "ret20": 0.10},
            {"ticker": "BBB", "industry": "Industry X", "sector": "S", "rs63": 80.0, "rs189": 80.0, "ret1": 0.02, "ret20": 0.05},
            {"ticker": "REF", "industry": "Industry Y", "sector": "T", "rs63": 70.0, "rs189": 70.0, "ret1": 0.00, "ret20": 0.00},
            {"ticker": "OVR", "industry": "Industry X", "sector": "S", "rs63": 75.0, "rs189": 75.0, "ret1": 0.03, "ret20": 0.08},
        ]
    }


def _exact():
    return {
        "AAA": ("Major A", "Theme A"),
        "BBB": ("Major A", "Theme A"),
        "REF": ("Major B", "Theme B"),
    }


def test_manual_override_precedes_industry_inference_and_keeps_trade_score_neutral(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "load_theme_map", lambda path: _exact())
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({
        "schema_version": rt.OVERRIDES_SCHEMA,
        "researched_at": "2026-09-12",
        "source_kind": "SEC/issuer cross-check",
        "policy": "existing fine themes only",
        "overrides": {
            "OVR": ["Theme B", 0.91, "Issuer is a Theme B business."],
        },
    }), encoding="utf-8")

    membership, rotation, scores = rt.build_recovered_theme_outputs(
        _rows(),
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
        theme_map_path=tmp_path / "unused.b64",
        theme_overrides_path=overrides,
    )

    by_ticker = {row["ticker"]: row for row in membership["rows"]}
    assert by_ticker["OVR"]["theme_id"] == "Theme B"
    assert by_ticker["OVR"]["major_theme"] == "Major B"
    assert by_ticker["OVR"]["tag_method"] == "MANUAL_RESEARCHED_OVERRIDE"
    assert by_ticker["OVR"]["tag_confidence"] == pytest.approx(0.91)
    assert by_ticker["OVR"]["tag_evidence"] == "Issuer is a Theme B business."
    assert by_ticker["OVR"]["tag_source_kind"] == "SEC/issuer cross-check"
    assert membership["coverage_detail"]["manual"] == 1
    assert membership["coverage_detail"]["inferred"] == 0
    assert membership["coverage_detail"]["unmapped"] == 0
    assert membership["coverage"] == 1.0

    score = {row["ticker"]: row for row in scores["rows"]}["OVR"]
    assert score["peer_theme_score"] == rt.NEUTRAL_THEME_SCORE
    assert scores["rules"]["manual_override_membership_only"] is True
    assert any(row["theme_id"] == "Theme B" for row in rotation["rows"])


def test_manual_override_rejects_nonlegacy_theme(tmp_path):
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({
        "schema_version": rt.OVERRIDES_SCHEMA,
        "overrides": {"OVR": ["Invented Theme", 0.9, "not allowed"]},
    }), encoding="utf-8")
    with pytest.raises(rt.RecoveredThemeError, match="non-legacy fine theme"):
        rt.load_theme_overrides(overrides, _exact())


def test_exact_legacy_map_remains_authoritative_over_manual_override(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "load_theme_map", lambda path: _exact())
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({
        "schema_version": rt.OVERRIDES_SCHEMA,
        "overrides": {"AAA": ["Theme B", 0.99, "must not replace exact"]},
    }), encoding="utf-8")

    membership, _, _ = rt.build_recovered_theme_outputs(
        {"rows": _rows()["rows"][:3]},
        session_date="2026-09-11",
        generated_at="2026-09-12T00:00:00Z",
        theme_map_path=tmp_path / "unused.b64",
        theme_overrides_path=overrides,
    )
    row = {x["ticker"]: x for x in membership["rows"]}["AAA"]
    assert row["theme_id"] == "Theme A"
    assert row["major_theme"] == "Major A"
    assert row["tag_method"] == "EXACT_SECTOR_SNAPSHOT"
    assert membership["coverage_detail"]["manual"] == 0


def test_production_override_file_matches_current_manual_rows_and_legacy_taxonomy(tmp_path):
    config = Path("config")
    parts = sorted(config.glob("theme_s2t.part*.b64"))
    assert len(parts) >= 2
    combined = "".join(part.read_text(encoding="utf-8").strip() for part in parts)
    reconstructed = tmp_path / "theme_s2t.b64"
    reconstructed.write_text(combined, encoding="utf-8")

    exact = rt.load_theme_map(reconstructed)
    manual, meta = rt.load_theme_overrides(config / "theme_manual_overrides.json", exact)
    current = json.loads(Path("data/theme_membership.json").read_text(encoding="utf-8"))
    manual_rows = {
        str(row.get("ticker") or "").strip().upper()
        for row in current.get("rows", [])
        if row.get("tag_method") == "MANUAL_RESEARCHED_OVERRIDE"
    }
    unmapped = {
        str(row.get("ticker") or "").strip().upper()
        for row in current.get("rows", [])
        if row.get("tag_method") == "UNMAPPED"
    }

    assert current["coverage_detail"]["unmapped"] == 0
    assert current["coverage"] == 1.0
    assert not unmapped
    assert current["coverage_detail"]["manual"] == 115
    assert len(manual) == 115
    assert set(manual) == manual_rows
    assert all(ticker not in exact for ticker in manual)
    assert meta["policy"].startswith("Only current-universe legacy-map gaps")
