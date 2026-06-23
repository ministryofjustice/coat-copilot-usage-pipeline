import os
from datetime import datetime, timedelta, timezone

mode = os.environ.get("MODE", "dev")

# Target report day: REPORT_DAY env var (YYYY-MM-DD), default = yesterday (UTC).
report_day = os.environ.get(
    "REPORT_DAY",
    (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"),
)

# Billing constants (mirror the bash script).
enterprise = os.environ.get("ENTERPRISE", "Ministry of Justice (UK)")
price_per_unit = float(os.environ.get("PRICE_PER_UNIT", "0.01"))

# S3 locations. Bucket/prefix values are environment placeholders until the
# real paths are known; override via env vars without code changes.
input_bucket = os.environ.get(
    "INPUT_BUCKET", "s3://mojap-data-production-copilot-usage-reports/"
)
input_prefix = os.environ.get("INPUT_PREFIX", "reports/")

output_bucket = os.environ.get(
    "OUTPUT_BUCKET", "s3://mojap-data-production-copilot-usage-credits/"
)
output_prefix = os.environ.get("OUTPUT_PREFIX", "ai-credits/")

# dev/prod dataset separation, like the example pipeline.
env_label = "prod" if mode == "prod" else "dev"

# Full S3 paths for the target day.
# Input: the day's users-1-day report files (NDJSON, many partition files).
input_path = f"{input_bucket}{input_prefix}{report_day}/users-1-day/"

# Output: one Parquet object for the day.
output_path = (
    f"{output_bucket}{output_prefix}{env_label}/"
    f"day={report_day}/ai_credits.parquet"
)
