#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.market_engine import calculate_market_from_files
from v38.recovered_live_inputs import write_recovered_inputs


def main() -> int:
    p = argparse.ArgumentParser(description="Materialize recovered V38 live inputs without restoring obsolete trading rules")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--work-dir", default="")
    p.add_argument("--no-fundamentals", action="store_true")
    a = p.parse_args()

    root = Path(a.data_dir)
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    generated_at = str(state["generated_at"])
    work = Path(a.work_dir) if a.work_dir else None
    ohlcv = work / "ohlcv.csv" if work and (work / "ohlcv.csv").is_file() else None

    paths = write_recovered_inputs(
        data_dir=root,
        ohlcv_path=ohlcv,
        generated_at=generated_at,
        fetch_fundamentals=not a.no_fundamentals,
    )
    market_state, core12 = calculate_market_from_files(
        root / "rs.json",
        root / "breadth.json",
        root / "nqsar.json",
        root,
        generated_at=generated_at,
        classifications_path=root / "classifications.json",
        theme_scores_path=root / "theme_scores.json",
    )
    nqsar = json.loads((root / "nqsar.json").read_text(encoding="utf-8"))
    classifications = json.loads((root / "classifications.json").read_text(encoding="utf-8"))
    themes = json.loads((root / "theme_scores.json").read_text(encoding="utf-8"))
    market = json.loads(market_state.read_text(encoding="utf-8"))
    core = json.loads(core12.read_text(encoding="utf-8"))
    print(json.dumps({
        "session_date": state["session_date"],
        "nqsar": nqsar.get("state"),
        "nqsar_input_kind": nqsar.get("input_kind"),
        "classification_rows": len(classifications.get("rows") or []),
        "theme_rows": len(themes.get("rows") or []),
        "display_rotation_groups": len(themes.get("theme_groups") or []),
        "market_mode": market.get("market_mode"),
        "core12_status": core.get("status"),
        "outputs": [str(path) for path in paths] + [str(market_state), str(core12)],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
