#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from v38.site_builder import CANONICAL_BLOB_SHA, CANONICAL_SIZE, build_site
from v38.ui_contract import validate_production_html


_RULES_SECTION = re.compile(r'(<section[^>]+id="t-rules"[^>]*>).*?(</section>)', re.DOTALL)


def _restore_section_0905(out: Path, section_id: str, fragment: Path) -> bool:
    """Keep recovered DOM slots; visual authority is applied later from build_dashboard(2).py."""
    if not fragment.is_file():
        return False
    source = out.read_text(encoding="utf-8")
    body = fragment.read_text(encoding="utf-8").strip()
    body = re.sub(r'\s+on[a-z]+="[^"]*"', "", body, flags=re.IGNORECASE)
    section = re.compile(
        rf'(<section[^>]+id="{re.escape(section_id)}"[^>]*>).*?(</section>)',
        re.DOTALL,
    )
    restored, count = section.subn(
        lambda match: match.group(1) + body + match.group(2), source, count=1
    )
    if count != 1:
        raise RuntimeError(f"09/05 {section_id} section was not found in production shell")
    out.write_text(restored, encoding="utf-8")
    return True


def _restore_rules_0905(out: Path, fragment: Path) -> bool:
    if not fragment.is_file():
        return False
    source = out.read_text(encoding="utf-8")
    body = fragment.read_text(encoding="utf-8").strip()
    restored, count = _RULES_SECTION.subn(lambda match: match.group(1) + body + match.group(2), source, count=1)
    if count != 1:
        raise RuntimeError("09/05 Rules section was not found in production shell")
    out.write_text(restored, encoding="utf-8")
    return True


def _copy_asset(out: Path, asset: Path) -> bool:
    if not asset.is_file():
        return False
    asset_dir = out.parent / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / asset.name
    if asset.resolve() == target.resolve():
        return True
    shutil.copy2(asset, target)
    return True


def _inject_external_extension(out: Path, asset: Path) -> bool:
    if not _copy_asset(out, asset):
        return False
    html = out.read_text(encoding="utf-8")
    marker = f'<script src="assets/{asset.name}" defer></script>'
    if marker not in html:
        if "</body>" not in html:
            raise RuntimeError("production body end tag is missing")
        html = html.replace("</body>", marker + "\n</body>", 1)
        out.write_text(html, encoding="utf-8")
    return True


def _inject_stylesheet(out: Path, asset: Path) -> bool:
    if not _copy_asset(out, asset):
        return False
    html = out.read_text(encoding="utf-8")
    marker = f'<link rel="stylesheet" href="assets/{asset.name}">'
    if marker not in html:
        html = html.replace("</head>", marker + "\n</head>", 1)
        out.write_text(html, encoding="utf-8")
    return True


def _is_production_context() -> bool:
    event = str(os.environ.get("GITHUB_EVENT_NAME") or "").strip().lower()
    return event not in {"", "pull_request", "pull_request_target"}


def _run_materializer(script_name: str) -> bool:
    script = Path("scripts") / script_name
    if not _is_production_context() or not script.is_file():
        return False
    subprocess.run(
        [sys.executable, str(script), "--data-dir", "data"]
        if script_name == "materialize_restored_experience.py"
        else [sys.executable, str(script)],
        check=True,
        env=os.environ.copy(),
    )
    return True


def _run_py_source_display_materializer() -> bool:
    """Display-only adapter. Safe in PR builds; never mutates trading calculations."""
    script = Path("scripts/materialize_py_source_display.py")
    if not script.is_file():
        return False
    subprocess.run(
        [sys.executable, str(script), "--data-dir", "data"],
        check=True,
        env=os.environ.copy(),
    )
    return True


def _copy_restored_data(out: Path) -> dict[str, bool]:
    target = out.parent / "data"
    target.mkdir(parents=True, exist_ok=True)
    sources = {
        "search_index": Path("data/history/search_index.json"),
        "vwap_restore": Path("data/history/vwap_restore.json"),
        "setup_restore": Path("data/history/setup_restore.json"),
        "py_source_display": Path("data/py_source_display.json"),
    }
    copied: dict[str, bool] = {}
    for key, source in sources.items():
        if source.is_file() and source.stat().st_size > 0:
            destination = target / f"{key}.json"
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            copied[key] = True
        else:
            copied[key] = False
    return copied


