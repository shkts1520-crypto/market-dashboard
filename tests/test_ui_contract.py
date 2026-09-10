import pytest

from v38.ui_contract import (
    EXPECTED_TABS,
    UIContractError,
    display_value,
    inspect_shell,
    scan_production_forbidden_logic,
    validate_canonical_shell,
    validate_production_html,
)


def shell(
    *,
    extra_nav="",
    omit_visual="",
):
    visual = (
        "<style>"
        ".card{}"
        ".chart{}"
        ".rsx-card{}"
        ".rsx-item{}"
        ".mrow{}"
        ".bflags{}"
        "</style>"
    )

    if omit_visual:
        visual = visual.replace(
            omit_visual,
            "",
        )

    nav = (
        "<nav>"
        + "".join(
            (
                '<a class="tabx" '
                f'href="{href}">'
                f"{label}</a>"
            )
            for label, href
            in EXPECTED_TABS
        )
        + extra_nav
        + "</nav>"
    )

    sections = "".join(
        (
            '<section id="'
            f'{href[1:]}">'
            "</section>"
        )
        for _, href
        in EXPECTED_TABS
    )

    return (
        "<!doctype html>"
        "<html><head>"
        f"{visual}"
        "</head><body>"
        f"{nav}"
        f"{sections}"
        "</body></html>"
    )


def test_exact_nine_tab_shell_passes():
    out = validate_canonical_shell(
        shell()
    )

    assert (
        out["tabs"]
        == list(EXPECTED_TABS)
    )


def test_tab_order_is_contract_not_set_membership():
    bad = shell().replace(
        "Daily</a>",
        "X</a>",
        1,
    )

    with pytest.raises(
        UIContractError,
        match="tabs must equal",
    ):
        validate_canonical_shell(
            bad
        )


def test_setups_and_movers_are_forbidden_in_nav():
    bad = shell(
        extra_nav=(
            '<a class="tabx" '
            'href="#x">'
            "Setups</a>"
        )
    )

    with pytest.raises(
        UIContractError
    ):
        validate_canonical_shell(
            bad
        )


def test_all_nine_sections_are_required():
    bad = shell().replace(
        (
            '<section '
            'id="t-options">'
            "</section>"
        ),
        "",
    )

    with pytest.raises(
        UIContractError,
        match=(
            "missing tab sections"
        ),
    ):
        validate_canonical_shell(
            bad
        )


def test_visual_vocabulary_is_guarded():
    bad = shell(
        omit_visual=(
            ".rsx-card{}"
        )
    )

    with pytest.raises(
        UIContractError,
        match="visual tokens",
    ):
        validate_canonical_shell(
            bad
        )


def test_inspection_does_not_mutate_html():
    html = shell()
    before = html[:]

    inspect_shell(html)

    assert html == before


def test_production_forbidden_logic_is_detected():
    bad = (
        shell()
        + (
            "<script>"
            "var x=Entry*0.75;"
            "</script>"
        )
    )

    hits = (
        scan_production_forbidden_logic(
            bad
        )
    )

    assert hits

    with pytest.raises(
        UIContractError
    ):
        validate_production_html(
            bad
        )


def test_null_nan_and_empty_display_as_dash():
    assert (
        display_value(None)
        == "—"
    )

    assert (
        display_value("")
        == "—"
    )

    assert (
        display_value(
            float("nan")
        )
        == "—"
    )


def test_zero_is_not_confused_with_missing():
    assert (
        display_value(
            0,
            decimals=2,
        )
        == "0.00"
    )
