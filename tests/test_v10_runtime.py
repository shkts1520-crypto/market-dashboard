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


def test_runtime_hides_mock_children_before_payload_render():
    text = js()
    assert "suppressMockContent();" in text
    assert "child.hidden = true;" in text
    assert "Mock values remain shielded." in text


def test_runtime_uses_canonical_on_class_for_tabs_and_sections():
    text = js()
    assert "tab.classList.toggle(\n          'on'," in text
    assert "section.classList.toggle(\n          'on'," in text
    assert "tab.classList.contains(\n              'on'" in text
    assert "'active'" not in text
