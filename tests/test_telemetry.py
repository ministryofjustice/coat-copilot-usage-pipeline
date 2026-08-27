import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import telemetry


def _full_record(**overrides):
    """A person-day record with every field the report sends when a person was
    active. Mirrors what pd.read_json(lines=True) produces from the NDJSON."""
    record = {
        "user_id": 1,
        "user_login": "alice",
        "enterprise_id": "83",
        "user_initiated_interaction_count": 10,
        "code_generation_activity_count": 8,
        "code_acceptance_activity_count": 3,
        "loc_suggested_to_add_sum": 100,
        "loc_suggested_to_delete_sum": 0,
        "loc_added_sum": 120,
        "loc_deleted_sum": 5,
        "used_agent": True,
        "used_chat": True,
        "used_cli": False,
        "used_copilot_app": False,
        "used_copilot_cloud_agent": False,
        "used_copilot_coding_agent": False,
        "used_copilot_code_review_active": True,
        "used_copilot_code_review_passive": False,
        "ai_credits_used": 12.5,
        "totals_by_cli": np.nan,
        "totals_by_copilot_app": np.nan,
        "totals_by_language_feature": [
            {
                "language": "python",
                "feature": "code_completion",
                "code_generation_activity_count": 5,
                "code_acceptance_activity_count": 2,
                "loc_suggested_to_add_sum": 100,
                "loc_suggested_to_delete_sum": 0,
                "loc_added_sum": 40,
                "loc_deleted_sum": 0,
            },
            {
                "language": "terraform",
                "feature": "agent_edit",
                "code_generation_activity_count": 3,
                "code_acceptance_activity_count": 1,
                "loc_suggested_to_add_sum": 0,
                "loc_suggested_to_delete_sum": 0,
                "loc_added_sum": 80,
                "loc_deleted_sum": 5,
            },
        ],
    }
    record.update(overrides)
    return record


def _reduced_record(**overrides):
    """The shape GitHub sends when it has no activity telemetry for a person:
    every used_* flag, both surface blocks and the language array are absent.
    26% of August 2026 records arrived this way."""
    record = {
        "user_id": 2,
        "user_login": "bob",
        "enterprise_id": "83",
        "user_initiated_interaction_count": 0,
        "code_generation_activity_count": 0,
        "code_acceptance_activity_count": 0,
        "loc_suggested_to_add_sum": 0,
        "loc_suggested_to_delete_sum": 0,
        "loc_added_sum": 0,
        "loc_deleted_sum": 0,
        "ai_credits_used": 3.0,
    }
    record.update(overrides)
    return record


def _frame(*records):
    """Build the DataFrame the same way pd.read_json(lines=True) would: a field
    absent from one record but present in another arrives as NaN."""
    return pd.DataFrame(list(records))


# --- telemetry_by_user -----------------------------------------------------


def test_reduced_record_keeps_used_cli_null_not_false():
    rows = telemetry.build_user_rows(
        _frame(_full_record(), _reduced_record()), "2026-08-20"
    )
    assert rows["used_cli"].tolist() == [False, pd.NA]
    assert rows["has_activity_telemetry"].tolist() == [True, False]


def test_builds_when_no_used_cli_column_at_all():
    # A day where every record is the reduced shape has no used_* column.
    rows = telemetry.build_user_rows(_frame(_reduced_record()), "2026-08-20")
    assert rows["used_cli"].isna().all()
    assert rows["has_activity_telemetry"].tolist() == [False]


def test_builds_when_surface_block_is_nan():
    # pd.read_json gives NaN, not {}, for an absent totals_by_cli.
    rows = telemetry.build_user_rows(_frame(_full_record()), "2026-08-20")
    assert rows["cli_request_count"].isna().all()
    assert rows["cli_version"].isna().all()


def test_cli_and_app_blocks_are_folded_into_columns():
    record = _full_record(
        totals_by_cli={
            "session_count": 4,
            "request_count": 40,
            "prompt_count": 12,
            "token_usage": {"prompt_tokens_sum": 900, "output_tokens_sum": 70},
            "last_known_cli_version": {"cli_version": "1.2.3"},
        },
        totals_by_copilot_app={
            "session_count": 1,
            "request_count": 2,
            "prompt_count": 2,
            "token_usage": {"prompt_tokens_sum": 50, "output_tokens_sum": 5},
        },
    )
    rows = telemetry.build_user_rows(_frame(record), "2026-08-20")
    assert rows["cli_session_count"].tolist() == [4]
    assert rows["cli_prompt_tokens_sum"].tolist() == [900]
    assert rows["cli_version"].tolist() == ["1.2.3"]
    assert rows["app_request_count"].tolist() == [2]
    assert rows["app_output_tokens_sum"].tolist() == [5]


def test_carries_the_credit_amount():
    rows = telemetry.build_user_rows(
        _frame(
            _full_record(ai_credits_used=12.5),
            _reduced_record(ai_credits_used=0.0),
        ),
        "2026-08-20",
    )
    assert rows["ai_credits_used"].tolist() == [12.5, 0.0]
    assert rows["ai_credits_used"].dtype.name == "Float64"


