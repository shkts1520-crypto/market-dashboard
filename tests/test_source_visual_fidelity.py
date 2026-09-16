from pathlib import Path

SOURCE_ASSET = Path('assets/v38-source-fidelity.js')
BUILD = Path('scripts/build_site.py')
RUNTIME = Path('assets/v38-runtime.js')
BINDER = Path('assets/v38-canonical-binder.js')


def test_fixed_canvas_source_fidelity_is_not_bound_to_production():
    py = BUILD.read_text(encoding='utf-8')
    assert 'source_fidelity_enabled = False' in py
    assert 'source_fidelity_contract_enabled = False' in py


def test_bad_fixed_canvas_asset_remains_quarantined_not_deleted():
    js = SOURCE_ASSET.read_text(encoding='utf-8')
    assert 'width:1680px!important' in js
    assert 'height:1080px!important' in js
    assert 'v38-source-rotation-frame' in js


def test_only_single_canonical_binder_owns_public_cards():
    py = BUILD.read_text(encoding='utf-8')
    assert 'canonical_binder_enabled = _inject_external_extension(out, Path("assets/v38-canonical-binder.js"))' in py
    for old_flag in (
        'live_binder_enabled = False', 'restored_experience_enabled = False',
        'production_truth_enabled = False', 'production_label_truth_enabled = False',
        'public_final_enabled = False',
    ):
        assert old_flag in py
    js = BINDER.read_text(encoding='utf-8')
    assert 'v38TruthSource' in js
    assert 'UNBOUND_VISIBLE_CARD' in js


def test_runtime_never_reinjects_display_extensions():
    js = RUNTIME.read_text(encoding='utf-8')
    assert 'loadDisplayExtensions' not in js
    assert 'appendExtension' not in js
    for asset in ('v38-observables.js', 'v38-polish.js', 'v38-final-ui.js'):
        assert asset not in js


def test_quarantined_visual_asset_does_not_define_trading_rules():
    js = SOURCE_ASSET.read_text(encoding='utf-8')
    for token in ('market_mode','max_new_total_slots','normal_tqqq_pct','panic_tqqq','stop_loss','final_score','eligibility'):
        assert token not in js
