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
| `MODE` | `dev` | selects the output bucket: `prod` → `PROD_S3_BUCKET`, else `DEV_S3_BUCKET` |
| `DEV_S3_BUCKET` | _(required when `MODE=dev`)_ | output bucket for dev. Accepts `bucket`, `s3://bucket`, or trailing-slash forms. |
| `PROD_S3_BUCKET` | _(required when `MODE=prod`)_ | output bucket for prod. |
| `OUTPUT_PREFIX` | `copilot/` | prefix above the two dataset dirs inside the bucket |
| `SECRET_ENTERPRISE_BILLING_TOKEN` | _(required)_ | GitHub token used for **both** the metrics report and the enterprise billing call. Needs Copilot metrics read **and** `manage_billing:enterprise`. Injected by Analytical Platform Airflow from the `enterprise-billing-token` secret; for local runs, export it. |
| `ORG` | `ministryofjustice` | GitHub org for the metrics-reports API |
| `ENTERPRISE_SLUG` | `ministry-of-justice-uk` | enterprise slug in the billing API URL |
| `REPORT_DAY` | yesterday (UTC) | target day, `YYYY-MM-DD` |

> The output bucket is chosen by `MODE` from the two bucket variables; a missing
> bucket for the active `MODE` (or a missing token) fails the job at startup.

---

## Template setup notes

This repository was created from the Analytical Platform Airflow Python template.

## Included Files

The repository comes with the following preset files:

- GitHub Actions workflows
  - Dependency review (if your repository is public) (`.github/workflows/dependency-review.yml`)
  - Container release to Analytical Platform's ECR (`.github/workflows/release-container.yml`)
  - Container scan with Trivy (`.github/workflows/scan-container.yml`)
  - Container structure test (`.github/workflows/test-container.yml`)
- CODEOWNERS
- Dependabot configuration
- Dockerfile
- MIT License

## Setup Instructions

Once you've created your repository using this template, ensure the following steps:

### Update README

Edit this README.md file to document your project accurately. Take the time to create a clear, engaging, and informative README.md file. Include information like what your project does, how to install and run it, how to contribute, and any other pertinent details.

### Update repository description

After you've created your repository, GitHub provides a brief description field that appears on the top of your repository's main page. This is a summary that gives visitors quick insight into the project. Using this field to provide a succinct overview of your repository is highly recommended.

This description and your README.md will be one of the first things people see when they visit your repository. It's a good place to make a strong, concise first impression. Remember, this is often visible in search results on GitHub and search engines, so it's also an opportunity to help people discover your project.

### Grant Team Permissions

Assign permissions to the appropriate Ministry of Justice teams. Ensure at least one team is granted Admin permissions. Whenever possible, assign permissions to teams rather than individual users.

### Read about the GitHub repository standards

Familiarise yourself with the Ministry of Justice GitHub Repository Standards. These standards ensure consistency, maintainability, and best practices across all our repositories.

You can find the standards [here](https://user-guide.operations-engineering.service.justice.gov.uk/documentation/information/mojrepostandards.html).

Please read and understand these standards thoroughly and enable them when you feel comfortable.

### Modify the GitHub Standards Badge

Once you've ensured that all the [GitHub Repository Standards](https://user-guide.operations-engineering.service.justice.gov.uk/documentation/information/mojrepostandards.html) have been applied to your repository, it's time to update the Ministry of Justice (MoJ) Compliance Badge located in the README file.

The badge demonstrates that your repository is compliant with MoJ's standards. Please follow these [instructions](https://user-guide.operations-engineering.service.justice.gov.uk/documentation/information/add-repo-badge.html) to modify the badge URL to reflect the status of your repository correctly.

**Please note** the badge will not function correctly if your repository is internal or private. In this case, you may remove the badge from your README.

### Manage Outside Collaborators

To add an Outside Collaborator to the repository, follow the guidelines detailed [here](https://github.com/ministryofjustice/github-collaborators).

### Update CODEOWNERS

(Optional) Modify the CODEOWNERS file to specify the teams or users authorized to approve pull requests.

### Configure Dependabot

Adapt the dependabot.yml file to match your project's [dependency manager](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#package-ecosystem) and to enable [automated pull requests for package updates](https://docs.github.com/en/code-security/supply-chain-security).

### Dependency Review

If your repository is private with no GitHub Advanced Security license, remove the `.github/workflows/dependency-review.yml` file.
