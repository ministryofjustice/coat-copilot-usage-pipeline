# COAT Copilot Usage Pipeline — AI Credits Extraction

[![Ministry of Justice Repository Compliance Badge](https://github-community.service.justice.gov.uk/repository-standards/api/analytical-platform-airflow-python-template/badge)](https://github-community.service.justice.gov.uk/repository-standards/analytical-platform-airflow-python-template)

This repository contains a Python pipeline that runs as a container on the
Analytical Platform's [Airflow infrastructure](https://github.com/ministryofjustice/analytical-platform-airflow).
It reproduces, as an Airflow job, the daily GitHub Copilot AI-credit extraction
done by the `getusagedata/daily.sh` reference script. It writes **two**
day-partitioned Parquet datasets straight to S3 — no intermediate CSV and no raw
report landing in S3 — queryable in Athena:

- **`credits_by_user`** — per-user AI credits from the `users-1-day` Copilot
  *usage-metrics* report (carries per-user `ai_credits_used` since 2026-06-19).
- **`credits_by_model`** — per-model AI credits from the enterprise *billing*
  `ai_credit/usage` API, tagged with a model family and a `routed` flag.

## What it does

The two paths are independent and run in order (per-user first):

**Per-user (`credits_by_user`)**

1. Fetches the day's `users-1-day` report download links from the GitHub API
   (`GET /orgs/{org}/copilot/metrics/reports/users-1-day`). Skips cleanly if the
   report is not yet available.
2. Downloads each NDJSON part **into memory** (never persisted to S3).
3. Validates the `ai_credits_used` field is present (reports predate 2026-06-19
   otherwise).
4. Filters users with `ai_credits_used > 0` and writes the `credits_by_user`
   dataset for the day.

**Per-model (`credits_by_model`)**

5. Fetches the enterprise `ai_credit/usage` billing report
   (`GET /enterprises/{slug}/settings/billing/ai_credit/usage`) into memory.
   Skips the dataset if there are no `usageItems`.
6. Groups by model, sums `grossQuantity`, tags `model_family`
   (`Opus | Sonnet | Haiku | GPT | Gemini | CodeReview | Other`) and
   `routed` (`model` starts with `Auto:`), and writes the `credits_by_model`
   dataset for the day.

Both datasets are written with `mode="overwrite_partitions"`, so re-running a day
replaces just that day's partition (idempotent — no double counts).

**Failure policy (fail-loud):** per-user is written first; if the per-model path
then fails (e.g. the token lacks `manage_billing:enterprise` scope), the job
exits non-zero so Airflow flags the run — but the per-user Parquet is already
written and kept.

## Output datasets

Both Hive-partitioned by `day` (`day=YYYY-MM-DD/`) under the selected bucket:

`{prefix}credits_by_user/day=YYYY-MM-DD/`

| column | description |
|---|---|
| `day` | report day (partition) |
| `user_login` | Copilot user login |
| `ai_credits_used` | AI credits the user consumed that day (`> 0`) |

`{prefix}credits_by_model/day=YYYY-MM-DD/`

| column | description |
|---|---|
| `day` | report day (partition) |
| `model` | model name from the billing report |
| `model_family` | `Opus`/`Sonnet`/`Haiku`/`GPT`/`Gemini`/`CodeReview`/`Other` |
| `routed` | `true` when `model` starts with `Auto:` |
| `ai_credits_used` | summed `grossQuantity` for that model |

## Configuration (environment variables)

| variable | default | description |
|---|---|---|
| `MODE` | `dev` | selects the output bucket: `prod` → `PROD_BUCKET`, else `DEV_BUCKET` |
| `DEV_BUCKET` | _(required for dev)_ | output S3 bucket used when `MODE` is not `prod`. No default — an unset value fails the job at startup. In Airflow, supplied via the manifest's per-task `env_vars`. |
| `PROD_BUCKET` | _(required for prod)_ | output S3 bucket used when `MODE=prod`. No default — an unset value fails the job at startup. In Airflow, supplied via the manifest's per-task `env_vars`. |
| `OUTPUT_PREFIX` | `reports-live-consolidated` | prefix above the two dataset dirs inside the bucket |
| `SECRET_ENTERPRISE_BILLING_TOKEN` | _(required)_ | GitHub token used for **both** the metrics report and the enterprise billing call. Needs Copilot metrics read **and** `manage_billing:enterprise`. Injected by Analytical Platform Airflow from the `enterprise-billing-token` secret; for local runs, export it. |
| `ORG` | `ministryofjustice` | GitHub org for the metrics-reports API |
| `ENTERPRISE_SLUG` | `ministry-of-justice-uk` | enterprise slug in the billing API URL |
| `REPORT_DAY` | yesterday (UTC) | target day for a single-day run, `YYYY-MM-DD` (ignored when `BACKFILL_RANGE` is set) |
| `BACKFILL_RANGE` | _(empty)_ | `` (empty) = single day; `week` or `month` = catch-up range (see below) |

> The output bucket is chosen by `MODE` and read from `DEV_BUCKET` / `PROD_BUCKET`
> (no bucket names are hardcoded). A missing bucket for the active `MODE`, or a
> missing billing token, fails the job at startup.

## Backfill range

`BACKFILL_RANGE` runs the job over several days in one invocation, always ending
**yesterday (UTC)**:

| value | days processed |
|---|---|
| _(empty)_ | a single day — `REPORT_DAY` or yesterday (unchanged default) |
| `week` | Monday of the current week … yesterday, inclusive |
| `month` | the 1st of the current month … yesterday, inclusive |

When a range is set, `REPORT_DAY` is ignored. If the computed start is after
yesterday (today is a Monday for `week`, or the 1st for `month`), the range
collapses to just yesterday so the job never does nothing. An unrecognised value
fails the job at startup.

Within a range, each day is written to its own `day=YYYY-MM-DD/` partition
(`mode="overwrite_partitions"` — idempotent, no double counts). Days whose
per-user report isn't ready (or has no credits) are skipped and the run
continues; for the per-model path, a day with no billing `usageItems` is skipped,
but a failed billing request (e.g. a token lacking `manage_billing:enterprise`)
fails the job non-zero.

## Contributing

For running the pipeline locally, testing it, the failure policy, releasing it,
and how to extend it (a different sink, taxonomy, or upstream API), see
[CONTRIBUTING.md](CONTRIBUTING.md).

This pipeline is maintained for the Ministry of Justice's own use and steered by
our internal roadmap, so we can only merge pull requests that coincide with where
we're already going — please open an issue first for anything beyond a small fix.
You are free to fork it under the [MIT licence](LICENSE) and point it at your own
org, enterprise, and buckets — all of which are environment variables, not code
changes; see
[Contributions, forks, and governance](CONTRIBUTING.md#contributions-forks-and-governance).

## Licence

Licensed under the [MIT License](LICENSE). © Crown Copyright (Ministry of Justice).
