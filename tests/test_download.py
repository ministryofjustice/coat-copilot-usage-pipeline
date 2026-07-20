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


def test_report_url_defaults_to_enterprise_scope():
    assert download.report_url("ministry-of-justice-uk") == (
        "https://api.github.com/enterprises/ministry-of-justice-uk"
        "/copilot/metrics/reports/users-1-day"
    )


def test_report_url_uses_org_scope_when_org_set():
    assert download.report_url("ministry-of-justice-uk", "some-org") == (
        "https://api.github.com/orgs/some-org"
        "/copilot/metrics/reports/users-1-day"
    )


def test_report_url_empty_org_is_enterprise_scope():
    # An unset ORG env var arrives as "" — it must not select the org branch.
    assert download.report_url("ministry-of-justice-uk", "") == (
        "https://api.github.com/enterprises/ministry-of-justice-uk"
        "/copilot/metrics/reports/users-1-day"
    )


def test_fetch_download_links_calls_enterprise_endpoint_by_default(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"download_links": ["https://example.invalid/part-0"]}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(download.requests, "get", fake_get)

    links = download.fetch_download_links(
        "ministry-of-justice-uk", "2026-07-19", "tok"
    )

    assert captured["url"] == (
        "https://api.github.com/enterprises/ministry-of-justice-uk"
        "/copilot/metrics/reports/users-1-day"
    )
    assert captured["params"] == {"day": "2026-07-19"}
    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert links == ["https://example.invalid/part-0"]
