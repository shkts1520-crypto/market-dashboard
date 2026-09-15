from pathlib import Path


def test_production_truth_asset_is_one_shot_and_has_no_permanent_observer():
    source = Path('assets/v38-production-truth.js').read_text(encoding='utf-8')
    assert "dataset.v38TruthBinding='ready'" in source
    assert 'MutationObserver' not in source
    assert 'setInterval(' not in source
    assert 'MOCK DATA' not in source


def test_build_injects_production_truth_last():
    source = Path('scripts/build_site.py').read_text(encoding='utf-8')
    truth = source.index('production_truth = Path("assets/v38-production-truth.js")')
    restored = source.index('restored_experience = Path("assets/v38-restored-experience.js")')
    fallback = source.index('tradingview_fallback = Path("assets/v38-tradingview-fallback.js")')
    assert truth > restored
    assert truth > fallback
    assert '"production_truth_extension": production_truth_enabled' in source
