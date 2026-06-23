import logging

import awswrangler as wr

import config
from credits import read_report, validate_credits_field, build_credit_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Extracting AI credits for %s from %s", config.report_day, config.input_path)

    df = read_report(config.input_path)
    validate_credits_field(df)

    rows = build_credit_rows(
        df, config.report_day, config.enterprise, config.price_per_unit
    )

    if rows.empty:
        logger.info("No users with ai_credits_used > 0 for %s; nothing written", config.report_day)
        return

    wr.s3.to_parquet(df=rows, path=config.output_path, index=False)

    logger.info(
        "Wrote %d per-user credit row(s) to %s for %s",
        len(rows),
        config.output_path,
        config.report_day,
    )


if __name__ == "__main__":
    main()
