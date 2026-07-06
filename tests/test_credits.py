import pandas as pd
import pytest
import credits


def test_validate_missing_field_raises():
    with pytest.raises(ValueError):
        credits.validate_credits_field(pd.DataFrame({"user_login": ["a"]}))


def test_build_filters_zero_and_null_credits():
    df = pd.DataFrame({
        "user_login": ["alice", "bob", "carol"],
        "ai_credits_used": [5.0, 0.0, None],
    })
    rows = credits.build_credit_rows(df, "2026-06-25")
    assert list(rows.columns) == ["day", "user_login", "ai_credits_used"]
    assert rows["user_login"].tolist() == ["alice"]
    assert rows["day"].tolist() == ["2026-06-25"]
    assert rows["ai_credits_used"].tolist() == [5.0]


def test_build_empty_when_no_positive_credits():
    df = pd.DataFrame({"user_login": ["a"], "ai_credits_used": [0.0]})
    assert credits.build_credit_rows(df, "2026-06-25").empty
