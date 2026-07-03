import logging

import awswrangler as wr

import config
from billing import fetch_billing
from credits import build_credit_rows, validate_credits_field
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


def run_per_user(user_path):
    df = read_report(config.org, config.report_day, config.billing_token)
    if df is None or df.empty:
        logger.info("No report data for %s; skipping per-user", config.report_day)
        return
    validate_credits_field(df)
    rows = build_credit_rows(df, config.report_day)
    if rows.empty:
        logger.info("No users with credits for %s; nothing written", config.report_day)
        return
    _write(rows, user_path)
    logger.info("Wrote %d per-user row(s) to %s", len(rows), user_path)


def run_per_model(model_path):
    items = fetch_billing(config.enterprise_slug, config.report_day, config.billing_token)
    if not items:
        logger.info("No billing usageItems for %s; skipping per-model", config.report_day)
        return
    rows = build_model_rows(items, config.report_day)
    _write(rows, model_path)
    logger.info("Wrote %d per-model row(s) to %s", len(rows), model_path)


def main():
    if not config.billing_token:
        raise ValueError("SECRET_ENTERPRISE_BILLING_TOKEN is required")
    user_path, model_path = config.resolve_paths()

    # Per-user first so its Parquet is written before any per-model failure.
    run_per_user(user_path)
    # Fail-loud: a per-model error propagates (non-zero exit) without discarding
    # the per-user write above.
    run_per_model(model_path)


if __name__ == "__main__":
    main()
