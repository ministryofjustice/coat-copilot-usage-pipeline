# Output datasets

Four Parquet datasets, all Hive-partitioned by `day` (`day=YYYY-MM-DD/`) under
the bucket chosen by `MODE` and the `OUTPUT_PREFIX` prefix. All are written with
`mode="overwrite_partitions"`, so re-running a day replaces that day only.

| Dataset | Grain | Source |
|---|---|---|
| `credits_by_user` | person, day | `users-1-day` metrics report |
| `credits_by_model` | model, day | enterprise `ai_credit/usage` billing API |
| `telemetry_by_user` | person, day | `users-1-day` metrics report |
| `telemetry_by_user_activity` | person, day, language, feature | `users-1-day` metrics report |

Three of the four come from one report download per day. `credits_by_model` is
the only one that calls a second endpoint.

## credits_by_user

| column | description |
|---|---|
| `day` | report day (partition) |
| `user_login` | GitHub username |
| `ai_credits_used` | credits consumed that day; rows with 0 are dropped |

## credits_by_model

| column | description |
|---|---|
| `day` | report day (partition) |
| `model` | model name from the billing report |
| `model_family` | `Opus`, `Sonnet`, `Haiku`, `GPT`, `Gemini`, `CodeReview`, `Other` |
| `routed` | true when `model` starts with `Auto:` |
| `ai_credits_used` | summed `grossQuantity` for that model |

Copilot code review is billed as its own model line, so
`WHERE model_family = 'CodeReview'` gives its cost directly.

## telemetry_by_user

One row per person per day. Every person-day record in the report is kept,
including people with no activity.

| column | type | description |
|---|---|---|
| `day` | string (partition) | report day |
| `user_id` | bigint | GitHub numeric id, stable across renames |
| `user_login` | string | GitHub username |
| `enterprise_id` | string | enterprise the record came from |
| `user_initiated_interaction_count` | bigint | interactions the person started |
| `code_generation_activity_count` | bigint | suggestions offered |
| `code_acceptance_activity_count` | bigint | suggestions accepted |
| `loc_suggested_to_add_sum` | bigint | lines suggested to add, excluding agent edits |
| `loc_suggested_to_delete_sum` | bigint | lines suggested to delete |
| `loc_added_sum` | bigint | lines applied, including agent and edit mode |
| `loc_deleted_sum` | bigint | lines deleted |
| `used_agent` | boolean, nullable | capability flags; see the null rule below |
| `used_chat` | boolean, nullable | |
| `used_cli` | boolean, nullable | |
| `used_copilot_app` | boolean, nullable | |
| `used_copilot_cloud_agent` | boolean, nullable | |
| `used_copilot_coding_agent` | boolean, nullable | |
| `used_copilot_code_review_active` | boolean, nullable | person requested a review |
| `used_copilot_code_review_passive` | boolean, nullable | review ran automatically |
| `ai_credits_used` | double | credits consumed that day; 0 when there was no charge |
| `has_activity_telemetry` | boolean | derived: the full field set arrived |
| `cli_session_count` | bigint, nullable | Copilot CLI, from `totals_by_cli` |
| `cli_request_count` | bigint, nullable | includes automated agentic follow-up calls |
| `cli_prompt_count` | bigint, nullable | user prompts only |
| `cli_prompt_tokens_sum` | bigint, nullable | |
| `cli_output_tokens_sum` | bigint, nullable | |
| `cli_version` | string, nullable | last known CLI version |
| `app_session_count` | bigint, nullable | Copilot app, from `totals_by_copilot_app` |
| `app_request_count` | bigint, nullable | |
| `app_prompt_count` | bigint, nullable | |
| `app_prompt_tokens_sum` | bigint, nullable | |
| `app_output_tokens_sum` | bigint, nullable | |

`ai_credits_used` is the same per-person-day amount `credits_by_user` holds.
It is repeated here so a person who spent credits but produced no telemetry can
still be counted as active without a join. Both datasets are written from the
same report download in the same pass. Two differences from `credits_by_user`:
rows with 0 credits are kept here and dropped there, and a missing amount is
written as 0 here, so `ai_credits_used > 0` is the test for "had a charge".

Do not sum `ai_credits_used` from this dataset and from `credits_by_user` in one
query. It is the same money in both.

## telemetry_by_user_activity

One row per person, day, language and feature. `language` alone does not
identify a row: the same language appears once per feature.

| column | type | description |
|---|---|---|
| `day` | string (partition) | report day |
| `user_login` | string | GitHub username |
| `language` | string | raw value from the report, not normalised |
| `feature` | string | see values below |
| `mode` | string | derived grouping of `feature` |
| `code_generation_activity_count` | bigint | suggestions offered |
| `code_acceptance_activity_count` | bigint | suggestions accepted |
| `loc_suggested_to_add_sum` | bigint | |
| `loc_suggested_to_delete_sum` | bigint | |
| `loc_added_sum` | bigint | |
| `loc_deleted_sum` | bigint | |

`feature` to `mode`:

| feature | mode |
|---|---|
| `code_completion` | Inline completion |
| `chat_inline`, `chat_panel_ask_mode`, `chat_panel_plan_mode`, `chat_panel_custom_mode`, `chat_panel_unknown_mode` | Chat |
| `chat_panel_agent_mode`, `agent_edit` | Agent mode |
| `copilot_cli` | CLI |
| `copilot_app` | Copilot app |
| `others` | Other |

There is no `user_initiated_interaction_count` here. That count exists only at
person level, in `telemetry_by_user`.

The six counts in this dataset sum to the matching person-level totals in
`telemetry_by_user`, so either can be used for a total.

## Query notes

**Null and false mean different things in the `used_*` columns.** Null means
GitHub sent no activity telemetry for that person-day. False means GitHub
reported the capability unused. About a quarter of records arrive in the reduced
shape that produces nulls, and some of them carry credits.
`has_activity_telemetry` is false on exactly those records.

**Do not divide lines applied by lines suggested across all features.** GitHub
excludes agent edits from `loc_suggested_to_add_sum` but includes them in
`loc_added_sum`. Over all features the ratio exceeds 100%. Compute a lines-kept
rate only for `feature = 'code_completion'`.

**Acceptance counts are near zero for agent features**, which apply code without
a discrete accept step. An acceptance rate spanning all features understates
people who work mainly through agents. Group by `feature` or `mode`.

**Language strings are not normalised.** `ts` and `typescript` both occur, as do
`js`/`javascript`/`jsx`, `py`/`python` and `hcl`/`terraform`. Some values are not
languages at all (`prompt`, `instructions`, `vscode`). Normalise in the query or
add a derived column; do not overwrite the raw value.

**Some people have no row in `telemetry_by_user_activity`.** Activity with no
language attached lands as `language = 'others', feature = 'others'` with zero
counts, and code review, the coding agent and the cloud agent have no language
rows at all. Fall back to the `used_*` columns in `telemetry_by_user` when the
activity dataset yields nothing for a person.

**Credits cannot be split by feature or mode.** `ai_credits_used` is one number
per person per day. The billing API splits credits by model only.

## Schema stability

The Glue crawler infers Athena types from the Parquet footer, so the pandas
dtypes at write time decide the column types. `src/telemetry.py` sets an explicit
nullable dtype on every column: `boolean` for the flags, `Int64` for the counts,
`Float64` for the credit amount, `string` for the text. Without that, a column that is all-null for one day writes
as Parquet type `null` and that partition disagrees with the others.
`tests/test_telemetry.py` asserts the dtypes and that no column writes as `null`.
