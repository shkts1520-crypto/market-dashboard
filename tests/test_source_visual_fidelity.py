from pathlib import Path

LEGACY_SOURCE_ASSET = Path('assets/v38-source-fidelity.js')
LEGACY_SOURCE_CSS = Path('assets/v38-source-fidelity.css')
LEGACY_VISUAL_POLISH = Path('assets/v38-visual-polish.js')
PY_SOURCE_CSS = Path('assets/v38-py-source-authority.css')
PY_SOURCE_JS = Path('assets/v38-py-source-authority.js')
BUILD = Path('scripts/build_site.py')
RUNTIME = Path('assets/v38-runtime.js')
BINDER = Path('assets/v38-canonical-binder.js')


def test_legacy_fixed_canvas_layer_stays_unbound():
    py = BUILD.read_text(encoding='utf-8')
    assert 'source_fidelity_enabled = False' in py
    js = LEGACY_SOURCE_ASSET.read_text(encoding='utf-8')
    assert 'width:1680px!important' in js
    assert 'height:1080px!important' in js
    assert 'v38-source-rotation-frame' in js


def test_uploaded_py_authority_assets_are_injected_and_legacy_layers_are_not():
    py = BUILD.read_text(encoding='utf-8')
    assert 'assets/v38-py-source-authority.css' in py
    assert 'assets/v38-py-source-authority.js' in py
    assert 'assets/v38-source-fidelity.css' not in py
    assert 'assets/v38-visual-polish.js' not in py
    assert 'visual_polish_enabled = False' in py


def test_uploaded_py_authority_excludes_options_and_covers_non_options_tabs():
    css = PY_SOURCE_CSS.read_text(encoding='utf-8')
    js = PY_SOURCE_JS.read_text(encoding='utf-8')
    assert 'section:not(#t-options)' in css
    assert "const NON_OPTIONS = ['t-market','t-alloc','t-port','t-today','t-rotation','t-movers','t-rs','t-weekly','t-post1','t-rules']" in js
    assert "'t-options'" not in js.split('const NON_OPTIONS =', 1)[1].split(';', 1)[0]
    for section in ('t-market', 't-alloc', 't-port', 't-today', 't-rotation', 't-movers', 't-rs', 't-weekly', 't-post1', 't-rules'):
        assert section in js


def test_source_py_specialized_cards_are_locked():
    css = PY_SOURCE_CSS.read_text(encoding='utf-8')
    js = PY_SOURCE_JS.read_text(encoding='utf-8')
    for token in ('reg-grid', 'vixvals', 'vixwtabs', 'ftd-row'):
        assert token in css
    for token in ('sourceRegime', 'sourceVix', 'sourceFtd', 'sourceOrder'):
        assert token in js
    assert 'F1 リーダー脱落率' in js
    assert 'LWMA5' in js
    assert 'LWMA10' in js


def test_legacy_visual_assets_remain_available_but_are_not_authoritative():
    assert LEGACY_SOURCE_CSS.is_file()
    assert LEGACY_VISUAL_POLISH.is_file()
    assert PY_SOURCE_CSS.is_file()
    assert PY_SOURCE_JS.is_file()


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
