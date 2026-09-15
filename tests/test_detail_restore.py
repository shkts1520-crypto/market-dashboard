from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_detail_restore_has_vix_five_condition_panel_and_rotation_sections():
    js = (ROOT / "assets" / "v38-detail-restore.js").read_text(encoding="utf-8")
    for token in ("EVENT", "ROLLOVER", "BOTTOM", "RE-EXTREME", "REARM"):
        assert token in js
    for token in (
        "大分類 — 期間ごとランキング",
        "順位推移（大分類） Rank Flow",
        "細分類 — Sub-theme RS Rank",
        "Dollar-Vol (Adv+Dec)",
        "セクターETF強弱 Sector ETF Strength",
        "fine_theme_groups",
        "major_theme_groups",
    ):
        assert token in js
    assert "v38-ticker-link" in js
    assert "Core 12のEligibility/Rankingには使用しません" in js


def test_detail_restore_is_retired_from_production():
    build = (ROOT / "scripts" / "build_site.py").read_text(encoding="utf-8")
    assert 'detail_restore_enabled = False' in build
    assert '_inject_external_extension(out, detail_restore)' not in build
    assert '"detail_restore_extension": detail_restore_enabled' in build
