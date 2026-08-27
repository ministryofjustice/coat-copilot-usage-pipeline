import pandas as pd
import pytest
import main

PATHS = {
    "credits_by_user": "s3://b/u/",
    "credits_by_model": "s3://b/m/",
    "telemetry_by_user": "s3://b/tu/",
    "telemetry_by_user_activity": "s3://b/ta/",
}


def _report_frame(login="a", credits=5.0):
    """One person-day record with the fields every builder reads."""
    return pd.DataFrame([{
        "user_id": 1,
        "user_login": login,
        "enterprise_id": "83",
        "user_initiated_interaction_count": 1,
        "code_generation_activity_count": 1,
        "code_acceptance_activity_count": 0,
        "loc_suggested_to_add_sum": 10,
        "loc_suggested_to_delete_sum": 0,
        "loc_added_sum": 10,
        "loc_deleted_sum": 0,
        "used_cli": False,
        "ai_credits_used": credits,
        "totals_by_language_feature": [
            {"language": "python", "feature": "code_completion",
             "code_generation_activity_count": 1},
        ],
    }])


def _patch_common(monkeypatch, calls):
    monkeypatch.setattr(main.config, "billing_token", "t")
    monkeypatch.setattr(main.config, "org", "")
    monkeypatch.setattr(main.config, "enterprise_slug", "slug")
    monkeypatch.setattr(main.config, "report_day", "2026-06-25")
    monkeypatch.setattr(main.config, "backfill_range", "")
    monkeypatch.setattr(main.config, "resolve_paths", lambda: PATHS)
    monkeypatch.setattr(
        main.wr.s3, "to_parquet",
        lambda **kw: calls.append(kw["path"]),
    )


def test_main_writes_every_dataset(monkeypatch):
    calls = []
    _patch_common(monkeypatch, calls)
    monkeypatch.setattr(main, "read_report", lambda *a: _report_frame())
    monkeypatch.setattr(
        main, "fetch_billing",
        lambda *a: [{"model": "Claude Sonnet 4", "grossQuantity": 3}],
    )
    main.main()
    assert calls == ["s3://b/u/", "s3://b/tu/", "s3://b/ta/", "s3://b/m/"]


def test_main_report_datasets_written_before_per_model_failure(monkeypatch):
    calls = []
    _patch_common(monkeypatch, calls)
    monkeypatch.setattr(main, "read_report", lambda *a: _report_frame())

    def boom(*a):
        raise RuntimeError("billing 403")

    monkeypatch.setattr(main, "fetch_billing", boom)
    with pytest.raises(RuntimeError):
        main.main()
    # everything derived from the metrics report is on S3 before billing runs
    assert calls == ["s3://b/u/", "s3://b/tu/", "s3://b/ta/"]


def test_main_missing_token_raises(monkeypatch):
    monkeypatch.setattr(main.config, "billing_token", "")
    with pytest.raises(ValueError):
        main.main()


def test_main_range_writes_once_per_dataset(monkeypatch):
    calls = []
    _patch_common(monkeypatch, calls)
    days = ["2026-06-23", "2026-06-24", "2026-06-25"]
    monkeypatch.setattr(main, "report_days", lambda *a: days)

    reads = []

    def fake_read(enterprise_slug, day, token, org=""):
        reads.append(day)
        return _report_frame(login=day)

    monkeypatch.setattr(main, "read_report", fake_read)
    monkeypatch.setattr(
        main, "fetch_billing",
        lambda slug, day, token: [{"model": "GPT-5", "grossQuantity": 1}],
    )
    main.main()
    # one download per day, one accumulated write per dataset
    assert reads == days
    assert calls == ["s3://b/u/", "s3://b/tu/", "s3://b/ta/", "s3://b/m/"]


def test_collect_all_rows_downloads_each_day_once(monkeypatch):
    monkeypatch.setattr(main.config, "enterprise_slug", "slug")
    monkeypatch.setattr(main.config, "org", "")
    monkeypatch.setattr(main.config, "billing_token", "t")

    reads = []

    def fake_read(enterprise_slug, day, token, org=""):
        reads.append(day)
        return _report_frame(login=day)

    monkeypatch.setattr(main, "read_report", fake_read)
    frames = main.collect_all_rows(["a", "b"])
    # the report download is the largest cost in the job; three datasets come
    # out of one call per day, never one call per dataset
    assert reads == ["a", "b"]
    assert frames["telemetry_by_user"]["day"].tolist() == ["a", "b"]
    assert frames["telemetry_by_user_activity"]["day"].tolist() == ["a", "b"]


def test_collect_all_rows_skips_missing_days(monkeypatch):
    monkeypatch.setattr(main.config, "enterprise_slug", "slug")
    monkeypatch.setattr(main.config, "org", "")
    monkeypatch.setattr(main.config, "billing_token", "t")

    def fake_read(enterprise_slug, day, token, org=""):
        if day == "b":
            return None  # report not ready for this day
        return _report_frame(login=day)

    monkeypatch.setattr(main, "read_report", fake_read)
    frames = main.collect_all_rows(["a", "b", "c"])
    assert frames["credits_by_user"]["day"].tolist() == ["a", "c"]
    assert frames["telemetry_by_user"]["day"].tolist() == ["a", "c"]


def test_collect_all_rows_keeps_person_rows_with_no_credits(monkeypatch):
    monkeypatch.setattr(main.config, "enterprise_slug", "slug")
    monkeypatch.setattr(main.config, "org", "")
    monkeypatch.setattr(main.config, "billing_token", "t")
    monkeypatch.setattr(
        main, "read_report",
        lambda *a, **kw: _report_frame(login="a", credits=0.0),
    )
    frames = main.collect_all_rows(["a"])
    # credits_by_user drops a zero-credit person; telemetry_by_user must not,
    # because a person-day with no spend and no activity is still a fact.
    assert frames["credits_by_user"].empty
    assert len(frames["telemetry_by_user"]) == 1
