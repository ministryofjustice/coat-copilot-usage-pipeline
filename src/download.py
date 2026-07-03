import io
import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPORT_TYPE = "users-1-day"
API_VERSION = "2022-11-28"


def fetch_download_links(org, day, token):
    """Call the Copilot metrics-reports API for the day's users-1-day report and
    return the list of presigned download URLs."""
    url = f"{GITHUB_API}/orgs/{org}/copilot/metrics/reports/{REPORT_TYPE}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    response = requests.get(url, headers=headers, params={"day": day}, timeout=30)
    response.raise_for_status()
    return response.json().get("download_links", [])


def parse_ndjson(bodies):
    """Concatenate NDJSON text bodies into one DataFrame. Empty in -> empty out."""
    frames = [
        pd.read_json(io.StringIO(b), lines=True) for b in bodies if b.strip()
    ]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def read_report(org, day, token):
    """Fetch the day's report links, download each NDJSON body into memory and
    return one DataFrame. Returns None when there are no links (report not ready).
    Presigned S3 URLs are fetched WITHOUT the GitHub auth header."""
    links = fetch_download_links(org, day, token)
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
