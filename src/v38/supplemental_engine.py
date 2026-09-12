from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .freshness import DATA_REQUIRED, READY, STALE, assess_shard_file, atomic_write_json
from .positions_engine import PositionsRuleError, normal_stock_next_open_action

CALCULATION_VERSION = "v38-supplemental-engine-1.0.1"
VALID_NQSAR = {"Blue", "Green", "Yellow", "Red"}

SCHEMAS = {
    "rules": "v38.rules.1",
    "weekly": "v38.weekly.1",
    "rotation": "v38.rotation.1",
    "positions": "v38.positions.1",
    "publish": "v38.publish.1",
    "placeholder": "v38.data_required.1",
}

PUBLISH_INPUTS = (
    "market_state.json",
    "breadth.json",
    "mc57.json",
    "f123.json",
    "core12.json",
    "positions.json",
    "rotation.json",
    "rs.json",
    "weekly.json",
    "options/index.json",
    "rules.json",
)


class SupplementalEngineError(RuntimeError):
    pass


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    return None


def _load(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _same_session(obj: dict[str, Any] | None, session_date: str) -> bool:
    return bool(obj is not None and obj.get("session_date") == session_date)


def _base(
    *,
    session_date: str,
    generated_at: str,
    coverage: float | None,
    source: str,
    schema_version: str,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": coverage,
        "source": source,
        "schema_version": schema_version,
        "calculation_version": CALCULATION_VERSION,
        "status": status,
    }
    if reason:
        out["reason"] = reason
    return out


def data_required_shard(
    *,
    session_date: str,
    generated_at: str,
    source: str,
    reason: str,
    dependency: str,
) -> dict[str, Any]:
    return {
        **_base(
            session_date=session_date,
            generated_at=generated_at,
            coverage=None,
            source=source,
            schema_version=SCHEMAS["placeholder"],
            status=DATA_REQUIRED,
            reason=reason,
        ),
        "dependency": dependency,
        "value": None,
    }


def build_rules_shard(*, session_date: str, generated_at: str) -> dict[str, Any]:
    """Expose only already-adopted V38 contracts; no market value is calculated here."""
    return {
        **_base(
            session_date=session_date,
            generated_at=generated_at,
            coverage=1.0,
            source="code:adopted-v38-contracts",
            schema_version=SCHEMAS["rules"],
            status=READY,
        ),
        "rules": {
            "allocation": {
                "normal_tqqq_pct": 30,
                "normal_stock_max_pct": 70,
                "gross_max_pct": 100,
                "panic_tqqq_target_pct": 80,
                "panic_reset_per_name_pct": 2.9,
                "panic_reset_max_names": 4,
                "gross_priority": [
                    "RSI30_PANIC_RESET",
                    "TQQQ_PROTECTED_UP_TO_80",
                    "NORMAL_STOCK",
                    "TQQQ_EXTRA",
                ],
                "share_level_golden_ledger_status": DATA_REQUIRED,
            },
            "market_mode": {
                "ATTACK": "NQSAR Blue/Green and Breadth50>=60 -> max 12 new/total slots",
                "SELECTIVE": "NQSAR Blue/Green and 50<=Breadth50<60 -> max 4 fill slots; no forced trim",
                "STOP": "Yellow or Blue/Green and Breadth50<50 -> new 0",
                "DEFENSE": "Red -> new 0 and normal stocks exit next open",
            },
            "normal_stock": {
                "eligibility": "Price>=5; DDV20>=10M; SMA50>SMA200; Close>SMA200; RS189>=85; RS63>=85; exclude Structural Clinical Biotech",
                "attack_rank": "0.70*RS189 + 0.30*PeerThemeScore (LOO)",
                "selective_rank": "RS189 only",
                "initial_stop": "first Close<=Entry*0.92 -> exit next open",
                "partial_profit": "first Close>=Entry*1.24 -> sell 25% next open once",
                "winner_trail": "remaining 75% stop=max(Entry*0.92, PeakClose*0.70)",
                "forbidden_exits": [
                    "RS rank decline",
                    "Theme rank decline",
                    "Top12 exit",
                    "Breadth threshold trim",
                    "Yellow forced exit",
                    "10SMA/21EMA/ATR2/building-stop rules",
                ],
            },
            "tqqq_panic": {
                "seed": "VIX Close>=23 AND QQQ SMA50 deviation<=-0.5ATR AND QQQ 10d DD<=-2%",
                "seed_max_age_sessions": 30,
                "qqq_4h_definition": "QQQ RTH only, America/New_York, 09:30 anchor: 09:30-13:30 full 4H + 13:30-16:00 session-tail; extended hours excluded; completed standard sessions only; nonstandard sessions fail closed",
                "qqq_4h_rsi": "Textbook Wilder RSI14: 14-delta SMA seed, then Wilder recursive smoothing",
                "trigger": "first QQQ 4H RSI14 touch from >30 to <=30 AND MC57>=20",
                "target_pct": 80,
                "max_hold_sessions": 10,
                "early_exit": "MC57<20 -> return to 30 next open",
            },
            "panic_reset": {
                "entry": "qualified strong theme; RSI14<=30 then first RSI rise within 20 sessions; theme RS63 Top3",
                "hold_sessions": 20,
                "cooldown_sessions": 20,
                "max_names": 4,
                "max_same_theme": 2,
                "averaging_down": False,
                "normal_minus8_stop": False,
            },
        },
    }


def build_weekly_shard(
    *,
    session_date: str,
    generated_at: str,
    nqsar: dict[str, Any] | None,
) -> dict[str, Any]:
    if not _same_session(nqsar, session_date):
        return data_required_shard(
            session_date=session_date,
            generated_at=generated_at,
            source="derived:nqsar-authoritative-input",
            reason="NQSAR_AUTHORITATIVE_INPUT_MISSING_OR_STALE",
            dependency="nqsar.json",
        ) | {"schema_version": SCHEMAS["weekly"], "state": None}
    state = nqsar.get("state")
    if state not in VALID_NQSAR:
        return data_required_shard(
            session_date=session_date,
            generated_at=generated_at,
            source="derived:nqsar-authoritative-input",
            reason="NQSAR_STATE_INVALID",
            dependency="nqsar.json",
        ) | {"schema_version": SCHEMAS["weekly"], "state": None}
    return {
        **_base(
            session_date=session_date,
            generated_at=generated_at,
            coverage=_finite(nqsar.get("coverage")) or 1.0,
            source=f"derived:{nqsar.get('source')}",
            schema_version=SCHEMAS["weekly"],
            status=READY,
        ),
        "state": state,
        "input_kind": nqsar.get("input_kind"),
        "note": "Authoritative NQSAR state is displayed; the unrecovered FSM is not recomputed here.",
    }


def build_rotation_shard(
    *,
    session_date: str,
    generated_at: str,
    theme_scores: dict[str, Any] | None,
) -> dict[str, Any]:
    if not _same_session(theme_scores, session_date):
        return data_required_shard(
            session_date=session_date,
            generated_at=generated_at,
            source="derived:peer-theme-authority",
            reason="PEER_THEME_AUTHORITATIVE_INPUT_MISSING_OR_STALE",
            dependency="theme_scores.json",
        ) | {"schema_version": SCHEMAS["rotation"], "rows": []}
    rows = theme_scores.get("rows")
    if not isinstance(rows, list):
        raise SupplementalEngineError("theme_scores.rows must be a list")
    clean = [dict(row) for row in rows if isinstance(row, dict)]
    if not clean:
        return data_required_shard(
            session_date=session_date,
            generated_at=generated_at,
            source="derived:peer-theme-authority",
            reason="PEER_THEME_ROWS_EMPTY",
            dependency="theme_scores.json",
        ) | {"schema_version": SCHEMAS["rotation"], "rows": []}
    return {
        **_base(
            session_date=session_date,
            generated_at=generated_at,
            coverage=_finite(theme_scores.get("coverage")),
            source=str(theme_scores.get("source") or "authoritative:peer-theme"),
            schema_version=SCHEMAS["rotation"],
            status=READY,
        ),
        "rows": clean,
        "ordering": "authoritative source order; dashboard does not re-rank themes",
        "loo_required": True,
    }


def build_positions_shard(
    *,
    session_date: str,
    generated_at: str,
    ledger: dict[str, Any] | None,
    nqsar_state: str | None,
) -> dict[str, Any]:
    if not _same_session(ledger, session_date):
        return data_required_shard(
            session_date=session_date,
            generated_at=generated_at,
            source="derived:portfolio-ledger",
            reason="POSITIONS_LEDGER_MISSING_OR_STALE",
            dependency="positions_ledger.json",
        ) | {"schema_version": SCHEMAS["positions"], "rows": []}
    rows = ledger.get("rows")
    if not isinstance(rows, list):
        raise SupplementalEngineError("positions_ledger.rows must be a list")

    out_rows: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        sleeve = str(row.get("sleeve") or "NORMAL_STOCK")
        if sleeve == "NORMAL_STOCK":
            required = ("entry", "close", "peak_close", "partial_taken")
            if all(key in row for key in required) and nqsar_state in VALID_NQSAR:
                try:
                    row["next_open_action"] = normal_stock_next_open_action(
                        entry=row["entry"],
                        close=row["close"],
                        peak_close=row["peak_close"],
                        partial_taken=row["partial_taken"],
                        nqsar_state=str(nqsar_state),
                    )
                except PositionsRuleError as exc:
                    row["next_open_action"] = {
                        "action": None,
                        "status": DATA_REQUIRED,
                        "reason": f"INVALID_LEDGER_ROW:{exc}",
                    }
            else:
                row["next_open_action"] = {
                    "action": None,
                    "status": DATA_REQUIRED,
                    "reason": "NORMAL_POSITION_FIELDS_OR_NQSAR_MISSING",
                }
        out_rows.append(row)

    return {
        **_base(
            session_date=session_date,
            generated_at=generated_at,
            coverage=_finite(ledger.get("coverage")) or 1.0,
            source=str(ledger.get("source") or "authoritative:positions-ledger"),
            schema_version=SCHEMAS["positions"],
            status=READY,
        ),
        "rows": out_rows,
        "ledger_version": ledger.get("ledger_version"),
        "note": "Actions are derived only from explicit ledger fields; quantities/cash are never inferred.",
    }


def build_publish_shard(
    *,
    data_dir: str | Path,
    session_date: str,
    generated_at: str,
) -> dict[str, Any]:
    root = Path(data_dir)
    components = [
        assess_shard_file(root / name, name=name, target_session=session_date)
        for name in PUBLISH_INPUTS
    ]
    blockers = [
        {"name": row["name"], "status": row["status"], "reason": row["reason"]}
        for row in components
        if row["status"] != READY
    ]
    ready = sum(1 for row in components if row["status"] == READY)
    return {
        **_base(
            session_date=session_date,
            generated_at=generated_at,
            coverage=ready / len(components),
            source="derived:publication-readiness",
            schema_version=SCHEMAS["publish"],
            status=READY,
        ),
        "full_v38_ready": not blockers,
        "ready_count": ready,
        "required_count": len(components),
        "blockers": blockers,
        "components": components,
        "note": "This shard reports publication readiness; READY means the report itself is current, not that every trading dependency is available.",
    }


def materialize_supplemental_shards(
    data_dir: str | Path,
    *,
    session_date: str,
    generated_at: str,
    theme_scores_path: str | Path | None = None,
    positions_ledger_path: str | Path | None = None,
) -> tuple[Path, ...]:
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    nqsar = _load(root / "nqsar.json")
    theme_scores = _load(theme_scores_path) if theme_scores_path else _load(root / "theme_scores.json")
    ledger = _load(positions_ledger_path) if positions_ledger_path else _load(root / "positions_ledger.json")
    nqsar_state = nqsar.get("state") if _same_session(nqsar, session_date) else None

    outputs: list[Path] = []
    generated = {
        "rules.json": build_rules_shard(session_date=session_date, generated_at=generated_at),
        "weekly.json": build_weekly_shard(
            session_date=session_date,
            generated_at=generated_at,
            nqsar=nqsar,
        ),
        "rotation.json": build_rotation_shard(
            session_date=session_date,
            generated_at=generated_at,
            theme_scores=theme_scores,
        ),
        "positions.json": build_positions_shard(
            session_date=session_date,
            generated_at=generated_at,
            ledger=ledger,
            nqsar_state=str(nqsar_state) if nqsar_state in VALID_NQSAR else None,
        ),
    }
    for name, obj in generated.items():
        path = atomic_write_json(root / name, obj)
        outputs.append(path)

    placeholders = {
        "mc57.json": ("FIXED57_AND_GOLDEN_FIXTURE_NOT_AVAILABLE", "mc57_fixed57_golden"),
        "options/index.json": ("OPTIONS_AUTHORITATIVE_INPUT_MISSING", "options_authority"),
    }
    for name, (reason, dependency) in placeholders.items():
        path = root / name
        existing = _load(path)
        if _same_session(existing, session_date):
            continue
        obj = data_required_shard(
            session_date=session_date,
            generated_at=generated_at,
            source=f"reference-gate:{dependency}",
            reason=reason,
            dependency=dependency,
        )
        outputs.append(atomic_write_json(path, obj))

    for name, reason in (
        ("market_state.json", "NQSAR_OR_MARKET_ENGINE_OUTPUT_MISSING"),
        ("core12.json", "CORE12_AUTHORITATIVE_DEPENDENCIES_MISSING"),
    ):
        path = root / name
        existing = _load(path)
        if _same_session(existing, session_date):
            continue
        outputs.append(
            atomic_write_json(
                path,
                data_required_shard(
                    session_date=session_date,
                    generated_at=generated_at,
                    source="reference-gate:market-engine",
                    reason=reason,
                    dependency=name,
                ),
            )
        )

    publish = build_publish_shard(
        data_dir=root,
        session_date=session_date,
        generated_at=generated_at,
    )
    outputs.append(atomic_write_json(root / "publish.json", publish))
    return tuple(outputs)
