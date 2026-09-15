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


def test_status_truth_repair_loop_is_retired_by_builder():
    py = BUILD.read_text(encoding="utf-8")
    assert 'status_truth_enabled = False' in py
    assert '_inject_external_extension(out, status_truth)' not in py
    assert '"status_truth_extension": status_truth_enabled' in py
