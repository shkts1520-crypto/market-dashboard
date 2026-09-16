from pathlib import Path


def site_js():
    return Path("assets/v38-site.js").read_text(encoding="utf-8")


def binder_js():
    return Path("assets/v38-canonical-binder.js").read_text(encoding="utf-8")


def test_runtime_uses_href_targets_not_missing_data_target_contract():
    text = site_js()
    assert 'a.tabx[href^="#"]' in text
    assert "tab.dataset.target" not in text


def test_runtime_keeps_all_section_ids():
    text = site_js()
    for section_id in (
        "t-market", "t-alloc", "t-port", "t-today", "t-rotation", "t-movers",
        "t-rs", "t-weekly", "t-options", "t-post1", "t-rules",
    ):
        assert text.count("'" + section_id + "'") >= 1


def test_runtime_is_navigation_and_data_loader_only():
    site = site_js()
    binder = binder_js()
    assert "rememberCardTitles();" in site
    assert "loadProductionData();" in site
    assert "neutralizeCards(section" not in site
    assert "renderPublish(view)" not in site
    assert "renderDaily(view)" not in site
    assert "function renderDaily(view)" in binder
    assert "function renderPublish(view)" in binder
    assert "v38-production-state" not in site
    assert "v38-live-grid" not in site
    assert "v38-generic-row" not in site
    assert "v38-rs-row" not in site


def test_runtime_uses_canonical_on_class_for_tabs_and_sections():
    text = site_js()
    assert "tab.classList.toggle('on', active)" in text
    assert "section.classList.toggle('on', section.id === targetId)" in text
    assert "classList.toggle('active'" not in text


def test_runtime_uses_history_and_never_manages_section_hidden_state():
    text = site_js()
    assert "history.pushState" in text
    assert "window.addEventListener('popstate'" in text
    assert "window.addEventListener('hashchange'" in text
    assert "window.scrollTo(0, 0)" in text
    assert "section.hidden" not in text


def test_canonical_binder_owns_live_component_rendering():
    text = binder_js()
    for renderer in (
        "function renderDaily(view)",
        "function renderPositions(view)",
        "function renderCore(view)",
        "function renderSetups(view)",
        "function renderRotation(view)",
        "function renderMovers(view)",
        "function renderRs(view)",
        "function renderWeekly(view)",
        "function renderOptions(options)",
        "function renderPublish(view)",
        "function renderRules(view)",
    ):
        assert renderer in text
    assert "v38-canonical-list" in text
    assert "dataset.v38TruthSource" in text
    assert "UNBOUND_VISIBLE_CARD" in text
