from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

CALCULATION_VERSION = "v38-market-engine-1.0.0"
MARKET_STATE_SCHEMA_VERSION = "v38.market_state.1"
CORE12_SCHEMA_VERSION = "v38.core12.1"
VALID_NQSAR = {"Blue", "Green", "Yellow", "Red"}


class MarketEngineError(RuntimeError):
    """Raised when a required V38 data contract is violated."""


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise MarketEngineError(f"input not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise MarketEngineError(f"expected JSON object: {p}")
    return obj


def _finite(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        if math.isfinite(x):
            return x
    return None


def _bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and v in (0, 1):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y"}:
            return True
        if s in {"false", "0", "no", "n"}:
            return False
    return None


def _meta_session(obj: dict[str, Any], label: str) -> str:
    s = obj.get("session_date")
    if not isinstance(s, str) or len(s) != 10:
        raise MarketEngineError(f"{label}.session_date is required")
    return s


def _require_same_session(items: list[tuple[str, dict[str, Any]]]) -> str:
    sessions = {label: _meta_session(obj, label) for label, obj in items}
    uniq = sorted(set(sessions.values()))
    if len(uniq) != 1:
        detail = ", ".join(f"{k}={v}" for k, v in sessions.items())
        raise MarketEngineError(f"STALE shard session mismatch: {detail}")
    return uniq[0]


def _nqsar_state(nqsar: dict[str, Any]) -> str:
    state = nqsar.get("state", nqsar.get("color", nqsar.get("nqsar")))
    if state not in VALID_NQSAR:
        raise MarketEngineError("nqsar.state must be one of Blue/Green/Yellow/Red")
    return str(state)


def determine_market_mode(nqsar_state: str, breadth50: float | None) -> tuple[str, int, str]:
    if nqsar_state == "Red":
        return "DEFENSE", 0, "NQSAR_RED"
    if nqsar_state == "Yellow":
        return "STOP", 0, "NQSAR_YELLOW"
    if breadth50 is None:
        return "DATA_REQUIRED", 0, "BREADTH50_MISSING"
    if breadth50 >= 60.0:
        return "ATTACK", 12, "BLUE_GREEN_BREADTH_GE_60"
    if breadth50 >= 50.0:
        return "SELECTIVE", 4, "BLUE_GREEN_BREADTH_50_60"
    return "STOP", 0, "BLUE_GREEN_BREADTH_LT_50"


def _classification_map(classifications: dict[str, Any] | None) -> tuple[dict[str, bool], dict[str, Any]]:
    if classifications is None:
        return {}, {"status": "DATA_REQUIRED", "reason": "CLASSIFICATION_INPUT_MISSING"}
    rows = classifications.get("rows")
    if not isinstance(rows, list):
        raise MarketEngineError("classifications.rows must be a list")
    out: dict[str, bool] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        flag = _bool(row.get("structural_clinical_biotech"))
        if flag is None:
            continue
        out[ticker] = flag
    meta = {
        "status": "OK",
        "source": classifications.get("source"),
        "classification_version": classifications.get("classification_version", classifications.get("version")),
        "coverage": classifications.get("coverage"),
    }
    return out, meta


def _theme_map(theme_scores: dict[str, Any] | None) -> tuple[dict[str, float], dict[str, Any]]:
    if theme_scores is None:
        return {}, {"status": "DATA_REQUIRED", "reason": "PEER_THEME_INPUT_MISSING"}
    rows = theme_scores.get("rows")
    if not isinstance(rows, list):
        raise MarketEngineError("theme_scores.rows must be a list")
    out: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker", "")).strip().upper()
        val = _finite(row.get("peer_theme_score"))
        if ticker and val is not None:
            out[ticker] = val
    return out, {
        "status": "OK",
        "source": theme_scores.get("source"),
        "calculation_version": theme_scores.get("calculation_version"),
        "loo_required": True,
        "coverage": theme_scores.get("coverage"),
    }


def calculate_market_outputs(
    rs: dict[str, Any],
    breadth: dict[str, Any],
    nqsar: dict[str, Any],
    *,
    classifications: dict[str, Any] | None = None,
    theme_scores: dict[str, Any] | None = None,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    session_date = _require_same_session([("rs", rs), ("breadth", breadth), ("nqsar", nqsar)])
    if classifications is not None:
        _require_same_session([("rs", rs), ("classifications", classifications)])
    if theme_scores is not None:
        _require_same_session([("rs", rs), ("theme_scores", theme_scores)])
    if not generated_at:
        raise MarketEngineError("generated_at is required")

    nq = _nqsar_state(nqsar)
    b50 = _finite(breadth.get("breadth50"))
    mode, max_slots, mode_reason = determine_market_mode(nq, b50)

    common = {
        "session_date": session_date,
        "generated_at": generated_at,
        "calculation_version": CALCULATION_VERSION,
    }
    market_state = {
        **common,
        "schema_version": MARKET_STATE_SCHEMA_VERSION,
        "source": "derived:rs+breadth+nqsar",
        "coverage": min(
            x for x in [
                _finite(rs.get("coverage")),
                _finite(breadth.get("coverage")),
                _finite(nqsar.get("coverage")),
            ]
            if x is not None
        ) if any(_finite(x.get("coverage")) is not None for x in (rs, breadth, nqsar)) else None,
        "nqsar": nq,
        "breadth50": b50,
        "breadth200": _finite(breadth.get("breadth200")),
        "market_mode": mode,
        "max_new_total_slots": max_slots,
        "normal_stock_target_max_pct": 70,
        "tqqq_normal_target_pct": 30,
        "mode_reason": mode_reason,
        "rules": {
            "attack": "Blue/Green + Breadth50>=60 -> max 12",
            "selective": "Blue/Green + 50<=Breadth50<60 -> max 4",
            "stop": "Yellow or Blue/Green + Breadth50<50 -> new 0",
            "defense": "Red -> new 0 and normal stocks exit next open",
            "selective_forced_trim": False,
            "mc57_hard_gate": False,
            "f123_hard_gate": False,
        },
    }

    class_map, class_meta = _classification_map(classifications)
    theme_map, theme_meta = _theme_map(theme_scores)
    rs_rows = rs.get("rows")
    if not isinstance(rs_rows, list):
        raise MarketEngineError("rs.rows must be a list")

    assessed: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    unresolved_classification: list[str] = []
    for raw in rs_rows:
        if not isinstance(raw, dict):
            continue
        ticker = str(raw.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        price = _finite(raw.get("price"))
        ddv20 = _finite(raw.get("ddv20"))
        sma50 = _finite(raw.get("sma50"))
        sma200 = _finite(raw.get("sma200"))
        rs63 = _finite(raw.get("rs63"))
        rs189 = _finite(raw.get("rs189"))
        reasons: list[str] = []
        data_required: list[str] = []
        if price is None or price < 5.0:
            reasons.append("PRICE_LT_5_OR_MISSING")
        if ddv20 is None or ddv20 < 10_000_000.0:
            reasons.append("DDV20_LT_10M_OR_MISSING")
        if sma50 is None or sma200 is None or not (sma50 > sma200):
            reasons.append("SMA50_NOT_GT_SMA200_OR_MISSING")
        if price is None or sma200 is None or not (price > sma200):
            reasons.append("CLOSE_NOT_GT_SMA200_OR_MISSING")
        if rs189 is None or rs189 < 85.0:
            reasons.append("RS189_LT_85_OR_MISSING")
        if rs63 is None or rs63 < 85.0:
            reasons.append("RS63_LT_85_OR_MISSING")
        if ticker not in class_map:
            data_required.append("STRUCTURAL_CLINICAL_BIOTECH_CLASSIFICATION_MISSING")
            unresolved_classification.append(ticker)
        elif class_map[ticker]:
            reasons.append("STRUCTURAL_CLINICAL_BIOTECH")

        status = "DATA_REQUIRED" if data_required else ("ELIGIBLE" if not reasons else "INELIGIBLE")
        row = {
            "ticker": ticker,
            "eligibility_status": status,
            "eligibility_reasons": reasons,
            "data_required": data_required,
            "price": price,
            "ddv20": ddv20,
            "sma50": sma50,
            "sma200": sma200,
            "rs63": rs63,
            "rs126": _finite(raw.get("rs126")),
            "rs189": rs189,
        }
        assessed.append(row)
        if status == "ELIGIBLE":
            eligible.append(row.copy())

    ranking_status = "OK"
    ranking_reason = None
    ranking: list[dict[str, Any]] = []
    if mode == "DATA_REQUIRED":
        ranking_status = "DATA_REQUIRED"
        ranking_reason = "MARKET_MODE_UNRESOLVED"
    elif unresolved_classification:
        ranking_status = "DATA_REQUIRED"
        ranking_reason = "CLASSIFICATION_COVERAGE_INCOMPLETE"
    elif mode == "ATTACK":
        missing_theme = [r["ticker"] for r in eligible if r["ticker"] not in theme_map]
        if missing_theme:
            ranking_status = "DATA_REQUIRED"
            ranking_reason = "PEER_THEME_COVERAGE_INCOMPLETE"
        else:
            for row in eligible:
                score = 0.70 * float(row["rs189"]) + 0.30 * theme_map[row["ticker"]]
                out = row.copy()
                out["peer_theme_score"] = theme_map[row["ticker"]]
                out["final_score"] = score
                ranking.append(out)
            ranking.sort(key=lambda r: (-float(r["final_score"]), -float(r["rs189"]), r["ticker"]))
            ranking = ranking[:12]
    else:
        # Selective is RS189-only. Stop/Defense still expose the same diagnostic order,
        # but max_new_total_slots=0 ensures it is not an entry instruction.
        for row in eligible:
            out = row.copy()
            out["peer_theme_score"] = None
            out["final_score"] = float(row["rs189"])
            ranking.append(out)
        ranking.sort(key=lambda r: (-float(r["rs189"]), r["ticker"]))
        if mode == "SELECTIVE":
            ranking = ranking[:4]

    core12 = {
        **common,
        "schema_version": CORE12_SCHEMA_VERSION,
        "source": "derived:rs+classification+peer_theme",
        "coverage": rs.get("coverage"),
        "market_mode": mode,
        "max_new_total_slots": max_slots,
        "ranking_status": ranking_status,
        "ranking_reason": ranking_reason,
        "ranking": ranking,
        "eligible_count": len(eligible),
        "assessed": sorted(assessed, key=lambda r: r["ticker"]),
        "dependencies": {
            "classification": class_meta,
            "peer_theme": theme_meta,
        },
        "rules": {
            "eligibility": "Price>=5 AND DDV20>=10M AND SMA50>SMA200 AND Close>SMA200 AND RS189>=85 AND RS63>=85 AND NOT StructuralClinicalBiotech",
            "attack_final": "0.70*RS189 + 0.30*PeerThemeScore",
            "selective_final": "RS189 only",
            "attack_tiebreak": "final desc, RS189 desc, ticker asc",
            "selective_tiebreak": "RS189 desc, ticker asc",
            "rank_decline_exit": False,
            "theme_decline_exit": False,
        },
    }
    return market_state, core12


def _atomic_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def calculate_market_from_files(
    rs_path: str | Path,
    breadth_path: str | Path,
    nqsar_path: str | Path,
    output_dir: str | Path,
    *,
    generated_at: str,
    classifications_path: str | Path | None = None,
    theme_scores_path: str | Path | None = None,
) -> tuple[Path, Path]:
    outputs = calculate_market_outputs(
        load_json(rs_path),
        load_json(breadth_path),
        load_json(nqsar_path),
        classifications=load_json(classifications_path) if classifications_path else None,
        theme_scores=load_json(theme_scores_path) if theme_scores_path else None,
        generated_at=generated_at,
    )
    out = Path(output_dir)
    market_path = out / "market_state.json"
    core12_path = out / "core12.json"
    _atomic_json(market_path, outputs[0])
    _atomic_json(core12_path, outputs[1])
    return market_path, core12_path
