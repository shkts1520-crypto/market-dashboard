from pathlib import Path


def test_production_options_surfaces_existing_upward_rankings():
    js = Path("assets/v38-canonical-binder.js").read_text(encoding="utf-8")
    assert "upward_rankings" in js
    assert "上方向配置 Upward Positioning" in js
    assert "data/options/index.json.upward_rankings" in js
    assert "上昇予測・売買ゲートではありません" in js
    assert "['0-45','0-6','7-21','22-45']" in js


def test_source_mc57_options_surfaces_existing_upward_rankings():
    js = Path("assets/source-mc57-options-tab.js").read_text(encoding="utf-8")
    assert "upward_rankings" in js
    assert "上方向配置" in js
    assert "Upward Positioning" in js
    assert "上昇予測ではなく表示専用" in js
    assert "['0-45','0-6','7-21','22-45']" in js
