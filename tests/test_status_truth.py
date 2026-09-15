from pathlib import Path


ASSET = Path("assets/v38-status-truth.js")
BUILD = Path("scripts/build_site.py")


def test_status_truth_only_suppresses_restoration_scaffolds():
    js = ASSET.read_text(encoding="utf-8")
    assert "BASELINE_CARD_SOURCE_UNAVAILABLE" in js
    assert "ROTATION_INDEX_BREADTH_SOURCE_UNAVAILABLE" in js
    assert "setups.status !== 'READY'" in js
    assert "rotation.status !== 'READY'" in js
    assert "v38PlaceholderSuppressed" in js


def test_status_truth_keeps_true_missing_states_visible():
    js = ASSET.read_text(encoding="utf-8")
    # No global replacement of missing-state words is allowed. Cleanup is scoped
    # to READY cards or known baseline placeholders only.
    assert "document.body.textContent" not in js
    assert "querySelectorAll('[data-v38-status=\"DATA_REQUIRED\"]')" not in js
    assert "closest('.card')" in js


def test_status_truth_is_bound_last_by_builder():
    py = BUILD.read_text(encoding="utf-8")
    status = py.index('status_truth = Path("assets/v38-status-truth.js")')
    restored = py.index('restored_experience = Path("assets/v38-restored-experience.js")')
    fallback = py.index('data_completeness_fallback = Path("assets/v38-data-completeness-fallback.js")')
    assert restored < fallback < status
    assert '"status_truth_extension": status_truth_enabled' in py
