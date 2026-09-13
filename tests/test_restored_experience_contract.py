from __future__ import annotations

from pathlib import Path


def test_restored_experience_assets_and_build_wiring() -> None:
    build = Path("scripts/build_site.py").read_text(encoding="utf-8")
    experience = Path("assets/v38-restored-experience.js").read_text(encoding="utf-8")
    chart = Path("assets/v38-restored-chart.js").read_text(encoding="utf-8")

    assert "materialize_restored_experience.py" in build
    assert "v38-restored-chart.js" in build
    assert "v38-restored-experience.js" in build
    assert "search_index.json" in build
    assert "vwap_restore.json" in build

    # Canonical v5 visual keeps Japanese and English search labels as separate DOM text.
    for text in (
        "銘柄検索",
        "Ticker Search",
        "大分類 — 期間ごとランキング",
        "順位フロー（大分類）",
        "小分類（サブテーマ）— 期間ごとランキング",
        "資金の流れ",
        "Options Intelligence",
        "Multi VWAPセットアップ",
        "63 / 252 / All-time VWAP",
    ):
        assert text in experience

    assert "VWAP63" in chart
    assert "VWAP252" in chart
    assert "All-time VWAP" in chart
    assert "Direction" not in chart
    assert "Confidence" not in chart
