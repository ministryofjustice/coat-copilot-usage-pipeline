import pandas as pd


def validate_credits_field(df):
    """Raise if the report lacks ai_credits_used (reports predate 2026-06-19)."""
    if "ai_credits_used" not in df.columns:
        raise ValueError(
            "No ai_credits_used field in report — report predates 2026-06-19. "
            "Re-download a current day."
        )


def build_credit_rows(df, report_day):
    """One row per user with positive credits: day, user_login, ai_credits_used."""
    credits = df.loc[
        df["ai_credits_used"].fillna(0) > 0, ["user_login", "ai_credits_used"]
    ]
    return pd.DataFrame({
        "day": report_day,
        "user_login": credits["user_login"].values,
        "ai_credits_used": credits["ai_credits_used"].values,
    })