def test_missing_credit_amount_becomes_zero():
    # A person-day with no charge must read as 0, not null, so "0 means no
    # charge" holds without a null check.
    rows = telemetry.build_user_rows(
        _frame(_full_record(ai_credits_used=None)), "2026-08-20"
    )
    assert rows["ai_credits_used"].tolist() == [0.0]


def test_user_column_order_matches_the_declared_schema():
    rows = telemetry.build_user_rows(_frame(_full_record()), "2026-08-20")
    assert list(rows.columns) == telemetry.USER_COLUMNS


def test_user_dtypes_are_nullable_never_object_or_float():
    rows = telemetry.build_user_rows(
        _frame(_full_record(), _reduced_record()), "2026-08-20"
    )
    for flag in telemetry.FLAGS:
        assert rows[flag].dtype.name == "boolean", flag
    for count in telemetry.COUNTS:
        assert rows[count].dtype.name == "Int64", count
    for token in ["cli_request_count", "app_prompt_tokens_sum"]:
        assert rows[token].dtype.name == "Int64", token
    assert rows["user_login"].dtype.name == "string"
    assert rows["cli_version"].dtype.name == "string"


def test_all_null_surface_columns_write_as_int64_not_parquet_null(tmp_path):
    # 2026-08-02 had zero Copilot app blocks, so every app_* column was null
    # for that whole partition. Without explicit dtypes it lands as Parquet
    # type "null" and disagrees with every other partition.
    rows = telemetry.build_user_rows(_frame(_full_record()), "2026-08-20")
    path = tmp_path / "user.parquet"
    rows.drop(columns=["day"]).to_parquet(path, index=False)
    schema = pq.read_schema(path)
    types = dict(zip(schema.names, [str(t) for t in schema.types]))
    assert "null" not in types.values(), types
    assert types["app_request_count"] == "int64"
    assert types["cli_version"] in ("string", "large_string")
    assert types["used_cli"] == "bool"


# --- telemetry_by_user_activity -------------------------------------------


def test_language_rows_are_one_per_person_language_feature():
    rows = telemetry.build_language_rows(_frame(_full_record()), "2026-08-20")
    assert len(rows) == 2
    assert rows["user_login"].tolist() == ["alice", "alice"]
    assert rows["language"].tolist() == ["python", "terraform"]
    assert rows["feature"].tolist() == ["code_completion", "agent_edit"]


def test_language_rows_sum_to_the_person_level_totals():
    df = _frame(_full_record(), _reduced_record())
    user_rows = telemetry.build_user_rows(df, "2026-08-20")
    lang_rows = telemetry.build_language_rows(df, "2026-08-20")
    for column in telemetry.LANG_COUNTS:
        assert lang_rows[column].sum() == user_rows[column].sum(), column


def test_feature_others_maps_to_mode_other():
    # "others" appears in totals_by_language_feature but not in the mode map.
    record = _full_record(
        totals_by_language_feature=[
            {"language": "others", "feature": "others",
             "code_generation_activity_count": 0}
        ]
    )
    rows = telemetry.build_language_rows(_frame(record), "2026-08-20")
    assert rows["mode"].tolist() == ["Other"]


def test_chat_and_agent_features_collapse_into_modes():
    record = _full_record(
        totals_by_language_feature=[
            {"language": "python", "feature": "chat_panel_ask_mode"},
            {"language": "python", "feature": "chat_panel_agent_mode"},
            {"language": "python", "feature": "code_completion"},
            {"language": "python", "feature": "copilot_cli"},
        ]
    )
    rows = telemetry.build_language_rows(_frame(record), "2026-08-20")
    assert rows["mode"].tolist() == [
        "Chat", "Agent mode", "Inline completion", "CLI"
    ]


def test_language_rows_empty_when_no_language_array():
    rows = telemetry.build_language_rows(_frame(_reduced_record()), "2026-08-20")
    assert rows.empty
    assert list(rows.columns) == telemetry.LANGUAGE_COLUMNS


def test_language_column_order_matches_the_declared_schema():
    rows = telemetry.build_language_rows(_frame(_full_record()), "2026-08-20")
    assert list(rows.columns) == telemetry.LANGUAGE_COLUMNS


def test_language_dtypes_are_nullable_never_object_or_float():
    rows = telemetry.build_language_rows(_frame(_full_record()), "2026-08-20")
    assert rows["language"].dtype.name == "string"
    assert rows["mode"].dtype.name == "string"
    for column in telemetry.LANG_COUNTS:
        assert rows[column].dtype.name == "Int64", column


def test_empty_language_partition_still_writes_typed_columns(tmp_path):
    rows = telemetry.build_language_rows(_frame(_reduced_record()), "2026-08-20")
    path = tmp_path / "activity.parquet"
    rows.drop(columns=["day"]).to_parquet(path, index=False)
    types = [str(t) for t in pq.read_schema(path).types]
    assert "null" not in types, types
