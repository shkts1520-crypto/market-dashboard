import json

import pytest

from v38.freshness import (
    DATA_REQUIRED,
    READY,
    STALE,
    FreshnessError,
    assess_shard_file,
    assess_shard_object,
    atomic_write_json,
    build_freshness,
)

SESSION = "2026-09-08"
GENERATED = (
    "2026-09-09T05:00:00+09:00"
)


def shard(
    session=SESSION,
    **updates,
):
    x = {
        "session_date": session,
        "generated_at": GENERATED,
        "coverage": 1.0,
        "source": "fixture",
        "schema_version": "x",
        "calculation_version": "x",
    }

    x.update(updates)

    return x


def test_current_shard_is_ready():
    out = assess_shard_object(
        shard(),
        name="rs.json",
        target_session=SESSION,
    )

    assert (
        out["status"]
        == READY
    )


def test_session_mismatch_is_stale_not_success():
    out = assess_shard_object(
        shard("2026-09-07"),
        name="rs.json",
        target_session=SESSION,
    )

    assert (
        out["status"]
        == STALE
    )

    assert (
        out["reason"]
        == "SESSION_MISMATCH"
    )


def test_missing_metadata_is_data_required():
    obj = shard()
    obj.pop("source")

    out = assess_shard_object(
        obj,
        name="rs.json",
        target_session=SESSION,
    )

    assert (
        out["status"]
        == DATA_REQUIRED
    )

    assert (
        "source"
        in out["missing"]
    )


def test_missing_file_is_data_required(
    tmp_path,
):
    out = assess_shard_file(
        tmp_path
        / "missing.json",
        name="missing.json",
        target_session=SESSION,
    )

    assert (
        out["status"]
        == DATA_REQUIRED
    )

    assert (
        out["reason"]
        == "FILE_MISSING"
    )


def test_invalid_json_is_data_required(
    tmp_path,
):
    p = tmp_path / "bad.json"

    p.write_text(
        "{bad",
        encoding="utf-8",
    )

    out = assess_shard_file(
        p,
        name="bad.json",
        target_session=SESSION,
    )

    assert (
        out["status"]
        == DATA_REQUIRED
    )

    assert (
        out["reason"]
        == "INVALID_JSON"
    )


def test_stale_dominates_overall_status(
    tmp_path,
):
    (
        tmp_path
        / "a.json"
    ).write_text(
        json.dumps(
            shard(
                "2026-09-07"
            )
        ),
        encoding="utf-8",
    )

    out = build_freshness(
        tmp_path,
        target_session=SESSION,
        generated_at=GENERATED,
        shard_names=(
            "a.json",
            "missing.json",
        ),
    )

    assert (
        out["status"]
        == STALE
    )

    assert (
        out["stale_count"]
        == 1
    )

    assert (
        out[
            "data_required_count"
        ]
        == 1
    )


def test_missing_without_stale_is_data_required(
    tmp_path,
):
    (
        tmp_path
        / "a.json"
    ).write_text(
        json.dumps(
            shard()
        ),
        encoding="utf-8",
    )

    out = build_freshness(
        tmp_path,
        target_session=SESSION,
        generated_at=GENERATED,
        shard_names=(
            "a.json",
            "missing.json",
        ),
    )

    assert (
        out["status"]
        == DATA_REQUIRED
    )

    assert (
        out["ready_count"]
        == 1
    )


def test_all_current_is_ready(
    tmp_path,
):
    for name in (
        "a.json",
        "b.json",
    ):
        (
            tmp_path
            / name
        ).write_text(
            json.dumps(
                shard()
            ),
            encoding="utf-8",
        )

    out = build_freshness(
        tmp_path,
        target_session=SESSION,
        generated_at=GENERATED,
        shard_names=(
            "a.json",
            "b.json",
        ),
    )

    assert (
        out["status"]
        == READY
    )

    assert (
        out["coverage"]
        == 1.0
    )


def test_duplicate_shard_names_are_rejected(
    tmp_path,
):
    with pytest.raises(
        FreshnessError
    ):
        build_freshness(
            tmp_path,
            target_session=SESSION,
            generated_at=GENERATED,
            shard_names=(
                "a",
                "a",
            ),
        )


def test_atomic_write_never_emits_nan(
    tmp_path,
):
    p = atomic_write_json(
        tmp_path
        / "freshness.json",
        {
            "x": None
        },
    )

    assert json.loads(
        p.read_text(
            encoding="utf-8"
        )
    ) == {
        "x": None
    }

    assert (
        "NaN"
        not in p.read_text(
            encoding="utf-8"
        )
    )
