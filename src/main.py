import logging
from datetime import datetime, timezone

import awswrangler as wr
import pandas as pd

import config
from billing import fetch_billing
from credits import build_credit_rows, validate_credits_field
from dates import report_days
from download import read_report
from models import build_model_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _write(rows, path):
    wr.s3.to_parquet(
        df=rows,
        path=path,
        dataset=True,
        partition_cols=["day"],
        mode="overwrite_partitions",
        index=False,
    )


def collect_user_rows(days):
    """Build per-user credit rows across days, skipping not-ready/empty days."""
    frames = []
    for day in days:
        df = read_report(config.org, day, config.billing_token)
        if df is None or df.empty:
            logger.info("No report data for %s; skipping per-user day", day)
            continue
        validate_credits_field(df)
        rows = build_credit_rows(df, day)
        if rows.empty:
            logger.info("No users with credits for %s; skipping per-user day", day)
            continue
        frames.append(rows)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def collect_model_rows(days):
    """Build per-model credit rows across days. Empty usageItems days are
    skipped; a non-2xx billing response raises (fail-loud)."""
    frames = []
    for day in days:
        items = fetch_billing(config.enterprise_slug, day, config.billing_token)
        if not items:
            logger.info("No billing usageItems for %s; skipping per-model day", day)
            continue
        frames.append(build_model_rows(items, day))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def run_per_user(user_path, days):
    rows = collect_user_rows(days)
    if rows.empty:
        logger.info("No per-user rows across %d day(s); nothing written", len(days))
        return
    _write(rows, user_path)
    logger.info("Wrote %d per-user row(s) to %s", len(rows), user_path)


def run_per_model(model_path, days):
    rows = collect_model_rows(days)
    if rows.empty:
        logger.info("No per-model rows across %d day(s); nothing written", len(days))
        return
    _write(rows, model_path)
    logger.info("Wrote %d per-model row(s) to %s", len(rows), model_path)


def main():
    if not config.billing_token:
        raise ValueError("SECRET_ENTERPRISE_BILLING_TOKEN is required")
    user_path, model_path = config.resolve_paths()

    today = datetime.now(timezone.utc).date()
    days = report_days(config.backfill_range, config.report_day, today)
    logger.info("Processing %d day(s): %s .. %s", len(days), days[0], days[-1])

    # Per-user first so its Parquet is written before any per-model failure.
    run_per_user(user_path, days)
    # Fail-loud: a per-model error propagates (non-zero exit) without discarding
    # the per-user write above.
    run_per_model(model_path, days)


if __name__ == "__main__":
    main()
