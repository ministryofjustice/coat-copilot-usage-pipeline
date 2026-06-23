import io
import logging
import posixpath
from urllib.parse import unquote, urlparse

import awswrangler as wr
import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPORT_TYPE = "users-1-day"
API_VERSION = "2022-11-28"


def fetch_download_links(org, day, token):
    """Call the Copilot metrics-reports API for the day's users-1-day report and
    return the list of presigned download URLs. Mirrors the gh api call in
    download-reports.sh."""
    url = f"{GITHUB_API}/orgs/{org}/copilot/metrics/reports/{REPORT_TYPE}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    response = requests.get(url, headers=headers, params={"day": day}, timeout=30)
    response.raise_for_status()
    return response.json().get("download_links", [])


def _filename_from_url(url, fallback):
    """Preserve GitHub's original filename (like curl --remote-name): take the
    last path segment, dropping the presigned query string, and URL-decode it.
    Falls back to the given name when no usable segment is present."""
    path = urlparse(url).path
    name = unquote(posixpath.basename(path))
    return name or fallback


def download_report(org, day, token, input_path):
    """Fetch the day's users-1-day report links, download each NDJSON file and
    write it to input_path under its original filename. Existing objects under
    input_path are deleted first (overwrite semantics). Returns the number of
    files written; 0 means the report is not yet available for the day."""
    if not token:
        raise ValueError(
            "GITHUB_TOKEN is required to download the usage-metrics report"
        )

    links = fetch_download_links(org, day, token)
    if not links:
        logger.warning(
            "No download links for %s report on %s; report not yet available",
            REPORT_TYPE,
            day,
        )
        return 0

    logger.info("Replacing any existing report files under %s", input_path)
    wr.s3.delete_objects(input_path)

    written = 0
    for i, url in enumerate(links):
        name = _filename_from_url(url, fallback=f"part-{i:05d}.json")
        # Presigned S3 URL from GitHub: fetch WITHOUT the GitHub auth header.
        content = requests.get(url, timeout=60)
        content.raise_for_status()
        dest = f"{input_path}{name}"
        wr.s3.upload(local_file=io.BytesIO(content.content), path=dest)
        written += 1
        logger.info("Downloaded %s -> %s", name, dest)

    logger.info("Downloaded %d report file(s) for %s to %s", written, day, input_path)
    return written
