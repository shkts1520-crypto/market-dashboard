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

    # Only approved post-baseline surfaces are rendered here. Rotation/Setups
    # structure comes from the build-time source DOM.
    for text in (
        "銘柄検索",
        "Ticker Search",
        "Options Intelligence",
        "v38-vwap-live",
    ):
        assert text in experience
    assert "if(view&&searchData)renderRotation" not in experience

    assert "VWAP63" in chart
    assert "VWAP252" in chart
    assert "All-time VWAP" in chart
    assert "Direction" not in chart
    assert "Confidence" not in chart
