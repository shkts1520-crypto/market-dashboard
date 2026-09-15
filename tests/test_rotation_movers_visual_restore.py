import json
from pathlib import Path

from v38.movers_ui import attach_movers_ui


ASSET = Path("assets/v38-rotation-movers-visual.js")
BUILD = Path("scripts/build_site.py")


def _row(ticker: str, base: float, bump: float) -> dict:
    closes = [base * (1 + bump * i / 30) for i in range(31)]
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": "Test",
        "industry": "Test Group",
        "rs189": 90.0,
        "ddv20": 20_000_000,
        "ret1": closes[-1] / closes[-2] - 1,
        "ret20": closes[-1] / closes[-21] - 1,
        "sparkline": [{"date": f"2026-08-{i+1:02d}", "close": value} for i, value in enumerate(closes)],
    }


def test_movers_payload_uses_full_rs_rows_and_three_windows(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    rows = [_row(f"T{i:03d}", 10 + i, (i - 20) / 500) for i in range(50)]
    (data / "rs.json").write_text(json.dumps({"session_date": "2026-09-14", "status": "READY", "rows": rows}), encoding="utf-8")
    view = {"session_date": "2026-09-14", "movers": {}}
    out = attach_movers_ui(view, data)
    movers = out["movers"]
    assert movers["status"] == "READY"
    assert movers["universe_count"] == 50
    assert set(movers["periods"]) == {"1d", "1w", "1m"}
    assert len(movers["periods"]["1d"]["gainers"]) == 20
    assert len(movers["periods"]["1w"]["losers"]) == 20
    assert movers["source"].startswith("rs.json full universe")


def test_rotation_movers_visual_layer_is_scoped_and_source_shaped():
    js = ASSET.read_text(encoding="utf-8")
    for token in (
        "t-rotation", "t-movers", "canonicalRotation", "mv-wrap", "mv-sec-h",
        "3窓一致", "資金フロー（GICS11）", "主導セクター・業種",
        "強い業種の主導株", "セクターETF強弱", "サブテーマ別RS",
    ):
        assert token in js
    for forbidden in ("t-market", "t-alloc", "t-port", "t-weekly", "t-options", "t-rules"):
        assert "getElementById('" + forbidden + "')" not in js


def test_rotation_movers_visual_layer_loads_last():
    py = BUILD.read_text(encoding="utf-8")
    status = py.index('status_truth = Path("assets/v38-status-truth.js")')
    visual = py.index('rotation_movers_visual = Path("assets/v38-rotation-movers-visual.js")')
    assert status < visual
    assert '"rotation_movers_visual_extension": rotation_movers_visual_enabled' in py
