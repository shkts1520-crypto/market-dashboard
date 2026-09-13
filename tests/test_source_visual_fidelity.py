from pathlib import Path


ASSET = Path("assets/v38-source-fidelity.js")
BUILD = Path("scripts/build_site.py")


def test_source_fidelity_is_visual_only_and_uses_canonical_rotation_geometry():
    js = ASSET.read_text(encoding="utf-8")
    assert "Visual-only source fidelity layer" in js
    assert "width:1680px!important" in js
    assert "height:1080px!important" in js
    assert "grid-template-columns:repeat(4,1fr)!important" in js
    assert "grid-template-rows:398px 1fr!important" in js
    assert "rotate(90deg)" in js
    assert "v38-source-rotation-frame" in js
    assert "SNS共有用カード" in js


def test_source_fidelity_restores_original_search_vwap_and_options_shapes():
    js = ASSET.read_text(encoding="utf-8")
    assert "font-size:15px!important" in js
    assert "padding:10px 12px!important" in js
    assert "native-rsx-stack" in js
    assert "['銘柄','63 VWAP','252 VWAP','上場来VWAP','上場来ブレイク']" in js
    assert "vwtbl" in js
    assert "five-column" in js


def test_source_fidelity_loads_after_restored_experience():
    py = BUILD.read_text(encoding="utf-8")
    restored = py.index('restored_experience = Path("assets/v38-restored-experience.js")')
    source = py.index('source_fidelity = Path("assets/v38-source-fidelity.js")')
    assert restored < source
    assert '"source_fidelity_extension": source_fidelity_enabled' in py


def test_source_fidelity_does_not_define_trading_rules():
    js = ASSET.read_text(encoding="utf-8")
    forbidden = (
        "market_mode",
        "max_new_total_slots",
        "normal_tqqq_pct",
        "panic_tqqq",
        "stop_loss",
        "final_score",
        "eligibility",
    )
    for token in forbidden:
        assert token not in js
