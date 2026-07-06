import os
from datetime import datetime, timedelta, timezone

mode = os.environ.get("MODE", "dev")

# Target report day: REPORT_DAY (YYYY-MM-DD), default = yesterday (UTC).
report_day = os.environ.get(
    "REPORT_DAY",
    (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"),
)

# GitHub org for the usage-metrics report endpoint.
org = os.environ.get("ORG", "ministryofjustice")

# Enterprise slug for the billing endpoint URL (see model-to-final.sh).
enterprise_slug = os.environ.get("ENTERPRISE_SLUG", "ministry-of-justice-uk")

# One token for both metrics and billing calls. Injected by Analytical Platform
# Airflow as SECRET_ENTERPRISE_BILLING_TOKEN.
billing_token = os.environ.get("SECRET_ENTERPRISE_BILLING_TOKEN", "")

# Prefix above the two dataset dirs inside the selected bucket.
output_prefix = os.environ.get("OUTPUT_PREFIX", "copilot/")

# Optional multi-day backfill: "" = single day (report_day), "week" or "month"
# = that period of today up to yesterday (UTC). See dates.report_days.
backfill_range = os.environ.get("BACKFILL_RANGE", "").strip().lower()

# Output S3 buckets by MODE (Cloud Platform bucket names, hardcoded).
DEV_BUCKET = "cloud-platform-c7bd5f7843c58dde69caa00cb7509154"
PROD_BUCKET = "cloud-platform-41b6a454e7cc120fe1764d3f7fe3f1e2"


def select_bucket(mode):
    """Pick the output bucket by MODE (prod -> PROD_BUCKET, else DEV_BUCKET)."""
    return PROD_BUCKET if mode == "prod" else DEV_BUCKET


def dataset_paths(bucket, prefix):
    """Return (credits_by_user_path, credits_by_model_path) as s3:// URIs."""
    p = prefix.strip("/")
    base = f"s3://{bucket}/{p}/" if p else f"s3://{bucket}/"
    return base + "credits_by_user/", base + "credits_by_model/"


def resolve_paths():
    """Resolve output dataset paths at job start."""
    return dataset_paths(select_bucket(mode), output_prefix)
