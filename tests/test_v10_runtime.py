from pathlib import Path


def js():
    return Path("assets/v38-site.js").read_text(encoding="utf-8")


def test_runtime_uses_href_targets_not_missing_data_target_contract():
    text = js()
    assert 'a.tabx[href^="#"]' in text
    assert "tab.dataset.target" not in text


def test_runtime_keeps_exact_nine_section_ids():
    text = js()
    for section_id in (
        "t-market",
        "t-alloc",
        "t-port",
        "t-rotation",
        "t-rs",
        "t-weekly",
        "t-options",
        "t-post1",
        "t-rules",
    ):
        assert text.count("'" + section_id + "'") >= 1


def test_runtime_reuses_canonical_cards_and_removes_legacy_replacement_ui():
    text = js()
    assert "rememberCardTitles();" in text
    assert "neutralizeCards(section" in text
    assert "suppressMockContent" not in text
    assert "child.hidden = true;" not in text
    assert "v38-production-state" not in text
    assert "v38-live-grid" not in text
    assert "v38-generic-row" not in text
    assert "v38-rs-row" not in text


def test_runtime_uses_canonical_on_class_for_tabs_and_sections():
    text = js()
    assert "tab.classList.toggle('on', active)" in text
    assert "section.classList.toggle('on', id === valid)" in text
    assert "'active'" not in text


def test_runtime_uses_history_and_never_manages_section_hidden_state():
    text = js()
    assert "history.pushState" in text
    assert "window.addEventListener('popstate'" in text
    assert "window.addEventListener('hashchange'" in text
    assert "window.scrollTo(0, 0)" in text
    assert "section.hidden" not in text


def test_runtime_binds_live_values_into_canonical_component_classes():
    text = js()
    for class_name in (
        "rsx-item",
        "rsx-row",
        "rsx-name",
        "rsx-score",
        "w30exit",
    ):
        assert class_name in text
