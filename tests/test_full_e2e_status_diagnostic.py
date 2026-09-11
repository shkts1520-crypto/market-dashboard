from test_full_e2e_golden import build_full, load_fixture


def test_full_e2e_view_statuses_are_all_ready(tmp_path):
    fx = load_fixture()
    _, _, view = build_full(tmp_path, fx)
    keys = ("daily", "positions", "core12", "rotation", "rs", "weekly", "options", "publish", "rules")
    statuses = {key: (view[key]["status"], view[key].get("reason")) for key in keys}
    daily_metrics = {
        row["key"]: (row["status"], row.get("reason"), row.get("value"))
        for row in view["daily"]["metrics"]
    }
    assert all(status == "READY" for status, _ in statuses.values()), {
        "sections": statuses,
        "daily_metrics": daily_metrics,
    }
