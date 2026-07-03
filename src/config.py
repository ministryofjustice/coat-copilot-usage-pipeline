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


def normalize_bucket(raw):
    """Accept 'bucket', 's3://bucket' or trailing-slash forms -> bare name."""
    return raw.replace("s3://", "").strip("/")


def select_bucket(mode, dev, prod):
    """Pick the output bucket by MODE. Raise if the active one is empty."""
    raw = prod if mode == "prod" else dev
    if not raw:
        which = "PROD_S3_BUCKET" if mode == "prod" else "DEV_S3_BUCKET"
        raise RuntimeError(f"{which} is required for MODE={mode}")
    return normalize_bucket(raw)


def dataset_paths(bucket, prefix):
    """Return (credits_by_user_path, credits_by_model_path) as s3:// URIs."""
    p = prefix.strip("/")
    base = f"s3://{bucket}/{p}/" if p else f"s3://{bucket}/"
    return base + "credits_by_user/", base + "credits_by_model/"


def resolve_paths():
    """Resolve output dataset paths from env at job start (fail-fast)."""
    bucket = select_bucket(
        mode,
        os.environ.get("DEV_S3_BUCKET", ""),
        os.environ.get("PROD_S3_BUCKET", ""),
    )
    return dataset_paths(bucket, output_prefix)
