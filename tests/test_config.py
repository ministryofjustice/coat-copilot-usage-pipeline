import pytest
import config


def test_normalize_bucket_strips_scheme_and_slashes():
    assert config.normalize_bucket("s3://my-bucket/") == "my-bucket"
    assert config.normalize_bucket("my-bucket") == "my-bucket"


def test_select_bucket_picks_by_mode():
    assert config.select_bucket("dev", "dev-b", "prod-b") == "dev-b"
    assert config.select_bucket("prod", "dev-b", "prod-b") == "prod-b"


def test_select_bucket_missing_raises():
    with pytest.raises(RuntimeError):
        config.select_bucket("prod", "dev-b", "")


def test_dataset_paths_with_prefix():
    user, model = config.dataset_paths("my-bucket", "copilot/")
    assert user == "s3://my-bucket/copilot/credits_by_user/"
    assert model == "s3://my-bucket/copilot/credits_by_model/"


def test_dataset_paths_empty_prefix():
    user, model = config.dataset_paths("my-bucket", "")
    assert user == "s3://my-bucket/credits_by_user/"
    assert model == "s3://my-bucket/credits_by_model/"
