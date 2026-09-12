from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .ui_contract import (
    EXPECTED_TABS,
    validate_canonical_shell,
    validate_production_html,
)

CALCULATION_VERSION = (
    "v38-live-site-builder-1.3.0"
)

CANONICAL_BLOB_SHA = (
    "966fe157e3d35344f6e373877b3de5689409dd67"
)

CANONICAL_SIZE = 1412062

_SCRIPT_RE = re.compile(
    (
        r"<script\b[^>]*>"
        r".*?"
        r"</script\s*>"
    ),
    re.I | re.S,
)

_EVENT_RE = re.compile(
    (
        r"\s+on[a-zA-Z0-9_-]+"
        r"\s*=\s*"
        r"(?:"
        r"\"[^\"]*\""
        r"|'[^']*'"
        r"|[^\s>]+"
        r")"
    ),
    re.I | re.S,
)

_STYLE_RE = re.compile(
    (
        r"<style\b[^>]*>"
        r".*?"
        r"</style\s*>"
    ),
    re.I | re.S,
)

_BODY_RE = re.compile(
    (
        r"<body\b"
        r"(?P<attrs>[^>]*)>"
    ),
    re.I | re.S,
)

_HEAD_END_RE = re.compile(
    r"</head\s*>",
    re.I,
)

_BODY_END_RE = re.compile(
    r"</body\s*>",
    re.I,
)

SECTION_IDS = tuple(
    href[1:]
    for _, href
    in EXPECTED_TABS
)

BINDING_STYLE = """<style id="v38-live-binding-bootstrap">
body[data-v38-production="live-binding"] .wrap{opacity:0;pointer-events:none}
body[data-v38-production="live-binding"][data-v38-binding-status] .wrap{opacity:1;pointer-events:auto}
.v38-bind-note{font-size:11px;line-height:1.55;color:#575242;margin-top:6px;overflow-wrap:anywhere}
.v38-bind-note strong{font-size:12px;color:#272622}
.v38-bind-note[data-v38-status="DATA_REQUIRED"] strong,
.v38-bind-note[data-v38-status="STALE"] strong{color:#806319}
.v38-bind-note[data-v38-status="READY"] strong{color:#2b6e45}
.v38-live-kv{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:5px 0;border-top:1px solid rgba(27,29,28,.08)}
.v38-live-kv:first-of-type{border-top:0}
.v38-live-kv span{font-size:10px;color:#575242;min-width:0}
.v38-live-kv b{font-size:12px;text-align:right;overflow-wrap:anywhere;min-width:0}
.v38-ticker-link{color:inherit;text-decoration:none;font-weight:800}
.v38-ticker-link:hover,.v38-ticker-link:focus{text-decoration:underline}
.v38-live-spark{width:100%;height:58px;display:block;margin:6px 0 0}
.chart>.v38-live-spark{height:150px;margin:3px 0 0}
.hm[data-v38-direction="up"]{background:rgba(37,194,95,.10)}
.hm[data-v38-direction="down"]{background:rgba(223,84,84,.10)}
</style>"""

RUNTIME_SCRIPTS = (
    '<script '
    'src="assets/v38-runtime.js" '
    'defer></script>\n'
    '<script '
    'src="assets/v38-site.js" '
    'defer></script>\n'
    '<script '
    'src="assets/v38-observables.js" '
    'defer></script>'
)


class SiteBuildError(
    RuntimeError
):
    pass


def git_blob_sha(
    data: bytes,
) -> str:
    header = (
        f"blob {len(data)}\0"
    ).encode(
        "ascii"
    )

    return hashlib.sha1(
        header + data
    ).hexdigest()


def canonical_fingerprint(
    data: bytes,
) -> dict[str, object]:
    return {
        "size": len(data),
        "blob_sha": (
            git_blob_sha(
                data
            )
        ),
    }


