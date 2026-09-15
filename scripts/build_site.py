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
    rules_0905_enabled = _restore_rules_0905(out, Path("assets/v38-rules-0905.html"))

    # The canonical v5 HTML/CSS is the visual authority. Extensions below may
    # bind live values or add user-approved post-09/05 features, but they must not
    # rebuild the page geometry. Each extension is injected exactly once here.
    observables = Path("assets/v38-observables.js")
    observables_enabled = _inject_external_extension(out, observables)
    polish = Path("assets/v38-polish.js")
    polish_enabled = _inject_external_extension(out, polish)
    recovery = Path("assets/v38-recovery.js")
    recovery_enabled = _inject_external_extension(out, recovery)
    final_ui = Path("assets/v38-final-ui.js")
    final_ui_enabled = _inject_external_extension(out, final_ui)
    data_repair = Path("assets/v38-data-repair.js")
    data_repair_enabled = _inject_external_extension(out, data_repair)
    visual_fidelity = Path("assets/v38-visual-fidelity.js")
    visual_fidelity_enabled = _inject_external_extension(out, visual_fidelity)
    detail_restore = Path("assets/v38-detail-restore.js")
    detail_restore_enabled = _inject_external_extension(out, detail_restore)

    # Recovered in-page chart is the only chart-modal implementation when present.
    restored_chart = Path("assets/v38-restored-chart.js")
    restored_chart_enabled = _inject_external_extension(out, restored_chart)
    if restored_chart_enabled:
        options_chart_enabled = False
    else:
        options_chart = Path("assets/v38-options-chart.js")
        options_chart_enabled = _inject_external_extension(out, options_chart)

    restored_experience = Path("assets/v38-restored-experience.js")
    restored_experience_enabled = _inject_external_extension(out, restored_experience)

    # Fixed 1680x1080 rewrite remains quarantined.
    source_fidelity_enabled = False
    source_fidelity_contract_enabled = False

    data_completeness_fallback = Path("assets/v38-data-completeness-fallback.js")
    data_completeness_fallback_enabled = _inject_external_extension(out, data_completeness_fallback)

    observation_ribbon_repair = Path("assets/v38-observation-ribbon-repair.js")
    observation_ribbon_repair_enabled = _inject_external_extension(out, observation_ribbon_repair)

    status_truth = Path("assets/v38-status-truth.js")
    status_truth_enabled = _inject_external_extension(out, status_truth)

    # Final, tightly scoped visual owner for only Rotation and Movers. It captures
    # the canonical Rotation DOM before generic binders can neutralize it, restores
    # that shell after live binding, and renders Movers with the source mv-* structure.
    rotation_movers_visual = Path("assets/v38-rotation-movers-visual.js")
    rotation_movers_visual_enabled = _inject_external_extension(out, rotation_movers_visual)

    # Legacy restored-experience intentionally re-renders Rotation several times
    # after DOMContentLoaded. Keep the approved Rotation/Movers rendering stable
    # through that legacy retry window without changing any other tab.
    rotation_movers_owner = Path("assets/v38-rotation-movers-owner.js")
    rotation_movers_owner_enabled = _inject_external_extension(out, rotation_movers_owner)

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
                "rules_0905_restored": rules_0905_enabled,
                "observables_extension": observables_enabled,
                "polish_extension": polish_enabled,
                "recovery_extension": recovery_enabled,
                "final_ui_extension": final_ui_enabled,
                "data_repair_extension": data_repair_enabled,
                "visual_fidelity_extension": visual_fidelity_enabled,
                "detail_restore_extension": detail_restore_enabled,
                "options_chart_extension": options_chart_enabled,
                "restored_chart_extension": restored_chart_enabled,
                "restored_experience_extension": restored_experience_enabled,
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
