from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .ui_contract import (
    EXPECTED_TABS,
    validate_canonical_shell,
    validate_production_html,
)

CALCULATION_VERSION = "v38-safe-site-builder-1.1.0"

CANONICAL_BLOB_SHA = "966fe157e3d35344f6e373877b3de5689409dd67"
CANONICAL_SIZE = 1412062

_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.I | re.S)
_EVENT_RE = re.compile(
    r"\s+on[a-zA-Z0-9_-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.I | re.S,
)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.I | re.S)
_BODY_END_RE = re.compile(r"</body\s*>", re.I)

SECTION_IDS = tuple(href[1:] for _, href in EXPECTED_TABS)

RUNTIME_SCRIPTS = (
    '<script src="assets/v38-runtime.js" defer></script>\n'
    '<script src="assets/v38-site.js" defer></script>'
)


class SiteBuildError(RuntimeError):
    pass


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def canonical_fingerprint(data: bytes) -> dict[str, object]:
    return {"size": len(data), "blob_sha": git_blob_sha(data)}


def verify_canonical_bytes(data: bytes) -> None:
    fp = canonical_fingerprint(data)
    if fp["size"] != CANONICAL_SIZE:
        raise SiteBuildError(
            f"canonical size mismatch: {fp['size']} != {CANONICAL_SIZE}"
        )
    if fp["blob_sha"] != CANONICAL_BLOB_SHA:
        raise SiteBuildError(
            f"canonical blob mismatch: {fp['blob_sha']} != {CANONICAL_BLOB_SHA}"
        )


def _style_blocks(html: str) -> tuple[str, ...]:
    return tuple(_STYLE_RE.findall(html))


def _strip_active_inline_logic(html: str) -> str:
    return _EVENT_RE.sub("", _SCRIPT_RE.sub("", html))


def _inert_section_mock(html: str, section_id: str) -> str:
    pattern = re.compile(
        r"(<section\b(?=[^>]*\bid\s*=\s*[\"']"
        + re.escape(section_id)
        + r"[\"'])[^>]*>)(.*?)(</section>)",
        re.I | re.S,
    )

    def replacement(match: re.Match[str]) -> str:
        original = match.group(2)
        live = (
            '<div class="card" role="status" aria-live="polite" '
            f'data-v38-live-section="{section_id}" data-v38-status="DATA_REQUIRED">'
            '<h2>DATA_REQUIRED</h2>'
            '<div class="mut">Authoritative data is loading.</div>'
            '</div>'
        )
        template = (
            f'<template data-v38-canonical-template="{section_id}">'
            f'{original}'
            '</template>'
        )
        return match.group(1) + template + live + match.group(3)

    out, count = pattern.subn(replacement, html, count=1)
    if count != 1:
        raise SiteBuildError(f"section conversion failed: {section_id}")
    return out


def build_safe_shell(canonical_html: str) -> str:
    validate_canonical_shell(canonical_html)
    original_styles = _style_blocks(canonical_html)

    out = _strip_active_inline_logic(canonical_html)
    for section_id in SECTION_IDS:
        out = _inert_section_mock(out, section_id)

    if not _BODY_END_RE.search(out):
        raise SiteBuildError("body end tag is missing")
    out = _BODY_END_RE.sub(RUNTIME_SCRIPTS + "\n</body>", out, count=1)

    if _style_blocks(out) != original_styles:
        raise SiteBuildError("canonical style blocks changed during build")

    report = validate_production_html(out)
    if report["external_script_count"] != 2:
        raise SiteBuildError(
            "production HTML must contain exactly two external scripts"
        )
    if out.count("data-v38-live-section=") != len(SECTION_IDS):
        raise SiteBuildError("all nine sections must have one live canonical surface")
    if out.count("data-v38-canonical-template=") != len(SECTION_IDS):
        raise SiteBuildError("all nine canonical section bodies must be inert templates")
    if "v38-production-shield" in out or "v38-production-state" in out:
        raise SiteBuildError("legacy replacement UI must not be emitted")
    return out


def build_site(canonical_path: str | Path, output_path: str | Path) -> Path:
    src = Path(canonical_path)
    raw = src.read_bytes()
    verify_canonical_bytes(raw)
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SiteBuildError("canonical must be UTF-8") from exc

    out_html = build_safe_shell(html)
    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out_html, encoding="utf-8")
    return dst
