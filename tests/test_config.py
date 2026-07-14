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
    user, model = config.dataset_paths("my-bucket", "copilot/")
    assert user == "s3://my-bucket/copilot/credits_by_user/"
    assert model == "s3://my-bucket/copilot/credits_by_model/"


def test_dataset_paths_empty_prefix():
    user, model = config.dataset_paths("my-bucket", "")
    assert user == "s3://my-bucket/credits_by_user/"
    assert model == "s3://my-bucket/credits_by_model/"


def test_resolve_paths_uses_selected_bucket(monkeypatch):
    monkeypatch.setattr(config, "mode", "prod")
    monkeypatch.setattr(config, "PROD_BUCKET", "prod-bucket")
    monkeypatch.setattr(config, "output_prefix", "reports-live-consolidated")
    user, model = config.resolve_paths()
    assert user == "s3://prod-bucket/reports-live-consolidated/credits_by_user/"
    assert model == "s3://prod-bucket/reports-live-consolidated/credits_by_model/"


def test_resolve_paths_raises_when_selected_bucket_unset(monkeypatch):
    monkeypatch.setattr(config, "mode", "prod")
    monkeypatch.setattr(config, "PROD_BUCKET", "")
    with pytest.raises(ValueError, match="No output bucket configured"):
        config.resolve_paths()
