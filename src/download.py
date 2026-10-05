import io
import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPORT_TYPE = "users-1-day"
API_VERSION = "2022-11-28"


def report_url(enterprise_slug, org=""):
    """Build the users-1-day report URL.

    Enterprise-scoped by default, so the report covers every org in the
    enterprise (MoJ plus siblings). When `org` is set, falls back to the
    org-scoped endpoint — an escape hatch for deployments holding only
    org-level metrics access.
    """
    if org:
        return f"{GITHUB_API}/orgs/{org}/copilot/metrics/reports/{REPORT_TYPE}"
    return (
        f"{GITHUB_API}/enterprises/{enterprise_slug}"
        f"/copilot/metrics/reports/{REPORT_TYPE}"
    )


def fetch_download_links(enterprise_slug, day, token, org=""):
    """Call the Copilot metrics-reports API for the day's users-1-day report and
    return the list of presigned download URLs."""
    url = report_url(enterprise_slug, org)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    response = requests.get(url, headers=headers, params={"day": day}, timeout=30)
    response.raise_for_status()
    return _download_links(response, url, day)


def _download_links(response, url, day):
    """Return download URLs, or [] when GitHub has not published the report yet.

    A processing delay comes back as HTTP 200 with an empty or non-object body
    (logged upstream as ``Payload: ''``). That is not a failure of this job.
    """
    try:
        payload = response.json()
    except ValueError:
        logger.warning(
            "Copilot %s report for %s returned a non-JSON body (HTTP %s) from %s; "
            "GitHub has not finished processing this day",
            REPORT_TYPE,
            day,
            response.status_code,
            url,
        )
        return []

    if not isinstance(payload, dict):
        logger.warning(
            "Copilot %s report for %s returned an empty or unexpected payload "
            "from %s; GitHub has not finished processing this day. Payload: %s",
            REPORT_TYPE,
            day,
            url,
            repr(payload)[:200],
        )
        return []

    links = payload.get("download_links") or []
    if not isinstance(links, list):
        logger.warning(
            "Copilot %s report for %s returned download_links of type %s; "
            "treating the report as not yet available",
            REPORT_TYPE,
            day,
            type(links).__name__,
        )
        return []
    return links


def parse_ndjson(bodies):
    """Concatenate NDJSON text bodies into one DataFrame. Empty in -> empty out."""
    frames = [
        pd.read_json(io.StringIO(b), lines=True) for b in bodies if b.strip()
    ]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def read_report(enterprise_slug, day, token, org=""):
    """Fetch the day's report links, download each NDJSON body into memory and
    return one DataFrame. Returns None when there are no links (report not ready).
    Presigned S3 URLs are fetched WITHOUT the GitHub auth header."""
    links = fetch_download_links(enterprise_slug, day, token, org)
    if not links:
        logger.warning(
            "No download links for %s report on %s; report not yet available",
            REPORT_TYPE,
            day,
        )
        return None

    bodies = []
    for url in links:
        content = requests.get(url, timeout=60)
        content.raise_for_status()
        bodies.append(content.text)
    logger.info("Downloaded %d report file(s) for %s into memory", len(bodies), day)
    return parse_ndjson(bodies)
