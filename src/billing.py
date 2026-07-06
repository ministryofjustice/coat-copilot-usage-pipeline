import logging

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
API_VERSION = "2022-11-28"


def fetch_billing(enterprise_slug, day, token):
    """Fetch the enterprise ai_credit/usage billing report for one day and return
    its usageItems (each with model + grossQuantity). Empty list when none.
    Mirrors the gh api call in model-to-final.sh."""
    year, month, dom = (int(part) for part in day.split("-"))
    url = (
        f"{GITHUB_API}/enterprises/{enterprise_slug}"
        "/settings/billing/ai_credit/usage"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    response = requests.get(
        url,
        headers=headers,
        params={"year": year, "month": month, "day": dom},
        timeout=30,
    )
    response.raise_for_status()
    items = response.json().get("usageItems", [])
    logger.info("Billing report for %s: %d usageItem(s)", day, len(items))
    return items
