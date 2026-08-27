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
from telemetry import build_language_rows, build_user_rows

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


# The datasets built from the users-1-day metrics report. credits_by_model is
# not here: it comes from the billing endpoint, in a separate pass.
REPORT_DATASETS = (
    "credits_by_user",
    "telemetry_by_user",
    "telemetry_by_user_activity",
)


def collect_all_rows(days):
    """Download each day's report once and fan the DataFrame out to every
    builder that reads it. The download is the largest cost in the job, so it
    is never repeated per dataset.

    Returns {dataset name: DataFrame}, empty frames included.
    """
    frames = {name: [] for name in REPORT_DATASETS}
    for day in days:
        df = read_report(
            config.enterprise_slug, day, config.billing_token, config.org
        )
        if df is None or df.empty:
            logger.info("No report data for %s; skipping day", day)
            continue
        validate_credits_field(df)

        credit_rows = build_credit_rows(df, day)
        if credit_rows.empty:
            logger.info("No users with credits for %s", day)
        else:
            frames["credits_by_user"].append(credit_rows)

        # No emptiness check here on purpose: a person-day with no activity is
        # exactly the record worth keeping, and has_activity_telemetry is the
        # only thing that tells "did nothing" apart from "no telemetry sent".
        frames["telemetry_by_user"].append(build_user_rows(df, day))

        language_rows = build_language_rows(df, day)
        if language_rows.empty:
            logger.info("No language/feature rows for %s", day)
        else:
            frames["telemetry_by_user_activity"].append(language_rows)

    return {
        name: pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        for name, parts in frames.items()
    }


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
    paths = config.resolve_paths()

    today = datetime.now(timezone.utc).date()
    days = report_days(config.backfill_range, config.report_day, today)
    logger.info("Processing %d day(s): %s .. %s", len(days), days[0], days[-1])

    # One download per day, three datasets out of it, all written before any
    # billing call is made.
    for name, rows in collect_all_rows(days).items():
        if rows.empty:
            logger.info(
                "No %s rows across %d day(s); nothing written", name, len(days)
            )
            continue
        _write(rows, paths[name])
        logger.info("Wrote %d %s row(s) to %s", len(rows), name, paths[name])

    # Fail-loud: a per-model error propagates (non-zero exit) without discarding
    # the writes above.
    run_per_model(paths["credits_by_model"], days)


if __name__ == "__main__":
    main()
