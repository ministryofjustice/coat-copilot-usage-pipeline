import pandas as pd
import download


def test_parse_ndjson_concatenates_bodies():
    body_a = '{"user_login": "alice", "ai_credits_used": 5}\n'
    body_b = (
        '{"user_login": "bob", "ai_credits_used": 0}\n'
        '{"user_login": "carol", "ai_credits_used": 2}\n'
    )
    df = download.parse_ndjson([body_a, body_b])
    assert len(df) == 3
    assert set(df["user_login"]) == {"alice", "bob", "carol"}


def test_parse_ndjson_empty_bodies_returns_empty_frame():
    df = download.parse_ndjson(["", "  \n"])
    assert df.empty
