"""Build the two telemetry datasets from the users-1-day report DataFrame.

Both are built from the DataFrame `download.read_report()` already holds, so
neither costs an extra API call.

    telemetry_by_user           one row per person per day
    telemetry_by_user_activity  one row per person per day per language
                                per feature

Pure transform, like `credits.py`: no I/O, no logging, no S3.

Two things this module deliberately does not do. It does not carry
`ai_credits_used` -- `credits_by_user` is the one place the amount lives, and a
`had_credit_charge` boolean is kept in its place so a person who spent credits
but produced no telemetry can still be counted as active. It does not compute
any rate: `loc_suggested_to_add_sum` excludes agent edits while `loc_added_sum`
includes them, so a lines-kept rate over all features exceeds 100%. Rates belong
in the query layer, per feature.

Every column is given an explicit nullable dtype. That is what keeps each
day-partition declaring the same Parquet schema even on days when a whole block
of columns is empty, which is what the Glue crawler reads types from.
"""

import pandas as pd

FLAGS = [
    "used_agent",
    "used_chat",
    "used_cli",
    "used_copilot_app",
    "used_copilot_cloud_agent",
    "used_copilot_coding_agent",
    "used_copilot_code_review_active",
    "used_copilot_code_review_passive",
]

COUNTS = [
    "user_initiated_interaction_count",
    "code_generation_activity_count",
    "code_acceptance_activity_count",
    "loc_suggested_to_add_sum",
    "loc_suggested_to_delete_sum",
    "loc_added_sum",
    "loc_deleted_sum",
]

# Report field -> column prefix. Each is a single JSON object per person-day,
# never an array, so both fold into the person row without changing its grain.
SURFACE = {"totals_by_cli": "cli", "totals_by_copilot_app": "app"}

USER_COLUMNS = (
    ["user_id", "user_login", "enterprise_id"]
    + COUNTS
    + FLAGS
    + ["had_credit_charge", "has_activity_telemetry"]
    + [
        "cli_session_count",
        "cli_request_count",
        "cli_prompt_count",
        "cli_prompt_tokens_sum",
        "cli_output_tokens_sum",
        "cli_version",
        "app_session_count",
        "app_request_count",
        "app_prompt_count",
        "app_prompt_tokens_sum",
        "app_output_tokens_sum",
    ]
    + ["day"]
)

LANG_COUNTS = [
    "code_generation_activity_count",
    "code_acceptance_activity_count",
    "loc_suggested_to_add_sum",
    "loc_suggested_to_delete_sum",
    "loc_added_sum",
    "loc_deleted_sum",
]

LANGUAGE_COLUMNS = (
    ["user_login", "language", "feature", "mode"] + LANG_COUNTS + ["day"]
)

# What Copilot was working as, collapsing the chat and agent variants. The raw
# `feature` is stored alongside it and stays the source of truth.
MODE = {
    "code_completion": "Inline completion",
    "chat_inline": "Chat",
    "chat_panel_ask_mode": "Chat",
    "chat_panel_plan_mode": "Chat",
    "chat_panel_custom_mode": "Chat",
    "chat_panel_unknown_mode": "Chat",
    "chat_panel_agent_mode": "Agent mode",
    "agent_edit": "Agent mode",
    "copilot_cli": "CLI",
    "copilot_app": "Copilot app",
}


def nested(value):
    """A missing nested block arrives as NaN or None, not {} / []."""
    return value if isinstance(value, (dict, list)) else None


def build_user_rows(df, report_day):
    """One row per person-day, keeping records with no activity at all.

    Those records are the point of `has_activity_telemetry`: GitHub sends a
    reduced shape with the used_* flags and both surface blocks absent, and
    some of them still carry credits.
    """
    out = pd.DataFrame(index=df.index)
    out["user_id"] = df["user_id"].astype("Int64")
    out["user_login"] = df["user_login"].astype("string")
    out["enterprise_id"] = df["enterprise_id"].astype("string")
    for column in COUNTS:
        out[column] = df[column].astype("Int64")
    for flag in FLAGS:
        # A day on which every record is the reduced shape has no used_* column
        # at all, so the column cannot be indexed unconditionally.
        column = df[flag] if flag in df.columns else pd.Series(pd.NA, index=df.index)
        out[flag] = column.astype("boolean")
    out["had_credit_charge"] = (df["ai_credits_used"].fillna(0) > 0).astype("boolean")
    out["has_activity_telemetry"] = (
        df["used_cli"].notna()
        if "used_cli" in df.columns
        else pd.Series(False, index=df.index)
    ).astype("boolean")

    for field, prefix in SURFACE.items():
        block = (
            df[field] if field in df.columns else pd.Series(None, index=df.index)
        ).map(lambda value: nested(value) or {})
        tokens = block.map(lambda d: d.get("token_usage") or {})
        for key in ("session_count", "request_count", "prompt_count"):
            # The default argument binds the loop variable; without it every
            # column would read the last key in the loop.
            out[f"{prefix}_{key}"] = block.map(
                lambda d, k=key: d.get(k)
            ).astype("Int64")
        out[f"{prefix}_prompt_tokens_sum"] = tokens.map(
            lambda d: d.get("prompt_tokens_sum")
        ).astype("Int64")
        out[f"{prefix}_output_tokens_sum"] = tokens.map(
            lambda d: d.get("output_tokens_sum")
        ).astype("Int64")
        if prefix == "cli":
            version = block.map(
                lambda d: nested(d.get("last_known_cli_version")) or {}
            )
            out["cli_version"] = version.map(
                lambda d: d.get("cli_version")
            ).astype("string")

    out["day"] = report_day
    return out[USER_COLUMNS].reset_index(drop=True)


def build_language_rows(df, report_day):
    """One row per person, day, language and feature, from the report's
    totals_by_language_feature array. Language strings are stored raw."""
    entries_per_person = (
        df["totals_by_language_feature"]
        if "totals_by_language_feature" in df.columns
        else pd.Series(None, index=df.index)
    )
    rows = []
    for login, entries in zip(df["user_login"], entries_per_person):
        for entry in nested(entries) or []:
            rows.append(
                {
                    "user_login": login,
                    "language": entry.get("language"),
                    "feature": entry.get("feature"),
                    **{c: entry.get(c) for c in LANG_COUNTS},
                }
            )
    out = pd.DataFrame(
        rows, columns=["user_login", "language", "feature"] + LANG_COUNTS
    )
    for column in ("user_login", "language", "feature"):
        out[column] = out[column].astype("string")
    # "others" appears here but not in the mode map, so it falls through.
    out["mode"] = out["feature"].map(MODE).fillna("Other").astype("string")
    for column in LANG_COUNTS:
        out[column] = out[column].astype("Int64")
    out["day"] = report_day
    return out[LANGUAGE_COLUMNS]
