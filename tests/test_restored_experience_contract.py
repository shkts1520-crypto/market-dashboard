from __future__ import annotations

from pathlib import Path


def test_single_canonical_binder_and_restored_interaction_assets_are_wired() -> None:
    build = Path("scripts/build_site.py").read_text(encoding="utf-8")
    binder = Path("assets/v38-canonical-binder.js").read_text(encoding="utf-8")
    experience = Path("assets/v38-restored-experience.js").read_text(encoding="utf-8")
    chart = Path("assets/v38-restored-chart.js").read_text(encoding="utf-8")

    assert "materialize_restored_experience.py" in build
    assert "v38-restored-chart.js" in build
    assert "v38-canonical-binder.js" in build
    assert "v38-restored-experience.js" not in build
    assert "search_index.json" in build
    assert "vwap_restore.json" in build

    # Card ownership is consolidated in the canonical binder. The old restored
    # experience asset remains only for audit/history and must not be injected.
    for text in (
        "銘柄検索",
        "Ticker Search",
        "資金フロー（GICS11＋スタイル）",
        "OPTION_BUCKETS",
    ):
        assert text in binder
    assert "v38-restored-experience.js" not in build
    assert "Ticker Search" in experience

    # Chart interaction remains a separate non-card enhancement.
    assert "VWAP63" in chart
    assert "VWAP252" in chart
    assert "All-time VWAP" in chart
    assert "Direction" not in chart
    assert "Confidence" not in chart
