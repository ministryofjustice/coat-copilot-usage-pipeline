import awswrangler as wr
import pandas as pd


def read_report(input_path):
    """Read all NDJSON users-1-day report files under input_path into one
    DataFrame. awswrangler reads the many partition files in a single call,
    avoiding the small-files problem on input."""
    return wr.s3.read_json(path=input_path, lines=True, dataset=False)


def validate_credits_field(df):
    """Raise if the report lacks ai_credits_used (reports predate 2026-06-19)."""
    if "ai_credits_used" not in df.columns:
        raise ValueError(
            "No ai_credits_used field in report — report predates 2026-06-19. "
            "Re-download a current day."
        )


def build_credit_rows(df, report_day, enterprise, price_per_unit):
    """Filter users with positive credits and build the flattened billing table
    (one row per user). Mirrors the bash/jq per-user billing object, flattened
    for Parquet/Athena."""
    year, month, day = (int(part) for part in report_day.split("-"))

    credits = df.loc[
        df["ai_credits_used"].fillna(0) > 0, ["user_login", "ai_credits_used"]
    ]

    rows = pd.DataFrame({
        "year": year,
        "month": month,
        "day": day,
        "enterprise": enterprise,
        "user": credits["user_login"].values,
        "product": "Copilot",
        "sku": "Copilot AI Credits",
        "model": "AI Credits",
        "unit_type": "ai-credits",
        "price_per_unit": price_per_unit,
        "gross_quantity": credits["ai_credits_used"].values,
        "gross_amount": credits["ai_credits_used"].values * price_per_unit,
    })

    return rows.reset_index(drop=True)
