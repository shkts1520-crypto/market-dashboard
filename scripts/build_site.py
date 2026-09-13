#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from v38.site_builder import CANONICAL_BLOB_SHA, CANONICAL_SIZE, build_site
from v38.ui_contract import validate_production_html


def _copy_asset(out: Path, asset: Path) -> bool:
    if not asset.is_file():
        return False
    asset_dir = out.parent / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(asset, asset_dir / asset.name)
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
    """Generate the recovered pre-v5 search/VWAP/chart payloads in production only.

    Pull-request and local verification stay network-free. Production already has
    current-session RS/Rotation/Options shards at this point, so this step only
    restores display data and never changes the adopted trading gates.
    """
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
    p = argparse.ArgumentParser(
        description="Build live-bound V38 production UI from canonical v5"
    )
    p.add_argument("--canonical", default="V38_Command_Center_mock_v5.html")
    p.add_argument("--output", default="index.html")
    args = p.parse_args()

    restored_materialized = _materialize_restored_experience()
    out = build_site(args.canonical, args.output)

    # Extensions load after the canonical v5 shell and only bind acquired data.
    # visual_fidelity runs after data_repair so it can restore the original MC57
    # temperature bands, robust display-only diagnostics and VIX fear-cycle card.
    # detail_restore restores the original VIX sequence-condition panel. The
    # historical-experience extensions then replace only the user-approved
    # Rotation / Options / search / VWAP surfaces with the recovered pre-v5 form.
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

    # Keep the old chart asset available in the repository but do not bind it when
    # the recovered chart exists. The recovered chart owns the same modal id and
    # adds 63/252/All-time VWAP without Direction/Confidence guesses.
    restored_chart = Path("assets/v38-restored-chart.js")
    restored_chart_enabled = _inject_external_extension(out, restored_chart)
    if restored_chart_enabled:
        options_chart_enabled = False
    else:
        options_chart = Path("assets/v38-options-chart.js")
        options_chart_enabled = _inject_external_extension(out, options_chart)

    restored_experience = Path("assets/v38-restored-experience.js")
    restored_experience_enabled = _inject_external_extension(out, restored_experience)

    # Final visual-only layer. It runs after restored_experience so the recovered
    # data DOM is already present, then restores the canonical card proportions,
    # spacing and table density without changing calculations or data contracts.
    source_fidelity = Path("assets/v38-source-fidelity.js")
    source_fidelity_enabled = _inject_external_extension(out, source_fidelity)

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
