from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "v38-build-dashboard3-fidelity.js"
BUILD = ROOT / "scripts" / "build_site.py"


def test_build_dashboard3_guard_owns_exactly_ten_non_options_tabs():
    js = ASSET.read_text(encoding="utf-8")
    expected = (
        "t-market", "t-alloc", "t-port", "t-today", "t-rotation",
        "t-movers", "t-rs", "t-weekly", "t-post1", "t-rules",
    )
    for section_id in expected:
        assert section_id in js
    assert "const SOURCE='build_dashboard(3).py'" in js
    assert "t-options" not in js
    assert "options_touched:false" in js


def test_mc57_detail_table_is_restored_from_live_view_model():
    js = ASSET.read_text(encoding="utf-8")
    for token in (
        "data/ui_view_model.json", "mri-bd", "主要マーケット観測",
        "MC57", "50MA Breadth", "200MA Breadth", "NQSAR", "F1 / F2 / F3",
    ):
        assert token in js
    assert "restoreMc57" in js


def test_rrg_is_single_owner_in_rotation():
    js = ASSET.read_text(encoding="utf-8")
    assert "function repairRrg" in js
    assert "rotation-rrg" in js
    assert "rr.length!==1" in js
    assert "rr[0]?.closest('section')?.id!=='t-rotation'" in js


def test_full_card_inventory_audit_is_fail_closed():
    js = ASSET.read_text(encoding="utf-8")
    for token in ("EXPECTED", "missing:[]", "duplicates:[]", "V38BuildDashboard3Audit"):
        assert token in js
    assert "r.ok=!r.missing.length&&!r.duplicates.length" in js
    assert "v38BuildDashboard3Audit=r.ok?'ready':'error'" in js


def test_production_build_loads_fidelity_guard_last():
    py = BUILD.read_text(encoding="utf-8")
    assert 'ui_authority": "build_dashboard(3).py"' in py
    finalizer = py.index('Path("assets/v38-py-source-finalizer.js")')
    fidelity = py.index('Path("assets/v38-build-dashboard3-fidelity.js")')
    assert finalizer < fidelity
    assert '"build_dashboard3_fidelity": build_dashboard3_fidelity_enabled' in py
    assert '"options_ui_authority": "current_options_implementation"' in py
    assert '"trading_logic_changed": False' in py
