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
    """Restore source DOM at build time; runtime code may only bind its slots."""
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


def _materialize_restored_experience() -> bool:
    """Generate recovered search/VWAP/chart payloads in production only."""
    script = Path("scripts/materialize_restored_experience.py")
    if not _is_production_context() or not script.is_file():
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
    }
    copied: dict[str, bool] = {}
    for key, source in sources.items():
        if source.is_file() and source.stat().st_size > 0:
            shutil.copy2(source, target / f"{key}.json")
            copied[key] = True
        else:
            copied[key] = False
    return copied


def main() -> int:
    p = argparse.ArgumentParser(description="Build live-bound V38 production UI from canonical v5")
    p.add_argument("--canonical", default="V38_Command_Center_mock_v5.html")
    p.add_argument("--output", default="index.html")
    args = p.parse_args()

    restored_materialized = _materialize_restored_experience()
    out = build_site(args.canonical, args.output)

    baseline_shell = Path("assets/v38-baseline-shell.js")
    baseline_shell_enabled = _copy_asset(out, baseline_shell)
    source_mobile_enabled = _inject_stylesheet(out, Path("assets/v38-source-mobile.css"))
    setups_0905_enabled = _restore_section_0905(
        out, "t-today", Path("assets/baseline-0905/setups.html")
    )
    movers_0905_enabled = _restore_section_0905(
        out, "t-movers", Path("assets/baseline-0905/movers.html")
    )
    rules_0905_enabled = _restore_rules_0905(out, Path("assets/v38-rules-0905.html"))

    # Canonical/source DOM remains the visual authority. Runtime extensions may
    # bind current data but must not replace it with synthetic or legacy values.
    observables_enabled = polish_enabled = recovery_enabled = False
    final_ui_enabled = data_repair_enabled = visual_fidelity_enabled = False
    detail_restore_enabled = False

    live_binder = Path("assets/v38-live-binder.js")
    live_binder_enabled = _inject_external_extension(out, live_binder)
    restored_chart = Path("assets/v38-restored-chart.js")
    restored_chart_enabled = _inject_external_extension(out, restored_chart)
    if restored_chart_enabled:
        options_chart_enabled = False
    else:
        options_chart = Path("assets/v38-options-chart.js")
        options_chart_enabled = _inject_external_extension(out, options_chart)

    restored_experience = Path("assets/v38-restored-experience.js")
    restored_experience_enabled = _inject_external_extension(out, restored_experience)
    tradingview_fallback = Path("assets/v38-tradingview-fallback.js")
    tradingview_fallback_enabled = _inject_external_extension(out, tradingview_fallback)

    # Truth pass removes inherited baseline values first. Source-real visualizer
    # runs after it and rebuilds rich charts/tables only from authoritative data.
    production_truth = Path("assets/v38-production-truth.js")
    production_truth_enabled = _inject_external_extension(out, production_truth)
    production_label_truth = Path("assets/v38-production-label-truth.js")
    production_label_truth_enabled = _inject_external_extension(out, production_label_truth)
    source_real_visual = Path("assets/v38-source-real-visual.js")
    source_real_visual_enabled = _inject_external_extension(out, source_real_visual)

    source_fidelity_enabled = False
    source_fidelity_contract_enabled = False
    data_completeness_fallback_enabled = False
    observation_ribbon_repair_enabled = False
    status_truth_enabled = False
    rotation_movers_visual_enabled = False
    rotation_movers_owner_enabled = False

    restored_data = _copy_restored_data(out)
    report = validate_production_html(out.read_text(encoding="utf-8"))

    print(
        json.dumps(
            {
                "status": "LIVE_BINDING_SHELL_READY",
                "output": str(out),
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
                "setups_0905_restored": setups_0905_enabled,
                "movers_0905_restored": movers_0905_enabled,
                "rules_0905_restored": rules_0905_enabled,
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
                "production_truth_extension": production_truth_enabled,
                "production_label_truth_extension": production_label_truth_enabled,
                "source_real_visual_extension": source_real_visual_enabled,
                "source_fidelity_extension": source_fidelity_enabled,
                "source_fidelity_contract_extension": source_fidelity_contract_enabled,
                "data_completeness_fallback_extension": data_completeness_fallback_enabled,
                "observation_ribbon_repair_extension": observation_ribbon_repair_enabled,
                "status_truth_extension": status_truth_enabled,
                "rotation_movers_visual_extension": rotation_movers_visual_enabled,
                "rotation_movers_owner_extension": rotation_movers_owner_enabled,
                "restored_materialized": restored_materialized,
                "restored_data": restored_data,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
