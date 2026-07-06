import config


def test_select_bucket_picks_by_mode():
    assert config.select_bucket("dev") == config.DEV_BUCKET
    assert config.select_bucket("prod") == config.PROD_BUCKET


def test_select_bucket_defaults_to_dev():
    assert config.select_bucket("anything-else") == config.DEV_BUCKET


def test_dataset_paths_with_prefix():
    user, model = config.dataset_paths("my-bucket", "copilot/")
    assert user == "s3://my-bucket/copilot/credits_by_user/"
    assert model == "s3://my-bucket/copilot/credits_by_model/"


def test_dataset_paths_empty_prefix():
    user, model = config.dataset_paths("my-bucket", "")
    assert user == "s3://my-bucket/credits_by_user/"
    assert model == "s3://my-bucket/credits_by_model/"
