import hashlib
import re

import pytest

import v38.site_builder as sb

from v38.site_builder import (
    SiteBuildError,
    build_safe_shell,
    canonical_fingerprint,
    git_blob_sha,
)

from v38.ui_contract import (
    EXPECTED_TABS,
    validate_production_html,
)


def shell(
    extra_script="",
    extra_attr="",
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

    nav = (
        "<nav>"
        + "".join(
            (
                '<a class="tabx'
                + (
                    " active"
                    if i == 0
                    else ""
                )
                + '" '
                + f'href="{href}" '
                + (
                    'data-target="'
                    + href[1:]
                    + '">'
                )
                + label
                + "</a>"
            )
            for i, (
                label,
                href,
            )
            in enumerate(
                EXPECTED_TABS
            )
        )
        + "</nav>"
    )

    sections = "".join(
        (
            '<section id="'
            + href[1:]
            + '"'
            + extra_attr
            + '>'
            + (
                '<div class="mock">'
                '123'
                '</div>'
            )
            + '</section>'
        )
        for _, href
        in EXPECTED_TABS
    )

    return (
        "<!doctype html>"
        "<html>"
        "<head>"
        f"{visual}"
        "</head>"
        "<body>"
        f"{nav}"
        f"{sections}"
        f"{extra_script}"
        "</body>"
        "</html>"
    )


def test_git_blob_sha_matches_git_object_formula():
    data = b"abc"

    expected = hashlib.sha1(
        b"blob 3\0abc"
    ).hexdigest()

    assert (
        git_blob_sha(
            data
        )
        == expected
    )

    assert (
        canonical_fingerprint(
            data
        )
        == {
            "size": 3,
            "blob_sha": expected,
        }
    )


def test_builder_strips_inline_scripts_and_event_handlers():
    html = shell(
        (
            "<script>"
            "var x=Entry*0.75;"
            "</script>"
        ),
        ' onclick="bad()"',
    )

    out = build_safe_shell(
        html
    )

    report = (
        validate_production_html(
            out
        )
    )

    assert (
        report[
            "inline_script_count"
        ]
        == 0
    )

    assert (
        report[
            "inline_event_handler_count"
        ]
        == 0
    )


def test_builder_preserves_original_style_block_bytes():
    html = shell(
        (
            "<script>"
            "console.log(1)"
            "</script>"
        )
    )

    original = re.findall(
        (
            r"<style\b[^>]*>"
            r".*?"
            r"</style\s*>"
        ),
        html,
        flags=re.I | re.S,
    )

    out = build_safe_shell(
        html
    )

    generated = [
        x
        for x
        in re.findall(
            (
                r"<style\b[^>]*>"
                r".*?"
                r"</style\s*>"
            ),
            out,
            flags=re.I | re.S,
        )
        if (
            "v38-production-shield"
            not in x
        )
    ]

    assert (
        generated
        == original
    )


def test_builder_keeps_exact_nine_tabs_and_sections():
    out = build_safe_shell(
        shell()
    )

    report = (
        validate_production_html(
            out
        )
    )

    assert (
        report["tabs"]
        == list(
            EXPECTED_TABS
        )
    )

    assert (
        out.count(
            'class="card '
            'v38-production-state"'
        )
        == 9
    )


def test_builder_hides_mock_content_by_default():
    out = build_safe_shell(
        shell()
    )

    assert (
        'data-v38-production="shielded"'
        in out
    )

    assert (
        "Mock values are shielded."
        in out
    )

    assert (
        "#t-market > "
        ":not(.v38-production-state)"
        in out
    )


def test_builder_injects_only_two_external_runtime_scripts():
    out = build_safe_shell(
        shell()
    )

    report = (
        validate_production_html(
            out
        )
    )

    assert (
        report[
            "external_script_count"
        ]
        == 2
    )

    assert (
        'src="assets/v38-runtime.js"'
        in out
    )

    assert (
        'src="assets/v38-site.js"'
        in out
    )


def test_builder_fails_if_required_section_missing():
    bad = shell().replace(
        (
            '<section '
            'id="t-options">'
            '<div class="mock">'
            '123'
            '</div>'
            '</section>'
        ),
        "",
    )

    with pytest.raises(
        Exception
    ):
        build_safe_shell(
            bad
        )


def test_verify_canonical_bytes_fails_on_any_different_file():
    with pytest.raises(
        SiteBuildError,
        match=(
            "canonical size mismatch"
        ),
    ):
        sb.verify_canonical_bytes(
            b"not canonical"
        )
