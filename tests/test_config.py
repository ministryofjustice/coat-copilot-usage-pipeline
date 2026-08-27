import os

import pytest

import config


def test_select_bucket_picks_by_mode(monkeypatch):
    monkeypatch.setattr(config, "DEV_BUCKET", "dev-bucket")
    monkeypatch.setattr(config, "PROD_BUCKET", "prod-bucket")
    assert config.select_bucket("dev") == "dev-bucket"
    assert config.select_bucket("prod") == "prod-bucket"


def test_select_bucket_defaults_to_dev(monkeypatch):
    monkeypatch.setattr(config, "DEV_BUCKET", "dev-bucket")
    monkeypatch.setattr(config, "PROD_BUCKET", "prod-bucket")
    assert config.select_bucket("anything-else") == "dev-bucket"


def test_dataset_paths_with_prefix():
    paths = config.dataset_paths("my-bucket", "copilot/")
    assert paths == {
        "credits_by_user": "s3://my-bucket/copilot/credits_by_user/",
        "credits_by_model": "s3://my-bucket/copilot/credits_by_model/",
        "telemetry_by_user": "s3://my-bucket/copilot/telemetry_by_user/",
        "telemetry_by_user_activity":
            "s3://my-bucket/copilot/telemetry_by_user_activity/",
    }


def test_dataset_paths_empty_prefix():
    paths = config.dataset_paths("my-bucket", "")
    assert paths["credits_by_user"] == "s3://my-bucket/credits_by_user/"
    assert paths["telemetry_by_user"] == "s3://my-bucket/telemetry_by_user/"


def test_dataset_paths_covers_every_declared_dataset():
    # The writer loops over this mapping, so a dataset missing here is a
    # dataset silently never written.
    paths = config.dataset_paths("my-bucket", "")
    assert set(paths) == set(config.DATASETS)


def test_resolve_paths_uses_selected_bucket(monkeypatch):
    monkeypatch.setattr(config, "mode", "prod")
    monkeypatch.setattr(config, "PROD_BUCKET", "prod-bucket")
    monkeypatch.setattr(config, "output_prefix", "reports-live-consolidated")
    paths = config.resolve_paths()
    base = "s3://prod-bucket/reports-live-consolidated/"
    assert paths["credits_by_user"] == base + "credits_by_user/"
    assert paths["credits_by_model"] == base + "credits_by_model/"
    assert paths["telemetry_by_user_activity"] == base + "telemetry_by_user_activity/"


def test_resolve_paths_raises_when_selected_bucket_unset(monkeypatch):
    monkeypatch.setattr(config, "mode", "prod")
    monkeypatch.setattr(config, "PROD_BUCKET", "")
    with pytest.raises(ValueError, match="No output bucket configured"):
        config.resolve_paths()


@pytest.mark.skipif(
    os.environ.get("ORG"), reason="ORG is set in this environment"
)
def test_org_defaults_to_empty():
    # Guards the default itself: a non-empty ORG default would silently route
    # every run back to the org-scoped endpoint, dropping sibling orgs while
    # every other test still passes.
    assert config.org == ""
