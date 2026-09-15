from pathlib import Path


SOURCE_ASSET = Path("assets/v38-source-fidelity.js")
RESTORED_ASSET = Path("assets/v38-restored-experience.js")
BUILD = Path("scripts/build_site.py")
RUNTIME = Path("assets/v38-runtime.js")


def test_fixed_canvas_source_fidelity_is_not_bound_to_production():
    py = BUILD.read_text(encoding="utf-8")
    assert 'source_fidelity_enabled = False' in py
    assert 'source_fidelity_contract_enabled = False' in py
    assert '_inject_external_extension(out, source_fidelity)' not in py
    assert '_inject_external_extension(out, source_fidelity_contract)' not in py


def test_bad_fixed_canvas_asset_remains_quarantined_not_deleted():
    js = SOURCE_ASSET.read_text(encoding="utf-8")
    # Keep the old implementation for audit/history, but production must not bind it.
    assert "width:1680px!important" in js
    assert "height:1080px!important" in js
    assert "v38-source-rotation-frame" in js


def test_restored_experience_only_owns_approved_added_surfaces():
    js = RESTORED_ASSET.read_text(encoding="utf-8")
    py = BUILD.read_text(encoding="utf-8")
    for token in (
        "card rsx-card",
        "Ticker Search",
        "v38-vwap-live",
    ):
        assert token in js
    assert 'restored_experience = Path("assets/v38-restored-experience.js")' in py
    assert 'restored_experience_enabled = _inject_external_extension(out, restored_experience)' in py
    assert "if(view&&searchData)renderRotation" not in js


def test_runtime_never_reinjects_display_extensions():
    js = RUNTIME.read_text(encoding="utf-8")
    assert "loadDisplayExtensions" not in js
    assert "appendExtension" not in js
    for asset in ("v38-observables.js", "v38-polish.js", "v38-final-ui.js"):
        assert asset not in js


def test_quarantined_visual_asset_does_not_define_trading_rules():
    js = SOURCE_ASSET.read_text(encoding="utf-8")
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
