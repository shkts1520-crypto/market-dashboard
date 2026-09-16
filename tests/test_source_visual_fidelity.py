from pathlib import Path

SOURCE_ASSET = Path('assets/v38-source-fidelity.js')
SOURCE_CSS = Path('assets/v38-source-fidelity.css')
VISUAL_POLISH = Path('assets/v38-visual-polish.js')
BUILD = Path('scripts/build_site.py')
RUNTIME = Path('assets/v38-runtime.js')
BINDER = Path('assets/v38-canonical-binder.js')


def test_source_fidelity_visual_layer_is_bound_to_production():
    py = BUILD.read_text(encoding='utf-8')
    assert 'source_fidelity_enabled = _inject_external_extension' in py
    assert 'assets/v38-source-fidelity.js' in py
    assert 'assets/v38-source-fidelity.css' in py
    assert 'assets/v38-visual-polish.js' in py


def test_source_fidelity_fixed_canvas_has_mobile_fit_path():
    js = SOURCE_ASSET.read_text(encoding='utf-8')
    assert 'width:1680px!important' in js
    assert 'height:1080px!important' in js
    assert 'v38-source-rotation-frame' in js
    assert 'fitRotation' in js
    assert 'rotate(90deg)' in js


def test_primary_tabs_receive_source_density_css():
    css = SOURCE_CSS.read_text(encoding='utf-8')
    for selector in ('#t-market', '#t-alloc', '#t-port', '#t-rotation', '#t-movers', '#t-post1'):
        assert selector in css
    assert '.v38-trend-svg' in css
    assert '.v38-source-table' in css
    assert '.v38-rrg-svg' in css
    assert '1680/1080' in css


def test_visual_polish_reuses_existing_display_observations():
    js = VISUAL_POLISH.read_text(encoding='utf-8')
    assert 'display_observations' in js
    assert 'sentiment.current' in js
    assert 'sentiment.band' in js
    assert 'v38-publish-visual-polish' in js


def test_canonical_binder_remains_data_owner():
    py = BUILD.read_text(encoding='utf-8')
    assert 'canonical_binder_enabled = _inject_external_extension(out, Path("assets/v38-canonical-binder.js"))' in py
    js = BINDER.read_text(encoding='utf-8')
    assert 'v38TruthSource' in js
    assert 'UNBOUND_VISIBLE_CARD' in js


def test_runtime_never_reinjects_legacy_display_extensions():
    js = RUNTIME.read_text(encoding='utf-8')
    assert 'loadDisplayExtensions' not in js
    assert 'appendExtension' not in js