def verify_canonical_bytes(
    data: bytes,
) -> None:
    fp = canonical_fingerprint(
        data
    )

    if (
        fp["size"]
        != CANONICAL_SIZE
    ):
        raise SiteBuildError(
            "canonical size mismatch: "
            f"{fp['size']} != "
            f"{CANONICAL_SIZE}"
        )

    if (
        fp["blob_sha"]
        != CANONICAL_BLOB_SHA
    ):
        raise SiteBuildError(
            "canonical blob mismatch: "
            f"{fp['blob_sha']} != "
            f"{CANONICAL_BLOB_SHA}"
        )


def _style_blocks(
    html: str,
) -> tuple[str, ...]:
    return tuple(
        _STYLE_RE.findall(
            html
        )
    )


def _strip_active_inline_logic(
    html: str,
) -> str:
    without_scripts = (
        _SCRIPT_RE.sub(
            "",
            html,
        )
    )

    return _EVENT_RE.sub(
        "",
        without_scripts,
    )


def _mark_body_live(
    html: str,
) -> str:
    match = _BODY_RE.search(
        html
    )

    if not match:
        raise SiteBuildError(
            "canonical body element "
            "is missing"
        )

    attrs = (
        match.group(
            "attrs"
        )
        or ""
    )

    if (
        "data-v38-production"
        in attrs
    ):
        raise SiteBuildError(
            "canonical unexpectedly "
            "already contains "
            "production marker"
        )

    replacement = (
        '<body '
        'data-v38-production="live-binding"'
        f"{attrs}>"
    )

    return (
        html[
            : match.start()
        ]
        + replacement
        + html[
            match.end() :
        ]
    )


def build_safe_shell(
    canonical_html: str,
) -> str:
    validate_canonical_shell(
        canonical_html
    )

    original_styles = (
        _style_blocks(
            canonical_html
        )
    )

    out = (
        _strip_active_inline_logic(
            canonical_html
        )
    )

    out = _mark_body_live(
        out
    )

    if not _HEAD_END_RE.search(
        out
    ):
        raise SiteBuildError(
            "head end tag is missing"
        )

    out = _HEAD_END_RE.sub(
        (
            BINDING_STYLE
            + "\n</head>"
        ),
        out,
        count=1,
    )

    if not _BODY_END_RE.search(
        out
    ):
        raise SiteBuildError(
            "body end tag is missing"
        )

    out = _BODY_END_RE.sub(
        (
            RUNTIME_SCRIPTS
            + "\n</body>"
        ),
        out,
        count=1,
    )

    generated_styles = tuple(
        block
        for block
        in _style_blocks(
            out
        )
        if (
            'id="v38-live-binding-bootstrap"'
            not in block
        )
    )

    if (
        generated_styles
        != original_styles
    ):
        raise SiteBuildError(
            "canonical style blocks "
            "changed during build"
        )

    report = (
        validate_production_html(
            out
        )
    )

    if (
        report[
            "external_script_count"
        ]
        != 3
    ):
        raise SiteBuildError(
            "production HTML must "
            "contain exactly three "
            "external scripts"
        )

    if 'v38-production-state' in out:
        raise SiteBuildError(
            "legacy replacement cards "
            "must not be injected"
        )

    if (
        'data-v38-production="live-binding"'
        not in out
    ):
        raise SiteBuildError(
            "live binding "
            "marker missing"
        )

    return out


def build_site(
    canonical_path: str | Path,
    output_path: str | Path,
) -> Path:
    src = Path(
        canonical_path
    )

    raw = src.read_bytes()

    verify_canonical_bytes(
        raw
    )

    try:
        html = raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError as exc:
        raise SiteBuildError(
            "canonical must be UTF-8"
        ) from exc

    out_html = build_safe_shell(
        html
    )

    dst = Path(
        output_path
    )

    dst.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dst.write_text(
        out_html,
        encoding="utf-8",
    )

    return dst
