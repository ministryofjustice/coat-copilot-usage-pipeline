import pandas as pd
import pytest
import main


def _patch_common(monkeypatch, calls):
    monkeypatch.setattr(main.config, "billing_token", "t")
    monkeypatch.setattr(main.config, "org", "org")
    monkeypatch.setattr(main.config, "enterprise_slug", "slug")
    monkeypatch.setattr(main.config, "report_day", "2026-06-25")
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
