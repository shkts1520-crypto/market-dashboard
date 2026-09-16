from pathlib import Path


def test_production_build_has_one_canonical_card_owner():
    source = Path('scripts/build_site.py').read_text(encoding='utf-8')
    assert 'assets/v38-canonical-binder.js' in source
    assert 'live_binder_enabled = False' in source
    assert 'restored_experience_enabled = False' in source
    assert 'production_truth_enabled = False' in source
    assert 'production_label_truth_enabled = False' in source
    assert 'public_final_enabled = False' in source
    assert '"canonical_binder_extension": canonical_binder_enabled' in source


def test_canonical_binder_does_not_hide_missing_diagnostics():
    source = Path('assets/v38-canonical-binder.js').read_text(encoding='utf-8')
    assert 'hideDiagnostics' not in source
    assert "dataset.v38TruthSource" in source
    assert "dataset.v38Status" in source
    assert "UNBOUND_VISIBLE_CARD" in source
    assert "display:none" not in source.replace(' ', '')


def test_retired_patch_assets_are_not_runtime_injected():
    source = Path('scripts/build_site.py').read_text(encoding='utf-8')
    for asset in (
        'v38-live-binder.js', 'v38-restored-experience.js',
        'v38-production-truth.js', 'v38-production-label-truth.js',
        'v38-public-final.js',
    ):
        assert f'_inject_external_extension(out, Path("assets/{asset}"))' not in source
