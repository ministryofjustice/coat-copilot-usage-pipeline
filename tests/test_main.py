import pandas as pd
import pytest
import main


def _patch_common(monkeypatch, calls):
    monkeypatch.setattr(main.config, "billing_token", "t")
    monkeypatch.setattr(main.config, "org", "org")
    monkeypatch.setattr(main.config, "enterprise_slug", "slug")
    monkeypatch.setattr(main.config, "report_day", "2026-06-25")
    monkeypatch.setattr(main.config, "backfill_range", "")
    monkeypatch.setattr(
        main.config, "resolve_paths", lambda: ("s3://b/u/", "s3://b/m/")
    )
    monkeypatch.setattr(
        main.wr.s3, "to_parquet",
        lambda **kw: calls.append(kw["path"]),
    )


def test_main_writes_both_paths(monkeypatch):
    calls = []
    _patch_common(monkeypatch, calls)
    monkeypatch.setattr(
        main, "read_report",
        lambda *a: pd.DataFrame(
            {"user_login": ["a"], "ai_credits_used": [5.0]}
        ),
    )
    monkeypatch.setattr(
        main, "fetch_billing",
        lambda *a: [{"model": "Claude Sonnet 4", "grossQuantity": 3}],
    )
    main.main()
    assert calls == ["s3://b/u/", "s3://b/m/"]


def test_main_per_user_written_before_per_model_failure(monkeypatch):
    calls = []
    _patch_common(monkeypatch, calls)
    monkeypatch.setattr(
        main, "read_report",
        lambda *a: pd.DataFrame(
            {"user_login": ["a"], "ai_credits_used": [5.0]}
        ),
    )

    def boom(*a):
        raise RuntimeError("billing 403")

    monkeypatch.setattr(main, "fetch_billing", boom)
    with pytest.raises(RuntimeError):
        main.main()
    # per-user parquet still written before the per-model failure
    assert calls == ["s3://b/u/"]


def test_main_missing_token_raises(monkeypatch):
    monkeypatch.setattr(main.config, "billing_token", "")
    with pytest.raises(ValueError):
        main.main()


def test_main_range_writes_once_per_path(monkeypatch):
    calls = []
    _patch_common(monkeypatch, calls)
    days = ["2026-06-23", "2026-06-24", "2026-06-25"]
    monkeypatch.setattr(main, "report_days", lambda *a: days)

    reads = []

    def fake_read(org, day, token):
        reads.append(day)
        return pd.DataFrame({"user_login": [day], "ai_credits_used": [1.0]})

    monkeypatch.setattr(main, "read_report", fake_read)
    monkeypatch.setattr(
        main, "fetch_billing",
        lambda slug, day, token: [{"model": "GPT-5", "grossQuantity": 1}],
    )
    main.main()
    # read once per day, but a single accumulated write per dataset
    assert reads == days
    assert calls == ["s3://b/u/", "s3://b/m/"]


def test_collect_user_rows_skips_missing_days(monkeypatch):
    monkeypatch.setattr(main.config, "org", "org")
    monkeypatch.setattr(main.config, "billing_token", "t")

    def fake_read(org, day, token):
        if day == "b":
            return None  # report not ready for this day
        return pd.DataFrame({"user_login": [day], "ai_credits_used": [1.0]})

    monkeypatch.setattr(main, "read_report", fake_read)
    rows = main.collect_user_rows(["a", "b", "c"])
    assert rows["day"].tolist() == ["a", "c"]
