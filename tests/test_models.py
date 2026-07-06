import models


def test_model_family_rules():
    assert models.model_family("Claude Opus 4.1") == "Opus"
    assert models.model_family("Claude Sonnet 4") == "Sonnet"
    assert models.model_family("Claude Haiku 3.5") == "Haiku"
    assert models.model_family("GPT-5") == "GPT"
    assert models.model_family("Gemini 2.5 Pro") == "Gemini"
    assert models.model_family("Code Review model") == "CodeReview"
    assert models.model_family("Something Else") == "Other"


def test_build_groups_sums_and_tags():
    items = [
        {"model": "Claude Sonnet 4", "grossQuantity": 3},
        {"model": "Claude Sonnet 4", "grossQuantity": 2},
        {"model": "Auto: Claude Opus 4.1", "grossQuantity": 10},
    ]
    df = models.build_model_rows(items, "2026-06-25")
    assert list(df.columns) == [
        "day", "model", "model_family", "routed", "ai_credits_used"
    ]
    # sorted credits-desc: the Auto Opus row (10) first
    assert df.iloc[0]["model"] == "Auto: Claude Opus 4.1"
    assert bool(df.iloc[0]["routed"]) is True
    assert df.iloc[0]["model_family"] == "Opus"
    sonnet = df[df["model"] == "Claude Sonnet 4"].iloc[0]
    assert sonnet["ai_credits_used"] == 5
    assert bool(sonnet["routed"]) is False


def test_build_empty_items_returns_typed_empty_frame():
    df = models.build_model_rows([], "2026-06-25")
    assert df.empty
    assert list(df.columns) == [
        "day", "model", "model_family", "routed", "ai_credits_used"
    ]
