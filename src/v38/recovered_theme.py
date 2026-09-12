from __future__ import annotations

import base64
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-recovered-theme-1.0.0"
MEMBERSHIP_SCHEMA = "v38.theme_membership.1"
ROTATION_SCHEMA = "v38.theme_rotation_recovered.1"
THEME_SCORE_SCHEMA = "v38.theme_scores.1"
NEUTRAL_THEME_SCORE = 50.0


class RecoveredThemeError(RuntimeError):
    pass


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load_theme_map(path: str | Path) -> dict[str, tuple[str, str]]:
    p = Path(path)
    if not p.is_file():
        raise RecoveredThemeError(f"theme map missing: {p}")
    try:
        raw = gzip.decompress(base64.b64decode(p.read_bytes(), validate=True))
        obj = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RecoveredThemeError(f"theme map invalid: {p}: {exc}") from exc
    if not isinstance(obj, dict):
        raise RecoveredThemeError("theme map root must be object")
    out: dict[str, tuple[str, str]] = {}
    for ticker, value in obj.items():
        if not isinstance(ticker, str) or not isinstance(value, list) or len(value) != 2:
            continue
        major, fine = value
        if not isinstance(major, str) or not major.strip() or not isinstance(fine, str) or not fine.strip():
            continue
        out[ticker.strip().upper()] = (major.strip(), fine.strip())
    if len(out) < 1000:
        raise RecoveredThemeError(f"theme map unexpectedly small: {len(out)}")
    return out


def _industry_inference(
    rs_rows: list[dict[str, Any]],
    exact: dict[str, tuple[str, str]],
) -> dict[str, tuple[str, str, float, int]]:
    """Infer only from peers in the same TradingView industry.

    The direct ticker map remains authoritative. For missing tickers we use the
    modal fine theme among already-mapped current-universe peers in the same
    industry, and expose confidence/count so the inference is auditable.
    """
    votes: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    for row in rs_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        industry = str(row.get("industry") or "").strip()
        if not ticker or not industry or ticker not in exact:
            continue
        votes[industry][exact[ticker]] += 1

    inferred: dict[str, tuple[str, str, float, int]] = {}
    for row in rs_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        industry = str(row.get("industry") or "").strip()
        if not ticker or ticker in exact or not industry:
            continue
        counter = votes.get(industry)
        if not counter:
            continue
        ranked = counter.most_common()
        (major, fine), count = ranked[0]
        total = sum(counter.values())
        confidence = count / total if total else 0.0
        # Avoid pretending a heterogeneous industry has a precise fine-theme.
        # 2 mapped peers and >=60% agreement is enough for recovery display;
        # otherwise keep it visibly unresolved for later company-description pass.
        if count >= 2 and confidence >= 0.60:
            inferred[ticker] = (major, fine, confidence, total)
    return inferred