def main() -> int:
    p = argparse.ArgumentParser(description="Build live-bound V38 production UI; build_dashboard(2).py owns every non-options display")
    p.add_argument("--canonical", default="V38_Command_Center_mock_v5.html")
    p.add_argument("--output", default="index.html")
    args = p.parse_args()

    recency_validated = _run_materializer("validate_benchmark_recency.py")
    restored_materialized = _run_materializer("materialize_restored_experience.py")
    setup_materialized = _run_materializer("materialize_setup_cards.py")
    py_source_display_materialized = _run_py_source_display_materializer()
    out = build_site(args.canonical, args.output)

    baseline_shell_enabled = _copy_asset(out, Path("assets/v38-baseline-shell.js"))
    # Keep containment/navigation behavior required by the current Options implementation.
    source_mobile_enabled = _inject_stylesheet(out, Path("assets/v38-source-mobile.css"))
    # The old fidelity stylesheet reinterpreted the py source; it is intentionally disabled.
    source_fidelity_css_enabled = False
    py_source_css_enabled = _inject_stylesheet(out, Path("assets/v38-py-source-authority.css"))
    py_source_guard_enabled = _inject_stylesheet(out, Path("assets/v38-py-source-guard.css"))
    py_source_finalizer_css_enabled = _inject_stylesheet(out, Path("assets/v38-py-source-finalizer.css"))

    # These recovered fragments remain only as data-binding DOM slots. Their visual authority
    # is removed by v38-py-source-authority.js/css after the live binder has populated them.
    setups_0905_enabled = _restore_section_0905(out, "t-today", Path("assets/baseline-0905/setups.html"))
    movers_0905_enabled = _restore_section_0905(out, "t-movers", Path("assets/baseline-0905/movers.html"))
    rules_0905_enabled = _restore_rules_0905(out, Path("assets/v38-rules-0905.html"))

    observables_enabled = polish_enabled = recovery_enabled = False
    final_ui_enabled = data_repair_enabled = visual_fidelity_enabled = False
    detail_restore_enabled = False

    live_binder_enabled = False
    restored_experience_enabled = False
    production_truth_enabled = False
    production_label_truth_enabled = False
    public_final_enabled = False
    canonical_binder_enabled = _inject_external_extension(out, Path("assets/v38-canonical-binder.js"))
    restored_chart_enabled = _inject_external_extension(out, Path("assets/v38-restored-chart.js"))
    options_chart_enabled = False if restored_chart_enabled else _inject_external_extension(out, Path("assets/v38-options-chart.js"))
    tradingview_fallback_enabled = _inject_external_extension(out, Path("assets/v38-tradingview-fallback.js"))
    public_labels_enabled = _inject_external_extension(out, Path("assets/v38-public-labels.js"))
    # The previous visual-polish layer is disabled: it must not redesign the py-source UI.
    visual_polish_enabled = False
    # Broad source-py structure is applied first. The finalizer below waits for the canonical
    # binder to finish and then owns the specialized source cards so async binders cannot overwrite them.
    py_source_authority_enabled = _inject_external_extension(out, Path("assets/v38-py-source-authority.js"))
    # Positions keeps the source hierarchy while binding only current V38 live cards.
    py_source_positions_enabled = _inject_external_extension(out, Path("assets/v38-py-source-positions.js"))
    # Must be last: wait for canonical binder completion, then finalize Regime/VIX/FTD/Rules.
    py_source_finalizer_enabled = _inject_external_extension(out, Path("assets/v38-py-source-finalizer.js"))

    source_fidelity_enabled = False
    source_fidelity_contract_enabled = False
    data_completeness_fallback_enabled = False
    observation_ribbon_repair_enabled = False
    status_truth_enabled = False
    rotation_movers_visual_enabled = False
    rotation_movers_owner_enabled = False

    restored_data = _copy_restored_data(out)
    report = validate_production_html(out.read_text(encoding="utf-8"))

    print(json.dumps({
        "status": "PY_SOURCE_UI_READY",
        "output": str(out),
        "ui_authority": "build_dashboard(2).py",
        "ui_authority_scope": "all_non_options_tabs",
        "options_ui_authority": "current_options_implementation",
        "trading_logic_changed": False,
        "canonical_blob_sha": CANONICAL_BLOB_SHA,
        "canonical_size": CANONICAL_SIZE,
        "tabs": [label for label, _ in report["tabs"]],
        "inline_script_count": report["inline_script_count"],
        "inline_event_handler_count": report["inline_event_handler_count"],
        "external_script_count": report["external_script_count"],
        "canonical_dom_preserved": True,
        "legacy_replacement_cards": False,
        "baseline_0905_shell": baseline_shell_enabled,
        "source_mobile_styles": source_mobile_enabled,
        "source_fidelity_css": source_fidelity_css_enabled,
        "py_source_css": py_source_css_enabled,
        "py_source_guard": py_source_guard_enabled,
        "py_source_finalizer_css": py_source_finalizer_css_enabled,
        "py_source_authority": py_source_authority_enabled,
        "py_source_positions": py_source_positions_enabled,
        "py_source_finalizer": py_source_finalizer_enabled,
        "py_source_display_materialized": py_source_display_materialized,
        "setups_0905_restored_as_slots": setups_0905_enabled,
        "movers_0905_restored_as_slots": movers_0905_enabled,
        "rules_0905_restored_as_slots": rules_0905_enabled,
        "observables_extension": observables_enabled,
        "polish_extension": polish_enabled,
        "recovery_extension": recovery_enabled,
        "final_ui_extension": final_ui_enabled,
        "data_repair_extension": data_repair_enabled,
        "visual_fidelity_extension": visual_fidelity_enabled,
        "detail_restore_extension": detail_restore_enabled,
        "live_binder_extension": live_binder_enabled,
        "options_chart_extension": options_chart_enabled,
        "restored_chart_extension": restored_chart_enabled,
        "restored_experience_extension": restored_experience_enabled,
        "tradingview_fallback_extension": tradingview_fallback_enabled,
        "public_labels_extension": public_labels_enabled,
        "production_truth_extension": production_truth_enabled,
        "production_label_truth_extension": production_label_truth_enabled,
        "public_final_extension": public_final_enabled,
        "canonical_binder_extension": canonical_binder_enabled,
        "source_fidelity_extension": source_fidelity_enabled,
        "visual_polish_extension": visual_polish_enabled,
        "source_fidelity_contract_extension": source_fidelity_contract_enabled,
        "data_completeness_fallback_extension": data_completeness_fallback_enabled,
        "observation_ribbon_repair_extension": observation_ribbon_repair_enabled,
        "status_truth_extension": status_truth_enabled,
        "rotation_movers_visual_extension": rotation_movers_visual_enabled,
        "rotation_movers_owner_extension": rotation_movers_owner_enabled,
        "recency_validated": recency_validated,
        "restored_materialized": restored_materialized,
        "setup_materialized": setup_materialized,
        "restored_data": restored_data,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