def build_recovered_theme_outputs(
    rs: dict[str, Any],
    *,
    session_date: str,
    generated_at: str,
    theme_map_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rows = rs.get("rows") if isinstance(rs, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RecoveredThemeError("rs rows missing")

    exact = load_theme_map(theme_map_path)
    inferred = _industry_inference(rows, exact)

    membership_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    exact_count = inferred_count = missing_count = 0

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        ticker = str(raw.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        major: str | None = None
        fine: str | None = None
        method = "UNMAPPED"
        confidence: float | None = None
        peer_count: int | None = None
        if ticker in exact:
            major, fine = exact[ticker]
            method = "EXACT_SECTOR_SNAPSHOT"
            confidence = 1.0
            exact_count += 1
        elif ticker in inferred:
            major, fine, confidence, peer_count = inferred[ticker]
            method = "INFERRED_INDUSTRY_PEERS"
            inferred_count += 1
        else:
            missing_count += 1

        member = {
            "ticker": ticker,
            "major_theme": major,
            "theme_id": fine,
            "theme_name": fine,
            "tag_method": method,
            "tag_confidence": confidence,
            "tag_peer_count": peer_count,
            "sector": raw.get("sector"),
            "industry": raw.get("industry"),
        }
        membership_rows.append(member)
        score_rows.append({
            "ticker": ticker,
            "peer_theme_score": NEUTRAL_THEME_SCORE,
            "theme_status": "RECOVERED_MEMBERSHIP_NEUTRAL_SCORE" if fine else "MISSING_NEUTRAL",
            "theme_id": fine,
            "theme_name": fine,
            "major_theme": major,
            "tag_method": method,
            "tag_confidence": confidence,
        })
        if major and fine:
            enriched = dict(raw)
            enriched.update(member)
            grouped[(major, fine)].append(enriched)

    def median(values: list[float]) -> float | None:
        if not values:
            return None
        values = sorted(values)
        n = len(values)
        m = n // 2
        return values[m] if n % 2 else (values[m - 1] + values[m]) / 2.0

    aggregate_rows: list[dict[str, Any]] = []
    for (major, fine), members in grouped.items():
        rs63 = [x for x in (_finite(m.get("rs63")) for m in members) if x is not None]
        rs189 = [x for x in (_finite(m.get("rs189")) for m in members) if x is not None]
        ret1 = [x for x in (_finite(m.get("ret1")) for m in members) if x is not None]
        ret20 = [x for x in (_finite(m.get("ret20")) for m in members) if x is not None]
        # Original Command Center display definition recovered from the archived
        # dashboard: median RS63 and median RS189, equal-weight blend, groups >=2.
        m63 = median(rs63)
        m189 = median(rs189)
        raw_strength = (m63 + m189) / 2.0 if m63 is not None and m189 is not None else None
        leaders = sorted(
            members,
            key=lambda x: (-(_finite(x.get("rs189")) or -1e100), str(x.get("ticker") or "")),
        )[:5]
        aggregate_rows.append({
            "major_theme": major,
            "theme_id": fine,
            "theme_name": fine,
            "member_count": len(members),
            "rs63_median": m63,
            "rs189_median": m189,
            "raw_strength": raw_strength,
            "ret1_median": median(ret1),
            "ret20_median": median(ret20),
            "leaders": [str(x.get("ticker")) for x in leaders],
        })

    eligible = [x for x in aggregate_rows if x["member_count"] >= 2 and x["raw_strength"] is not None]
    eligible.sort(key=lambda x: (x["raw_strength"], x["theme_id"]))
    if eligible:
        n = len(eligible)
        # Average-rank percentile for ties, same convention as stock RS.
        buckets: dict[float, list[int]] = defaultdict(list)
        for i, row in enumerate(eligible, start=1):
            buckets[float(row["raw_strength"])].append(i)
        pct = {value: (sum(pos) / len(pos)) / n * 100.0 for value, pos in buckets.items()}
        for row in aggregate_rows:
            raw_strength = row["raw_strength"]
            row["theme_rs"] = pct.get(float(raw_strength)) if row["member_count"] >= 2 and raw_strength is not None else None
    else:
        for row in aggregate_rows:
            row["theme_rs"] = None
    aggregate_rows.sort(key=lambda x: (-(x["theme_rs"] if x["theme_rs"] is not None else -1e100), x["theme_id"]))

    coverage = (exact_count + inferred_count) / max(1, len(membership_rows))
    common = {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": coverage,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
    }
    membership = {
        **common,
        "source": "recovered sector_snapshot.s2t + same-industry peer inference",
        "schema_version": MEMBERSHIP_SCHEMA,
        "coverage_detail": {
            "rows": len(membership_rows),
            "exact": exact_count,
            "inferred": inferred_count,
            "unmapped": missing_count,
            "source_map_tickers": len(exact),
        },
        "rows": membership_rows,
        "note": "Exact legacy ticker tags are preserved. Missing tickers are inferred only when same-industry mapped peers have >=60% agreement with at least 2 votes; unresolved names remain explicit.",
    }
    rotation = {
        **common,
        "source": "recovered fine-theme membership + current RS universe",
        "schema_version": ROTATION_SCHEMA,
        "definition": "median(RS63) and median(RS189), equal-weight blend; percentile across themes with >=2 members",
        "rows": aggregate_rows,
    }
    theme_scores = {
        **common,
        "source": "recovered fine-theme membership; final Peer Theme trade score intentionally neutral until full LOO inputs are restored",
        "schema_version": THEME_SCORE_SCHEMA,
        "rows": score_rows,
        "rules": {
            "missing_theme_score": NEUTRAL_THEME_SCORE,
            "recovered_membership_score": NEUTRAL_THEME_SCORE,
            "sector_substitution": False,
            "industry_inference_membership_only": True,
            "loo_required_when_trade_score_restored": True,
        },
        "note": "Membership is recovered now without silently changing the adopted Core12 ranking engine. The original display-oriented sub-theme RS is in theme_rotation_recovered.json.",
    }
    return membership, rotation, theme_scores


def write_theme_outputs(
    data_dir: str | Path,
    rs: dict[str, Any],
    *,
    session_date: str,
    generated_at: str,
    theme_map_path: str | Path,
) -> tuple[Path, Path, Path]:
    root = Path(data_dir)
    membership, rotation, scores = build_recovered_theme_outputs(
        rs,
        session_date=session_date,
        generated_at=generated_at,
        theme_map_path=theme_map_path,
    )
    return (
        atomic_write_json(root / "theme_membership.json", membership),
        atomic_write_json(root / "theme_rotation_recovered.json", rotation),
        atomic_write_json(root / "theme_scores.json", scores),
    )
